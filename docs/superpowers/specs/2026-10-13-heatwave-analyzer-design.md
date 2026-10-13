# Climate Hazard Trend Analyzer — Heatwave Design Spec

- **Date:** 2026-10-13
- **Status:** Approved in conversation, pending written-spec review
- **Scope:** Heatwave hazard end-to-end (frontend, backend, database, deployment). Other hazards (heavy rainfall, drought) are later, separate specs that plug into the same pipeline.

---

## 1. Goals and success criteria

**Goal:** A deployed web app where a user picks a region and a year range and sees how heatwaves in that region have changed over time, with statistically honest summary insights.

**Success criteria**
1. A user can select a region as a **city**, a **state**, or a **custom lat-lon box**, choose a year range (1940 … last complete year), and get results for the **Heatwave** hazard (selected by default).
2. Results include yearly time-series charts (frequency, duration, intensity), a trend line, a 5-year rolling mean, the list of detected events, and rule-generated insight sentences that only claim a trend when it is statistically significant.
3. Weather data is fetched from a public API, cleaned, cached and stored in **MongoDB**; analysis results are stored in MongoDB and API calls read from it.
4. The backend validates all input, rate-limits per IP, and accesses external APIs safely (timeouts, retries, fixed hosts).
5. The app is deployed on free tiers (Vercel + Render + MongoDB Atlas M0) and documented in a README covering setup, architecture, data sources, hazard logic, assumptions, AI-tool usage and future improvements.
6. The author can explain and modify every part live in an interview, so code favours clarity over cleverness.

**Bonus items in scope (after the core works):** Leaflet map region selection, CSV + PDF export, Sen's slope + Mann-Kendall trend detection.

**Out of scope for this spec:** other hazards, user accounts, background job queues, multi-instance deployment.

## 2. Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, httpx (async), pandas/numpy, pymannkendall (or own implementation), matplotlib (PDF/plots), slowapi (rate limiting), motor (async MongoDB driver) |
| Database | MongoDB Atlas M0 (prod), MongoDB in Docker (local dev) |
| Frontend | React + TypeScript + Vite, TanStack Query, Chart.js via react-chartjs-2, Leaflet via react-leaflet |
| Hosting | Frontend: Vercel. Backend: Render free web service. DB: Atlas M0 |
| Tests | pytest + respx (backend), Vitest (frontend helpers) |

## 3. Data sources

| Source | Use | Auth |
|---|---|---|
| Open-Meteo Historical Weather API — `https://archive-api.open-meteo.com/v1/archive` (ERA5 reanalysis, ~25 km grid, daily, 1940 → present) | Daily `temperature_2m_max` (and `precipitation_sum`, stored for future hazards) | None |
| Open-Meteo Geocoding — `https://geocoding-api.open-meteo.com/v1/search` | City search → lat/lon | None |
| Nominatim (OpenStreetMap) — `https://nominatim.openstreetmap.org/search` | State search → bounding box | None; max 1 req/s, custom `User-Agent` required |

NOAA NCEI Access Data Service (station data) is a possible future second source; not in this scope.

## 4. Architecture

Approach **A — compute on demand, cache in MongoDB.**

```
React (Vercel) ──HTTPS──► FastAPI (Render) ──► Open-Meteo / Nominatim
                                │
                                ▼
                         MongoDB Atlas
              (weather_daily, analyses, geocode_cache)
```

### Backend modules

| Module | Responsibility | Depends on |
|---|---|---|
| `api/` | Routes, request/response models, error handlers, rate limits | services |
| `services/region.py` | Resolve a region (point or box) into a list of ERA5 grid points + normalized cache key | — |
| `services/ingest.py` | Get daily series for grid points: read `weather_daily`, fetch missing points from Open-Meteo, validate, store | clients, db |
| `services/cleaning.py` | Units check, physical bounds, gap interpolation (≤2 days), year quality flags | — |
| `hazards/base.py` | Hazard interface: `analyze(series, years, params) -> HazardResult` | — |
| `hazards/heatwave.py` | Threshold climatology, event detection, yearly metrics | cleaning |
| `services/trends.py` | Sen's slope, Mann-Kendall, OLS line, rolling mean, % change rules | — |
| `services/insights.py` | Rule-based insight sentences + caveats | trends |
| `services/analysis.py` | Orchestrates: cache lookup → ingest → clean → hazard → trends → insights → store | all above |
| `services/export.py` | CSV and PDF (matplotlib) generation from a stored analysis | — |
| `clients/` | httpx client wrappers for Open-Meteo, geocoding, Nominatim (timeouts, retries, outbound rate limit, response validation) | — |
| `db.py` | Motor client, collections, index creation on startup | — |
| `scripts/seed.py` | Pre-warm demo cities | analysis |

