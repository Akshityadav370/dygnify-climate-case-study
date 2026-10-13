# Climate Hazard Trend Analyzer — Heatwaves

Pick a city, a state or a lat-lon box and a year range. The app downloads daily maximum temperatures,
detects heatwaves using a percentile rule, tests whether they are really increasing, and shows the result
as charts, a table of events and plain-language insights.

- **Live app:** https://dygnify-climate-case-study.vercel.app · **API docs:** https://dygnify-climate-case-study.vercel.app/docs

## Architecture

```
React + TS ──/api/*──► FastAPI   ──► Open-Meteo (primary) / NASA POWER (fallback)
(one Vercel project, two services: frontend at /, backend at /api, /docs)
                                     │              Open-Meteo geocoding, Nominatim (states)
                                     ▼
                              MongoDB Atlas
                 weather_daily · analyses · geocode_cache
```

How `POST /api/analyze` works:
1. Validate the input.
2. Snap the region to the MERRA-2 grid (0.5° × 0.625°).
3. If this analysis is already cached, return it.
4. Otherwise, load each grid cell's 1981→present daily series from `weather_daily`. Cells that are missing are fetched from Open-Meteo, falling back to NASA POWER.
5. Clean the data and average the points.
6. Detect heatwaves, then compute trends and insights.
7. Store the result with a 30-day expiry.

| Folder | What lives there |
|---|---|
| `backend/app/core` | Cleaning and trend statistics (pure functions) |
| `backend/app/hazards` | Heatwave detection; registry for future hazards |
| `backend/app/clients` | External APIs: retries, timeouts, validation |
| `backend/app/services` | Region resolution, cache/ingest, orchestration, insights, geocoding, export |
| `backend/app/api` | HTTP routes |
| `frontend/src` | React app (Leaflet map, Chart.js charts, TanStack Query) |

## Data sources