Adding a hazard later = add `hazards/<name>.py` implementing the same interface + register it in the hazard enum.

### `POST /api/analyze` flow
1. Pydantic validates input (see §7).
2. `region.py` snaps the region to the 0.25° ERA5 grid and computes the cache key `sha256(hazard | normalized region | start-end | algo_version)`.
3. Look up `analyses` by key → if found, return with `cached: true`.
4. Acquire a per-key `asyncio.Lock` (so concurrent identical requests compute once); re-check the cache.
5. `ingest.py` loads each grid point from `weather_daily`; points not present are fetched from Open-Meteo (full 1940-01-01 → last complete year, one call with multiple coordinates), validated and stored.
6. For a box: average the points' daily `tmax` into one regional series (area-average).
7. Clean → heatwave analysis → trends → insights.
8. Store in `analyses`, return with `cached: false`.

### Region handling
- **City:** single point from geocoding.
- **Box:** sample a grid of up to 3×3 points evenly inside the box (fewer if the box is smaller than the grid spacing), snapped to 0.25° and de-duplicated. Max box size 5°×5°.
- **State:** Nominatim bounding box → treated as a box. If the state's box exceeds 5°×5°, it is shrunk around its centre to 5°×5°, and the response includes a caveat saying so.

## 5. Heatwave logic

### 5.1 Cleaning
| Issue | Rule |
|---|---|
| Units | Request °C; verify `daily_units.temperature_2m_max == "°C"`, otherwise reject as upstream error |
| Impossible values | `tmax < -90` or `tmax > 60` → missing |
| Gaps of 1–2 consecutive missing days | Linear interpolation |
| Gaps of ≥3 days | Remain missing; a missing day breaks a heatwave run |
| Year quality | Year with >10% missing days (after interpolation) → `low_quality: true`; excluded from trends, shown faded in charts |
| Feb 29 | Uses the Feb 28 threshold |

A `data_quality` report (total days, values removed, values interpolated, low-quality years) is returned with each analysis.

### 5.2 Threshold climatology
- Baseline: fixed **1961–1990**, independent of the user's selected range.
- For each day-of-year *d* (365-day calendar), collect baseline `tmax` values from days *d−7 … d+7* (wrapping around year ends) across all baseline years → 95th percentile → `threshold[d]`.
- Parameters (stored with each analysis): `percentile=95`, `window=7`, `baseline=[1961,1990]`, `min_days=3`.

### 5.3 Event detection
- A **heatwave** is a run of **≥3 consecutive days** with `tmax > threshold[doy]`.
- Missing values break runs.
- An event belongs to the year in which it **starts**.
- Each event records: `start`, `end`, `days`, `peak_tmax`, `mean_exceedance` (mean of `tmax − threshold` over the event).

### 5.4 Yearly metrics
| Key | Meaning |
|---|---|
| `HWN` | Number of heatwave events |
| `HWF` | Total heatwave days |
| `HWD` | Length of longest event (days); 0 if none |
| `HWM` | Mean exceedance (°C above threshold) over all heatwave days; null if none |
| `HWA` | Peak `tmax` across all events (°C); null if none |

### 5.5 Trends (per metric, using non-low-quality years with non-null values)
- **Sen's slope** (reported per decade) — robust trend magnitude.
- **Mann-Kendall test** p-value; `significant = p < 0.05`.
- **OLS** slope/intercept — for the dashed trend line on charts.
- **5-year centred rolling mean** — for the smoothed chart line.
- **% change** = (Sen line value at end year − value at start year) / value at start year × 100, where the Sen line passes through the median point. If the start value is < 1 (or < 0.5 °C for HWM), report absolute change instead of %.
- Fewer than **10** usable years → trend fields null, with reason `"insufficient_years"`.

### 5.6 Insights (rule-based, no free-form generation)
- Significant: "Heatwave days in {region} increased by about {pct}% between {start} and {end} ({sen:+.1f} days/decade, statistically significant, p = {p:.3f})."
- Not significant: "Heatwave {metric} shows a slight {upward/downward} change, but it is not statistically significant (p = {p:.2f}) and may reflect natural year-to-year variability."
- Insufficient years / no events: explicit plain statements.
- Standard caveats: ERA5 is ~25 km gridded reanalysis and smooths local extremes; the threshold is relative to the 1961–1990 local climate; box/state results are area-averaged.

## 6. MongoDB schema

### `weather_daily` — raw cache, one document per ERA5 grid point
```json
{
  "_id": "openmeteo:28.50:77.25",
  "source": "open-meteo-era5",
  "lat": 28.50, "lon": 77.25,
  "start_date": "1940-01-01",
  "end_date": "2025-12-31",
  "units": { "tmax": "°C", "precip": "mm" },
  "tmax": [18.7, 18.5, null, ...],
  "precip": [0.0, 0.0, 0.0, ...],
  "fetched_at": "2026-10-13T10:00:00Z"
}
```
- Array index = day offset from `start_date`. ~31k values per array (~300 KB doc).
- No expiry. If `end_date` < last complete year, fetch only the missing tail and append.

### `analyses` — computed results cache
```json
{
  "_id": "<sha256 cache key>",
  "hazard": "heatwave",
  "algo_version": "v1",
  "region": { "type": "point|box", "label": "Delhi, IN", "bbox": null, "points": [[28.50, 77.25]] },
  "years": { "start": 1990, "end": 2020 },
  "params": { "percentile": 95, "min_days": 3, "window": 7, "baseline": [1961, 1990] },
  "yearly": [ { "year": 1990, "HWN": 2, "HWF": 7, "HWD": 4, "HWM": 1.8, "HWA": 45.1, "low_quality": false } ],
  "events": [ { "start": "1990-05-12", "end": "1990-05-15", "days": 4, "peak_tmax": 45.1, "mean_exceedance": 1.9 } ],
  "threshold_by_doy": [ "...365 values" ],
  "trends": { "HWF": { "sen_per_decade": 4.2, "mk_p": 0.003, "significant": true, "ols": { "slope": 0.41, "intercept": -812.3 }, "change": { "kind": "pct", "value": 120 }, "reason": null } },
  "insights": [ "..." ],
  "caveats": [ "..." ],
  "data_quality": { "days": 11323, "removed": 0, "interpolated": 0, "low_quality_years": [] },
  "created_at": "...",
  "expires_at": "..."
}
```
- TTL index on `expires_at` (30 days after creation).
- Bumping `algo_version` invalidates old results automatically (new keys).

### `geocode_cache`
`{ "_id": "<kind>:<normalized query>", "results": [...], "expires_at": ... }` — TTL 7 days.

All writes are upserts on deterministic `_id`s. No user-supplied value is ever used as a query object.

## 7. API

Base path `/api`; OpenAPI docs at `/docs`.

| Method | Route | Purpose | Rate limit / IP |
|---|---|---|---|
| GET | `/health` | Liveness + DB ping | — |
| GET | `/hazards` | Hazard list (`heatwave` enabled; others `coming_soon`) | 60/min |
| GET | `/geocode?q=&kind=city\|state` | City → points; state → bbox | 30/min |
| POST | `/analyze` | Run or return cached analysis | 10/min |
| GET | `/analyses/{id}` | Read stored analysis | 60/min |
| GET | `/analyses/{id}/export.csv` | Yearly metrics + events CSV | 10/min |
| GET | `/analyses/{id}/report.pdf` | PDF: insights + trend plots (matplotlib) | 10/min |

### `POST /analyze` request
```json
{
  "hazard": "heatwave",
  "region": { "type": "point", "lat": 28.61, "lon": 77.21, "label": "Delhi, IN" },
  "start_year": 1990,
  "end_year": 2020
}
```
Box variant: `{ "type": "box", "south": 26.0, "west": 74.0, "north": 28.5, "east": 77.0, "label": "Custom" }`.

### Response
The `analyses` document plus `id`, `cached`, and a `chart` block with plot-ready arrays per metric: `years`, values, `rolling5`, `trendline`.

### Validation
- `hazard`: enum.
- lat ∈ [−90, 90], lon ∈ [−180, 180]; box: `south < north`, `west < east`, each side ≤ 5°.
- Years ∈ [1940, last complete year]; `start_year ≤ end_year`.
- `q`: trimmed, 2–100 chars. `label`: ≤100 chars, rendered as plain text only.
- `id` path param: 64-char hex regex.

### Errors
Uniform body `{ "error": { "code": "...", "message": "..." } }`.
422 validation · 404 not found · 429 rate limited (+ `Retry-After`) · 502 upstream error · 504 upstream timeout · 500 generic (no stack traces).