| Source | Use |
|---|---|
| [Open-Meteo Historical](https://open-meteo.com/en/docs/historical-weather-api) (ERA5) | Primary: `temperature_2m_max` (°C) and `precipitation_sum` (mm), no key |
| [NASA POWER](https://power.larc.nasa.gov/docs/services/api/) daily point API (MERRA-2) | Fallback for each grid cell: `T2M_MAX` (°C) and `PRECTOTCORR` (mm/day), 1981→present, no key |
| [Open-Meteo Geocoding](https://open-meteo.com/en/docs/geocoding-api) | City search |
| [Nominatim](https://nominatim.org/release-docs/latest/api/Search/) | State bounding boxes (1 request/s, cached 7 days) |

**Why there is a fallback:** Open-Meteo's free tier counts every ~2 weeks of data as one API call
(600 per minute, 5,000 per hour, 10,000 per day). One location's 45-year history costs about 1,170 calls,
which is more than the per-minute limit. In practice Open-Meteo can serve roughly one new grid cell per
minute and a few per hour. When it refuses or fails, that cell is fetched from NASA POWER instead (about
2 s for 45 years, no published quota), and the results say so. Each cell is downloaded only once and then
served from MongoDB.

## Heatwave logic

1. **Cleaning**
   - Open-Meteo `null`s and POWER's `-999` fill values become missing values.
   - Values outside −90…60 °C are removed, and units are checked.
   - Gaps of up to 2 days are filled by linear interpolation. Longer gaps stay missing and break heatwave runs.
   - Years with more than 10% missing days are flagged as low quality and excluded from trends.
2. **Threshold** — for each calendar day, the 95th percentile of daily maximum temperature over
   1981–2010, using a ±7-day window. Feb 29 uses Feb 28's threshold.
3. **Event** — 3 or more consecutive days above that day's threshold. An event is counted in the year it starts.
4. **Yearly metrics**
   - HWN: number of events.
   - HWF: number of heatwave days.
   - HWD: length of the longest event.
   - HWM: mean °C above the threshold.
   - HWA: peak temperature.
5. **Trends**
   - Sen's slope measures how big the trend is, and is robust to outlier years.
   - The Mann-Kendall test decides whether the trend is significant (p < 0.05).
   - An OLS line is drawn on the chart, along with a 5-year rolling mean.
   - At least 10 usable years are required.
   - % change is measured along the Sen line, not between two noisy single years. It is only used when the starting value is at least 1; °C metrics report an absolute change instead.
6. **Insights** — sentences are generated from fixed rules. A trend is only described as an increase or
   decrease when it is statistically significant.

## API

| Method | Route | Limit / IP |
|---|---|---|
| GET | `/api/health` | — |
| GET | `/api/hazards` | 60/min |
| GET | `/api/geocode?q=&kind=city\|state` | 30/min |
| POST | `/api/analyze` | 10/min |
| GET | `/api/analyses/{id}` | 60/min |
| GET | `/api/analyses/{id}/export.csv`, `/report.pdf` | 10/min |

Errors always have the shape `{"error": {"code", "message"}}`:
- 422 for invalid input
- 404 for an unknown analysis
- 429 when rate limited, with a `Retry-After` header
- 502/504 when the upstream provider fails or times out

## Security & performance

- **Input validation:** every input is checked with Pydantic — coordinate ranges, box ≤ 5° × 5°, year range, hazard from a fixed list, and no extra fields.
- **Database safety:** lookups use SHA-256 ids computed by the server, never query objects supplied by the user.
- **External APIs:**
  - Fixed upstream hosts, with parameters URL-encoded by httpx.
  - Timeouts, a bounded number of retries, and at most 3 concurrent fetches.
  - Nominatim is throttled to 1 request/s.
  - Responses are validated (units, dates, coordinates) before anything is cached.
- **Rate limiting:** per IP with slowapi. The client IP is taken from the `X-Forwarded-For` entry added by the trusted proxy, so a spoofed header doesn't help.
- **HTTP:** in production the frontend and API share one domain, so no cross-origin access is needed; CORS stays restricted to configured origins (local dev). Responses are GZip-compressed; GET responses that never change get `Cache-Control` headers.
- **Two cache layers:** raw weather per grid cell (shared across regions and year ranges) and computed analyses (with an expiry).

## Local setup

Requirements: Docker, Python 3.12 with [uv](https://docs.astral.sh/uv/), and Node 20.19+.

```bash
docker compose up -d mongo
cd backend && cp .env.example .env && uv sync && uv run uvicorn app.main:app --reload --port 8000
cd frontend && cp .env.example .env && npm install && npm run dev     # http://localhost:5173
```

- **Tests:** `cd backend && uv run pytest` (needs the Mongo container) and `cd frontend && npm test`.
- **Pre-warm demo cities:** `cd backend && uv run python -m scripts.seed --api http://localhost:8000`.

## Deployment

1. **MongoDB Atlas** (free M0 tier):
   - Create a cluster and a database user.
   - Allow access from anywhere (`0.0.0.0/0`), because Vercel Functions have no fixed outbound IP on the free plan.
   - Copy the connection string.
2. **Vercel** (one project, two [services](https://vercel.com/docs/services) defined in `vercel.json`):
   - Import this repo with the **Root Directory left at the repository root**, so Vercel reads `vercel.json`.
   - `frontend` (Vite) serves `/`; `backend` (FastAPI, `app/main.py`) serves `/api/*`, `/docs` and `/openapi.json`.
     The browser calls `/api` on the same domain, so no API URL or CORS setting is needed.
   - Environment variables: `MONGO_URI`, `NOMINATIM_USER_AGENT=climate-hazard-analyzer/1.0 (<contact>)` and
     `TRUSTED_PROXY_HOPS=1` (use the client IP from Vercel's `X-Forwarded-For` for rate limiting).
     Do **not** set `VITE_API_BASE_URL`.
3. Run the seed script against the deployment so the demo cities load instantly:
   `uv run python -m scripts.seed --api https://<your-app>.vercel.app`.

The backend also has a `Dockerfile` for running it as a container elsewhere.

## Assumptions

- **Data:** reanalysis data (ERA5 via Open-Meteo, with MERRA-2 via NASA POWER as fallback) stands in for
  weather-station observations. It is consistent worldwide but smooths local extremes. Analysis starts in
  1981 so both sources cover the full range and the 1981–2010 baseline. A box can mix cells from both
  sources; the results add a caveat when the fallback was used.
- **Baseline:** 1981–2010 (a WMO 30-year normal), fixed regardless of the selected years.
- **Heatwaves can happen in any season.** The threshold is computed separately for each calendar day, so a
  heatwave means "unusually hot for this time of year". For example, in Delhi several detected events are
  winter warm spells (February, December–January), while summer events need temperatures above ~45 °C.
  This follows the brief's definition and common climate indices; a warm-season-only option would be an
  easy extension.
- **Regions:** box and state results are averaged over up to 9 grid points. States larger than 5° × 5° are
  clipped to a 5° × 5° box around their centre, and the UI says so.
- **Year range:** the last selectable year is the last complete calendar year.
- **Scale:** rate limits and per-key locks live in memory. On Vercel each function instance keeps its own
  counters, so under heavy load the limits are per instance rather than global. Fine for a demo; a shared
  store (Redis) would make them global.

## What I'd improve with more time

- Heavy-rainfall and drought hazards (precipitation is already stored).
- An option to count only warm-season heatwaves.
- NOAA GHCN station data as a comparison source, and pre-1981 history via Copernicus CDS.
- Maps of heatwaves per grid cell, instead of only area averages.
- Redis-backed rate limiting and a job queue for running multiple backend instances.
- User-configurable percentile, duration and baseline.
- Playwright end-to-end tests for the frontend.

## AI tools used

- **Claude Code (Claude Opus 5.5)** was used to:
  - Explain the climate-statistics concepts: percentile thresholds, Sen's slope, Mann-Kendall and interpolation.
  - Compare data sources. It measured Open-Meteo's quota cost and NASA POWER's speed with live requests, which shaped the fallback design.
  - Write the design spec and the implementation plan.
  - Generate code and tests task by task, and run browser checks of the UI.

  I reviewed every step, chose the architecture and trade-offs, and ran and verified the tests and the app.