### External access safety
- Base URLs fixed in config; user input only ever becomes URL-encoded query params.
- Shared `httpx.AsyncClient`: 10 s connect / 30 s read timeouts; 2 retries with exponential backoff on 429/5xx only.
- Nominatim: ≤1 req/s outbound limiter, descriptive `User-Agent`.
- Response validation (array lengths match, units, coordinates near request); invalid responses are never cached.

### Other security/performance
- CORS allowlist: Vercel domain + localhost.
- Secrets (Mongo URI) via env vars only.
- GZip middleware; `Cache-Control: public, max-age=86400` on immutable GET analysis/export responses.
- Client IP for rate limiting taken from the first `X-Forwarded-For` hop set by Render's proxy.

## 8. Frontend

Single page, controls left, results right; stacks on mobile.

| Component | Responsibility |
|---|---|
| `HazardSelect` | Heatwave default; other hazards shown disabled ("coming soon") |
| `RegionPicker` | Tabs: City (debounced search → dropdown), State (search → bbox), Draw box (drag rectangle on Leaflet map). Shared map shows marker or rectangle. Warns when box > 5°×5° |
| `YearRange` | Start/end dropdowns 1940…last complete year; default 1990–2020; warning if span < 10 years |
| `SummaryCards` | Avg heatwave days/yr, avg events/yr, longest event, trend badge (▲/▼ significant, or "no significant trend") |
| `InsightPanel` | Insight sentences + caveats |
| `MetricChart` | Chart.js bars per year + 5-yr rolling mean line + dashed trend line; metric toggle HWF/HWN/HWD/HWM/HWA; tooltips; low-quality years faded |
| `ThresholdChart` | 95th-percentile threshold by day of year |
| `EventsTable` | Sortable list of events |
| `ExportButtons` | CSV / PDF links |

**Behaviour:** TanStack Query for fetching/caching; selection mirrored in the URL query string (shareable); skeleton loading state with "first time for this region takes a few seconds"; error banners for 422/429/502/504 with retry; explicit empty state when no heatwaves occurred; all text rendered as plain React text (no `dangerouslySetInnerHTML`).

## 9. Testing
- **Heatwave logic (pytest, synthetic series):** 4 hot days → 1 event of 4 days; 2 hot + gap + 2 hot → 0 events; event crossing Dec 31 counted in start year; Feb 29 uses Feb 28 threshold; percentile window wraps around year ends.
- **Cleaning:** out-of-range values removed; 1–2-day gaps interpolated; 3-day gaps left missing; low-quality year flagging.
- **Trends:** Sen's slope and Mann-Kendall against hand-computed small examples; insufficient-years guard; % vs absolute change rule.
- **API (respx-mocked upstream, test Mongo DB):** cache miss then hit; 422 on bad input; 429 after limit; 502/504 on upstream failure; invalid upstream response not cached.
- **Frontend (Vitest):** URL-state encode/decode, number/insight formatting. Manual end-to-end check of the full flow.

## 10. Deployment
- Backend: Render free web service (Dockerfile or `uvicorn` start command); env vars `MONGO_URI`, `CORS_ORIGINS`, `NOMINATIM_USER_AGENT`. Free tier sleeps when idle (~30 s cold start) — documented in README.
- Frontend: Vercel; env var `VITE_API_BASE_URL`.
- DB: Atlas M0; network access open to Render egress (0.0.0.0/0 with strong credentials, documented as a free-tier trade-off).
- `scripts/seed.py` pre-warms 4–5 demo cities (e.g. Delhi, Phoenix, Paris, Sydney, Lagos).
- Local dev: `docker compose up` for MongoDB; backend `uvicorn`; frontend `npm run dev`.

## 11. Assumptions (to be repeated in README)
- ERA5 reanalysis (via Open-Meteo) is an acceptable stand-in for observed station data; it is gap-free and globally consistent but smooths local extremes.
- Heatwave definition follows the brief (≥3 consecutive days above the 95th percentile) using a calendar-day percentile with a ±7-day window over 1961–1990.
- Regional (box/state) analysis uses the area-average of up to 9 grid points.
- "Last complete year" = the previous calendar year (2025 as of this spec).
- Single backend instance; in-memory rate limiting and per-key locks are sufficient at this scale.

## 12. Future work (README "with more time")
- Heavy rainfall and drought hazards using stored `precip`.
- NOAA station data as a second source, with comparison against ERA5.
- Redis-backed rate limiting and a job queue for multi-instance deployments.
- Per-grid-point heatwave maps (choropleth) instead of area-average only.
- Configurable percentile/duration/baseline in the UI.
