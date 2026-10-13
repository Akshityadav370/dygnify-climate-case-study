# Heatwave Trend Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A deployed web app that fetches daily max temperatures for a city, state or lat-lon box, detects percentile-based heatwaves, computes statistically honest trends, stores everything in MongoDB and visualizes it in React.

**Architecture:** FastAPI backend computes analyses on demand and caches raw weather (per MERRA-2 grid cell) and results (per region+years+algo version) in MongoDB. NASA POWER is the primary data source with per-point Open-Meteo fallback. React + TypeScript frontend (Vite) with Leaflet region selection and Chart.js charts calls the JSON API.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pydantic-settings, httpx, pandas, numpy, scipy, matplotlib, slowapi, PyMongo async (`AsyncMongoClient`), pytest, pytest-asyncio, respx, uv · React 19 + TypeScript + Vite, TanStack Query, Chart.js + react-chartjs-2, Leaflet + react-leaflet, Vitest · MongoDB (Docker locally, Atlas M0 in prod) · Render (backend) + Vercel (frontend).

**Spec:** `docs/superpowers/specs/2026-10-13-heatwave-analyzer-design.md`

## Global Constraints

- Commit messages: plain conventional-commit style, **no `Co-Authored-By` or any Claude attribution lines**.
- Data range: `DATA_START_YEAR = 1981`; last selectable year = previous calendar year (`date.today().year - 1`).
- Baseline 1981–2010, percentile 95, ±7-day window, min 3 consecutive days, events counted in start year.
- Grid: MERRA-2 0.5° lat × 0.625° lon; boxes ≤ 5° × 5°, sampled with up to 3×3 points.
- Physical bounds: tmax < −90 °C or > 60 °C → missing; interpolate only gaps of ≤ 2 days; year with > 10% missing → `low_quality`.
- Trend: Sen's slope (per decade), Mann-Kendall p < 0.05 → significant, ≥ 10 usable years, % change only for count/day metrics with start value ≥ 1 (°C metrics HWM/HWA always absolute change).
- Error body always `{"error": {"code": ..., "message": ...}}`; no stack traces to clients.
- Rate limits per IP: `/analyze` 10/min, `/geocode` 30/min, exports 10/min, other reads 60/min.
- Upstream: fixed base URLs, 10 s connect / 30 s read timeout, 2 retries with exponential backoff on 429/5xx/transport errors only, max 3 concurrent provider fetches, Nominatim ≤ 1 req/s.
- Algorithm version string `"v1"` is part of the analysis cache key.
- Frontend renders all server/user text as plain React text (no `dangerouslySetInnerHTML`).
- Deviations from spec, decided while planning: PyMongo's `AsyncMongoClient` instead of Motor (deprecated); `weather_daily` stores `sources: list[str]` (a cell can be extended by a different provider) instead of a single `source`; hazards are registered in `app/hazards/__init__.py` (`ANALYZERS` dict) rather than a separate `base.py`; HWM/HWA (°C metrics) always report absolute change.

## Review Focus

1. **Stale cached weather** — a `weather_daily` doc ending before the last complete year must fetch only the missing tail and append it (test in Task 8).
2. **Long provider outage inside a year** (e.g. 40 consecutive `-999` days in 2015) — that year is flagged `low_quality`, still listed in `yearly`, excluded from trends, and no crash (test in Task 8).
3. **A region/range with zero heatwaves** — yearly zeros with `HWM`/`HWA` null, a "No heatwaves" insight and no trend claims (tests in Tasks 3 and 5; frontend empty state in Task 15).
4. **Single-year or very short range** (`start_year == end_year`) — trends return `insufficient_years`, insight says so, response is 200 (test in Task 8).
5. **Provider returns HTTP 200 with an error body** (Open-Meteo `{"error": true, "reason": ...}`) — treated as upstream failure, not cached (test in Task 7).

---

## File Structure

```
.gitignore
docker-compose.yml                     # local MongoDB
render.yaml                            # Render blueprint (backend)
README.md
backend/
  pyproject.toml, uv.lock, Dockerfile, .dockerignore, .env.example
  app/
    __init__.py
    config.py          # Settings, DATA_START_YEAR, last_complete_year()
    errors.py          # AppError hierarchy + exception handlers
    db.py              # AsyncMongoClient factory + indexes
    deps.py            # FastAPI dependencies (db, upstream)
    locks.py           # KeyedLocks (per-key asyncio locks)
    ratelimit.py       # slowapi limiter, client_ip key, limit constants
    models.py          # request/response Pydantic models
    main.py            # create_app(), middleware, routers, lifespan
    core/
      __init__.py
      series.py        # DailySeries dataclass
      cleaning.py      # bounds, area-average, gap fill, low-quality years
      trends.py        # Mann-Kendall, Sen, OLS, rolling mean, analyze_trend
    hazards/
      __init__.py      # ANALYZERS registry
      heatwave.py      # thresholds, events, yearly metrics
    clients/
      __init__.py
      http.py          # UpstreamClient: retries, timeouts, throttles
      power.py         # NASA POWER fetch + parse
      openmeteo.py     # Open-Meteo archive fetch + parse, city geocoding
      nominatim.py     # state search
    services/
      __init__.py
      region.py        # grid snapping, sampling, cache keys
      insights.py      # rule-based sentences + caveats
      ingest.py        # weather_daily cache + provider fallback
      analysis.py      # orchestration, response shaping, chart block
      geocode.py       # geocode cache + state box clipping
      export.py        # CSV + PDF
    api/
      __init__.py
      meta.py          # /health, /hazards
      analyze.py       # /analyze, /analyses/{id}, exports
      geocode.py       # /geocode
  scripts/
    __init__.py
    seed.py
  tests/
    __init__.py, conftest.py, fakes.py
    test_health.py, test_cleaning.py, test_heatwave.py, test_trends.py,
    test_insights.py, test_region.py, test_clients.py, test_api_analyze.py,
    test_api_geocode.py, test_security.py, test_export.py
frontend/                              # Vite react-ts scaffold, plus:
  src/
    main.tsx, App.tsx, index.css
    api/types.ts, api/client.ts
    lib/urlState.ts, lib/format.ts, lib/region.ts, lib/useDebouncedValue.ts
    lib/*.test.ts
    charts/setup.ts
    components/HazardSelect.tsx, YearRange.tsx, PlaceSearch.tsx, BoxInputs.tsx,
      RegionMap.tsx, RegionPicker.tsx, SummaryCards.tsx, InsightPanel.tsx,
      MetricChart.tsx, ThresholdChart.tsx, EventsTable.tsx, ExportButtons.tsx,
      ErrorBanner.tsx, LoadingSkeleton.tsx, Results.tsx
```

---

### Task 1: Backend scaffold, config, errors, DB, health endpoint

**Files:**
- Create: `.gitignore`, `docker-compose.yml`, `backend/pyproject.toml` (via uv), `backend/.env.example`
- Create: `backend/app/__init__.py`, `config.py`, `errors.py`, `db.py`, `deps.py`, `locks.py`, `ratelimit.py`, `main.py`, `api/__init__.py`, `api/meta.py`, `core/__init__.py`, `hazards/__init__.py` (empty for now), `clients/__init__.py`, `clients/http.py`, `services/__init__.py`
- Test: `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`

**Interfaces:**
- Produces: `Settings` (fields below), `get_settings()`, `DATA_START_YEAR`, `last_complete_year() -> int`; `AppError`, `NotFoundError`, `BadRequestError`, `UpstreamError`, `UpstreamTimeout(UpstreamError)`, `install_error_handlers(app)`; `create_mongo_client(settings)`, `ensure_indexes(db)`; `get_db(request)`, `get_upstream(request)`; `KeyedLocks.get(key) -> asyncio.Lock`; `limiter`, `client_ip(request)`, `ANALYZE_LIMIT`, `GEOCODE_LIMIT`, `EXPORT_LIMIT`, `READ_LIMIT`; `UpstreamClient(settings)` with `get_json(url, params)`, `concurrency` (Semaphore), `nominatim_slot()` (async ctx manager), `aclose()`; `create_app(settings=None) -> FastAPI` with `app.state.settings/db/upstream/locks`.

- [ ] **Step 1: Root files and Python project**

`.gitignore`:
```gitignore
__pycache__/
*.pyc
.venv/
.env
.pytest_cache/
node_modules/
dist/
.DS_Store
```

`docker-compose.yml`:
```yaml
services:
  mongo:
    image: mongo:7
    ports:
      - "27017:27017"
    volumes:
      - mongo-data:/data/db
volumes:
  mongo-data:
```

Run:
```bash
cd /home/akshit/prudent-assignment && docker compose up -d mongo
mkdir -p backend && cd backend
uv init --app --no-readme --python 3.12 --name climate-hazard-api . && rm -f main.py hello.py
uv add fastapi "uvicorn[standard]" pydantic-settings httpx pandas numpy scipy matplotlib slowapi pymongo
uv add --dev pytest pytest-asyncio respx
```
Then append to `backend/pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

`backend/.env.example`:
```dotenv
MONGO_URI=mongodb://localhost:27017
MONGO_DB=climate_hazards
CORS_ORIGINS=["http://localhost:5173"]
NOMINATIM_USER_AGENT=climate-hazard-analyzer/0.1 (contact: you@example.com)
TRUSTED_PROXY_HOPS=0
```

- [ ] **Step 2: Write the failing health test**

`backend/tests/__init__.py`: empty.

`backend/tests/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.config import Settings
from app.main import create_app
from app.ratelimit import limiter

TEST_DB = "climate_hazards_test"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        mongo_db=TEST_DB,
        http_backoff_seconds=0,
        http_retries=1,
        cors_origins=["http://allowed.test"],
    )


@pytest.fixture
def mongo(settings):
    client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=2000)
    client.drop_database(TEST_DB)
    yield client[TEST_DB]
    client.drop_database(TEST_DB)
    client.close()


@pytest.fixture
def client(settings, mongo):
    limiter.reset()
    with TestClient(create_app(settings)) as test_client:
        yield test_client
```

`backend/tests/test_health.py`:
```python
def test_health_reports_db_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_unknown_route_is_404(client):
    assert client.get("/api/nope").status_code == 404
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_health.py -v`
Expected: FAIL / collection error — `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 4: Implement the scaffold**

`backend/app/__init__.py`, `app/api/__init__.py`, `app/core/__init__.py`, `app/clients/__init__.py`, `app/services/__init__.py`: empty files.

`backend/app/hazards/__init__.py`: empty for now (Task 3 fills it).

`backend/app/config.py`:
```python
from datetime import date
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# NASA POWER daily data starts on 1981-01-01.
DATA_START_YEAR = 1981


def last_complete_year() -> int:
    """The most recent calendar year with a full year of data."""
    return date.today().year - 1


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "climate_hazards"
    cors_origins: list[str] = ["http://localhost:5173"]
    nominatim_user_agent: str = "climate-hazard-analyzer/0.1 (set NOMINATIM_USER_AGENT)"

    http_connect_timeout: float = 10.0
    http_read_timeout: float = 30.0
    http_retries: int = 2
    http_backoff_seconds: float = 0.5
    upstream_concurrency: int = 3

    # Number of reverse proxies in front of the app that append to X-Forwarded-For
    # (Render: 1). 0 means use the socket peer address.
    trusted_proxy_hops: int = 0

    analysis_ttl_days: int = 30
    geocode_ttl_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`backend/app/errors.py`:
```python
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class BadRequestError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"


class UpstreamError(AppError):
    status_code = 502
    code = "UPSTREAM_ERROR"


class UpstreamTimeout(UpstreamError):
    status_code = 504
    code = "UPSTREAM_TIMEOUT"


def error_body(code: str, message: str, **extra) -> dict:
    return {"error": {"code": code, "message": message, **extra}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        details = [{"loc": [str(part) for part in err["loc"]], "msg": err["msg"]} for err in exc.errors()]
        return JSONResponse(
            status_code=422,
            content=error_body("VALIDATION_ERROR", "Invalid request parameters.", details=details),
        )

    @app.exception_handler(RateLimitExceeded)
    async def handle_rate_limit(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content=error_body(
                "RATE_LIMITED",
                f"Too many requests (limit: {exc.detail}). Please wait a minute and try again.",
            ),
            headers={"Retry-After": "60"},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s", request.url.path)
        return JSONResponse(status_code=500, content=error_body("INTERNAL_ERROR", "Something went wrong on our side."))
```

`backend/app/db.py`:
```python
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.config import Settings


def create_mongo_client(settings: Settings) -> AsyncMongoClient:
    return AsyncMongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000, tz_aware=True)


async def ensure_indexes(db: AsyncDatabase) -> None:
    # TTL indexes: MongoDB deletes documents once `expires_at` is in the past.
    await db.analyses.create_index("expires_at", expireAfterSeconds=0)
    await db.geocode_cache.create_index("expires_at", expireAfterSeconds=0)
```

`backend/app/locks.py`:
```python
import asyncio
import weakref


class KeyedLocks:
    """One asyncio.Lock per key, so concurrent requests for the same key run once.

    Locks are held weakly: once no coroutine references a lock it is dropped.
    """

    def __init__(self) -> None:
        self._locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()

    def get(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock
```

`backend/app/ratelimit.py`:
```python
from slowapi import Limiter
from starlette.requests import Request

ANALYZE_LIMIT = "10/minute"
GEOCODE_LIMIT = "30/minute"
EXPORT_LIMIT = "10/minute"
READ_LIMIT = "60/minute"


def client_ip(request: Request) -> str:
    """Client IP used as the rate-limit key.

    Each trusted proxy appends the address it received the request from to
    X-Forwarded-For, so with N trusted proxies the N-th entry from the right is
    the real client. Entries further left are client-controlled and ignored.
    """
    hops = request.app.state.settings.trusted_proxy_hops
    if hops > 0:
        forwarded = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",") if part.strip()]
        if len(forwarded) >= hops:
            return forwarded[-hops]
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=client_ip, headers_enabled=False)
```

`backend/app/clients/http.py`:
```python
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import Settings
from app.errors import UpstreamError, UpstreamTimeout

logger = logging.getLogger(__name__)

NOMINATIM_MIN_INTERVAL_SECONDS = 1.0


class UpstreamClient:
    """Shared HTTP client for all external APIs: timeouts, retries, throttles."""

    def __init__(self, settings: Settings):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.http_read_timeout, connect=settings.http_connect_timeout),
            headers={"User-Agent": settings.nominatim_user_agent},
            follow_redirects=False,
        )
        self._retries = settings.http_retries
        self._backoff = settings.http_backoff_seconds
        self.concurrency = asyncio.Semaphore(settings.upstream_concurrency)
        self._nominatim_lock = asyncio.Lock()
        self._nominatim_last = 0.0

    async def get_json(self, url: str, params: dict[str, Any]) -> Any:
        host = urlparse(url).hostname
        last_error: UpstreamError = UpstreamError("Weather data provider is unavailable.")
        for attempt in range(self._retries + 1):
            try:
                response = await self._client.get(url, params=params)
            except httpx.TimeoutException:
                logger.warning("Timeout calling %s (attempt %d)", host, attempt + 1)
                last_error = UpstreamTimeout("Weather data provider did not respond in time. Try again shortly.")
            except httpx.TransportError as exc:
                logger.warning("Transport error calling %s: %s", host, exc)
                last_error = UpstreamError("Could not reach the weather data provider.")
            else:
                if response.status_code == 200:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise UpstreamError("Weather data provider returned invalid JSON.") from exc
                logger.warning("%s returned HTTP %d", host, response.status_code)
                if response.status_code != 429 and response.status_code < 500:
                    raise UpstreamError("Weather data provider rejected the request.")
                last_error = UpstreamError("Weather data provider returned an error.")
            if attempt < self._retries:
                await asyncio.sleep(self._backoff * 2**attempt)
        raise last_error

    @asynccontextmanager
    async def nominatim_slot(self):
        """Serialize Nominatim calls and keep them at least 1 s apart (usage policy)."""
        async with self._nominatim_lock:
            wait = self._nominatim_last + NOMINATIM_MIN_INTERVAL_SECONDS - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                yield
            finally:
                self._nominatim_last = time.monotonic()

    async def aclose(self) -> None:
        await self._client.aclose()
```

`backend/app/deps.py`:
```python
from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase

from app.clients.http import UpstreamClient


def get_db(request: Request) -> AsyncDatabase:
    return request.app.state.db


def get_upstream(request: Request) -> UpstreamClient:
    return request.app.state.upstream
```

`backend/app/api/meta.py`:
```python
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.deps import get_db

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health(db=Depends(get_db)):
    try:
        await db.command("ping")
    except Exception:
        return JSONResponse(status_code=503, content={"status": "degraded", "db": "unreachable"})
    return {"status": "ok", "db": "ok"}
```

`backend/app/main.py`:
```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api import meta
from app.clients.http import UpstreamClient
from app.config import Settings, get_settings
from app.db import create_mongo_client, ensure_indexes
from app.errors import install_error_handlers
from app.locks import KeyedLocks
from app.ratelimit import limiter

logging.basicConfig(level=logging.INFO)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        mongo = create_mongo_client(settings)
        app.state.db = mongo[settings.mongo_db]
        app.state.upstream = UpstreamClient(settings)
        app.state.locks = KeyedLocks()
        await ensure_indexes(app.state.db)
        yield
        await app.state.upstream.aclose()
        await mongo.close()

    app = FastAPI(title="Climate Hazard Trend Analyzer API", version="1.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.limiter = limiter
    install_error_handlers(app)

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    app.include_router(meta.router, prefix="/api")
    return app


app = create_app()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_health.py -v`
Expected: 2 passed (MongoDB container from Step 1 must be running).

- [ ] **Step 6: Commit**

```bash
git add .gitignore docker-compose.yml backend
git commit -m "feat(backend): scaffold FastAPI app with config, errors, MongoDB and health check"
```

---

### Task 2: Data cleaning (bounds, area-average, gap fill, low-quality years)

**Files:**
- Create: `backend/app/core/series.py`, `backend/app/core/cleaning.py`
- Test: `backend/tests/test_cleaning.py`

**Interfaces:**
- Produces: `DailySeries(start: date, tmax: list[float|None], precip: list[float|None], sources: list[str])` with property `end: date`; `to_daily_series(start: date, values: Sequence[float|None]) -> pd.Series`; `CleanResult(tmax: pd.Series, removed: int, interpolated: int)`; `clean_tmax(points: Sequence[pd.Series], max_gap_days: int = 2) -> CleanResult`; `fill_short_gaps(s, max_gap_days) -> tuple[pd.Series, int]`; `low_quality_years(s: pd.Series, years: Iterable[int], max_missing_fraction: float = 0.10) -> list[int]`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_cleaning.py`:
```python
from datetime import date

import numpy as np
import pandas as pd

from app.core.cleaning import clean_tmax, low_quality_years, to_daily_series
from app.core.series import DailySeries


def values(series: pd.Series) -> list:
    return [None if np.isnan(v) else round(float(v), 4) for v in series]


def test_daily_series_end_date():
    s = DailySeries(start=date(2020, 2, 27), tmax=[1.0, 2.0, 3.0], precip=[0, 0, 0], sources=["nasa-power"])
    assert s.end == date(2020, 2, 29)


def test_to_daily_series_converts_none_to_nan_with_daily_index():
    s = to_daily_series(date(2020, 1, 1), [1.0, None, 3.0])
    assert list(s.index.strftime("%Y-%m-%d")) == ["2020-01-01", "2020-01-02", "2020-01-03"]
    assert values(s) == [1.0, None, 3.0]


def test_out_of_range_values_are_removed_then_short_gap_interpolated():
    result = clean_tmax([to_daily_series(date(2020, 1, 1), [30.0, 75.0, 32.0])])
    assert result.removed == 1
    assert result.interpolated == 1
    assert values(result.tmax) == [30.0, 31.0, 32.0]


def test_two_day_gap_is_interpolated():
    result = clean_tmax([to_daily_series(date(2020, 1, 1), [30.0, None, None, 33.0])])
    assert values(result.tmax) == [30.0, 31.0, 32.0, 33.0]
    assert result.interpolated == 2


def test_three_day_gap_is_left_missing():
    result = clean_tmax([to_daily_series(date(2020, 1, 1), [30.0, None, None, None, 34.0])])
    assert values(result.tmax) == [30.0, None, None, None, 34.0]
    assert result.interpolated == 0


def test_leading_gap_is_not_extrapolated():
    result = clean_tmax([to_daily_series(date(2020, 1, 1), [None, 30.0, 31.0])])
    assert values(result.tmax) == [None, 30.0, 31.0]


def test_multiple_points_are_area_averaged_ignoring_missing():
    a = to_daily_series(date(2020, 1, 1), [30.0, 40.0])
    b = to_daily_series(date(2020, 1, 1), [32.0, None])
    assert values(clean_tmax([a, b]).tmax) == [31.0, 40.0]


def test_low_quality_years_flags_more_than_ten_percent_missing():
    raw = [20.0] * (365 * 2)
    for i in range(40):  # 2001: 40 missing days (11%)
        raw[100 + i] = None
    for i in range(30):  # 2002: 30 missing days (8%)
        raw[365 + 100 + i] = None
    s = to_daily_series(date(2001, 1, 1), raw)
    assert low_quality_years(s, range(2001, 2003)) == [2001]


def test_year_absent_from_series_counts_as_low_quality():
    s = to_daily_series(date(2001, 1, 1), [20.0] * 365)
    assert low_quality_years(s, [2001, 2002]) == [2002]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_cleaning.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.cleaning'`.

- [ ] **Step 3: Implement**

`backend/app/core/series.py`:
```python
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class DailySeries:
    """Daily values starting at `start`; list index = day offset. None = missing."""

    start: date
    tmax: list[float | None]
    precip: list[float | None]
    sources: list[str]

    @property
    def end(self) -> date:
        return self.start + timedelta(days=len(self.tmax) - 1)
```

`backend/app/core/cleaning.py`:
```python
import calendar
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

# Values outside this range are physically impossible for 2 m air temperature.
TMAX_MIN_C = -90.0
TMAX_MAX_C = 60.0


@dataclass
class CleanResult:
    tmax: pd.Series  # daily DatetimeIndex, NaN = missing
    removed: int  # values dropped as physically impossible
    interpolated: int  # missing days filled by interpolation


def to_daily_series(start: date, values: Sequence[float | None]) -> pd.Series:
    index = pd.date_range(start=start, periods=len(values), freq="D")
    return pd.Series([np.nan if v is None else float(v) for v in values], index=index, dtype="float64")


def fill_short_gaps(s: pd.Series, max_gap_days: int) -> tuple[pd.Series, int]:
    """Linearly interpolate runs of missing days no longer than `max_gap_days`.

    Longer gaps stay missing (we never invent long stretches of weather), and
    gaps at the very start or end are not extrapolated.
    """
    missing = s.isna()
    if not missing.any():
        return s, 0
    run_id = missing.ne(missing.shift(fill_value=False)).cumsum()
    run_length = missing.groupby(run_id).transform("size")
    fillable = missing & (run_length <= max_gap_days)
    interpolated = s.interpolate(method="linear", limit_area="inside")
    out = s.where(~fillable, interpolated)
    return out, int((fillable & out.notna()).sum())


def clean_tmax(points: Sequence[pd.Series], max_gap_days: int = 2) -> CleanResult:
    """Remove impossible values per point, area-average the points, fill short gaps."""
    removed = 0
    bounded = []
    for s in points:
        bad = (s < TMAX_MIN_C) | (s > TMAX_MAX_C)
        removed += int(bad.sum())
        bounded.append(s.mask(bad))
    regional = pd.concat(bounded, axis=1).mean(axis=1, skipna=True)
    filled, interpolated = fill_short_gaps(regional, max_gap_days)
    return CleanResult(tmax=filled, removed=removed, interpolated=interpolated)


def low_quality_years(s: pd.Series, years: Iterable[int], max_missing_fraction: float = 0.10) -> list[int]:
    """Years where more than `max_missing_fraction` of calendar days have no value."""
    flagged = []
    for year in years:
        expected = 366 if calendar.isleap(year) else 365
        present = int(s.loc[f"{year}-01-01":f"{year}-12-31"].notna().sum())
        if (expected - present) / expected > max_missing_fraction:
            flagged.append(year)
    return flagged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_cleaning.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core backend/tests/test_cleaning.py
git commit -m "feat(backend): add daily series cleaning with gap filling and quality flags"
```

---

### Task 3: Heatwave detection

**Files:**
- Create: `backend/app/hazards/heatwave.py`
- Modify: `backend/app/hazards/__init__.py`
- Test: `backend/tests/test_heatwave.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (operates on `pd.Series` with daily `DatetimeIndex`).
- Produces: `HeatwaveParams(percentile=95.0, window_days=7, min_days=3, baseline=(1981, 2010))`; `HeatwaveEvent(start: date, end: date, days: int, peak_tmax: float, mean_exceedance: float)` with `to_dict() -> dict` (ISO date strings); `METRIC_KEYS = ("HWN","HWF","HWD","HWM","HWA")`; `day_of_year_365(index) -> np.ndarray`; `compute_thresholds(tmax, params) -> np.ndarray` (shape 365, index = doy-1); `detect_events(tmax, thresholds, min_days) -> list[HeatwaveEvent]`; `yearly_metrics(events, years, low_quality: set[int]) -> list[dict]`; `HeatwaveResult(thresholds: list[float|None], events: list[HeatwaveEvent], yearly: list[dict])`; `analyze(tmax, years: range, low_quality: set[int], params=HeatwaveParams()) -> HeatwaveResult`; `ANALYZERS = {"heatwave": heatwave.analyze}` in `app/hazards/__init__.py`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_heatwave.py`:
```python
from datetime import date

import numpy as np
import pandas as pd

from app.hazards.heatwave import (
    HeatwaveEvent,
    HeatwaveParams,
    analyze,
    compute_thresholds,
    day_of_year_365,
    detect_events,
    yearly_metrics,
)

PARAMS = HeatwaveParams()


def make_series(start="1981-01-01", end="2012-12-31", value=30.0) -> pd.Series:
    index = pd.date_range(start, end, freq="D")
    return pd.Series(value, index=index, dtype="float64")


def test_day_of_year_maps_feb29_onto_feb28_and_keeps_march_aligned():
    index = pd.DatetimeIndex(["2000-02-28", "2000-02-29", "2000-03-01", "2001-03-01", "2000-12-31", "2001-12-31"])
    assert list(day_of_year_365(index)) == [59, 59, 60, 60, 365, 365]


def test_constant_series_gives_constant_thresholds():
    thresholds = compute_thresholds(make_series(), PARAMS)
    assert thresholds.shape == (365,)
    assert np.allclose(thresholds, 30.0)


def test_threshold_window_wraps_around_year_end():
    s = make_series(end="2010-12-31", value=10.0)
    s[(s.index.month == 12) & (s.index.day >= 25)] = 50.0
    thresholds = compute_thresholds(s, PARAMS)
    assert thresholds[0] == 50.0  # Jan 1 window includes Dec 25-31
    assert thresholds[179] == 10.0  # late June window is all 10s


def test_four_hot_days_make_one_event():
    s = make_series()
    s["2011-07-01":"2011-07-04"] = 40.0
    events = detect_events(s, compute_thresholds(s, PARAMS), min_days=3)
    assert events == [HeatwaveEvent(date(2011, 7, 1), date(2011, 7, 4), 4, 40.0, 10.0)]


def test_two_short_hot_spells_are_not_a_heatwave():
    s = make_series()
    s["2011-07-01":"2011-07-02"] = 40.0
    s["2011-07-04":"2011-07-05"] = 40.0
    assert detect_events(s, compute_thresholds(s, PARAMS), min_days=3) == []


def test_missing_day_breaks_a_hot_run():
    s = make_series()
    s["2011-07-01":"2011-07-05"] = 40.0
    s["2011-07-03"] = np.nan
    assert detect_events(s, compute_thresholds(s, PARAMS), min_days=3) == []


def test_event_crossing_new_year_counts_in_start_year():
    s = make_series()
    s["2011-12-30":"2012-01-02"] = 40.0
    result = analyze(s, range(2011, 2013), set(), PARAMS)
    assert [(e.start, e.days) for e in result.events] == [(date(2011, 12, 30), 4)]
    assert [(r["year"], r["HWN"], r["HWF"]) for r in result.yearly] == [(2011, 1, 4), (2012, 0, 0)]


def test_yearly_metrics_combine_events():
    events = [
        HeatwaveEvent(date(2011, 6, 1), date(2011, 6, 4), 4, 40.0, 1.0),
        HeatwaveEvent(date(2011, 7, 1), date(2011, 7, 4), 4, 42.0, 2.0),
    ]
    rows = yearly_metrics(events, range(2011, 2013), low_quality={2012})
    assert rows[0] == {"year": 2011, "HWN": 2, "HWF": 8, "HWD": 4, "HWM": 1.5, "HWA": 42.0, "low_quality": False}
    assert rows[1] == {"year": 2012, "HWN": 0, "HWF": 0, "HWD": 0, "HWM": None, "HWA": None, "low_quality": True}


def test_analyze_only_reports_events_inside_selected_years():
    s = make_series()
    s["2011-07-01":"2011-07-04"] = 40.0
    s["2012-07-01":"2012-07-04"] = 40.0
    result = analyze(s, range(2012, 2013), set(), PARAMS)
    assert [e.start.year for e in result.events] == [2012]
    assert len(result.thresholds) == 365


def test_event_to_dict_uses_iso_dates():
    event = HeatwaveEvent(date(2011, 7, 1), date(2011, 7, 4), 4, 40.0, 10.0)
    assert event.to_dict() == {
        "start": "2011-07-01", "end": "2011-07-04", "days": 4, "peak_tmax": 40.0, "mean_exceedance": 10.0,
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_heatwave.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.hazards.heatwave'`.

- [ ] **Step 3: Implement**

`backend/app/hazards/heatwave.py`:
```python
"""Heatwave detection.

Definition: a heatwave is >= `min_days` consecutive days whose daily maximum
temperature is above the `percentile` of that calendar day's baseline
climatology (baseline years, +/- `window_days` around the day).
"""

from dataclasses import asdict, dataclass
from datetime import date

import numpy as np
import pandas as pd

METRIC_KEYS = ("HWN", "HWF", "HWD", "HWM", "HWA")


@dataclass(frozen=True)
class HeatwaveParams:
    percentile: float = 95.0
    window_days: int = 7
    min_days: int = 3
    baseline: tuple[int, int] = (1981, 2010)


@dataclass
class HeatwaveEvent:
    start: date
    end: date
    days: int
    peak_tmax: float
    mean_exceedance: float  # mean degrees C above the threshold over the event

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start"] = self.start.isoformat()
        d["end"] = self.end.isoformat()
        return d


@dataclass
class HeatwaveResult:
    thresholds: list[float | None]  # 365 values, index = day-of-year - 1
    events: list[HeatwaveEvent]
    yearly: list[dict]


def day_of_year_365(index: pd.DatetimeIndex) -> np.ndarray:
    """Day of year on a 365-day calendar: Feb 29 shares Feb 28's slot (59)."""
    doy = index.dayofyear.to_numpy()
    shift = np.asarray(index.is_leap_year) & (doy >= 60)
    return np.where(shift, doy - 1, doy)


def compute_thresholds(tmax: pd.Series, params: HeatwaveParams) -> np.ndarray:
    start_year, end_year = params.baseline
    base = tmax.loc[f"{start_year}-01-01":f"{end_year}-12-31"]
    keys = day_of_year_365(base.index)
    values = base.to_numpy()
    thresholds = np.full(365, np.nan)
    for day in range(1, 366):
        distance = np.abs(keys - day)
        distance = np.minimum(distance, 365 - distance)  # circular: Dec 31 is next to Jan 1
        window = values[distance <= params.window_days]
        window = window[~np.isnan(window)]
        if window.size:
            thresholds[day - 1] = np.percentile(window, params.percentile)
    return thresholds


def detect_events(tmax: pd.Series, thresholds: np.ndarray, min_days: int) -> list[HeatwaveEvent]:
    threshold_per_day = thresholds[day_of_year_365(tmax.index) - 1]
    values = tmax.to_numpy()
    hot = values > threshold_per_day  # NaN compares False, so missing days break runs
    events: list[HeatwaveEvent] = []
    i, n = 0, len(values)
    while i < n:
        if not hot[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and hot[j + 1]:
            j += 1
        length = j - i + 1
        if length >= min_days:
            segment = values[i : j + 1]
            exceedance = segment - threshold_per_day[i : j + 1]
            events.append(
                HeatwaveEvent(
                    start=tmax.index[i].date(),
                    end=tmax.index[j].date(),
                    days=length,
                    peak_tmax=round(float(segment.max()), 2),
                    mean_exceedance=round(float(exceedance.mean()), 2),
                )
            )
        i = j + 1
    return events


def yearly_metrics(events: list[HeatwaveEvent], years: range, low_quality: set[int]) -> list[dict]:
    rows = []
    for year in years:
        year_events = [e for e in events if e.start.year == year]
        total_days = sum(e.days for e in year_events)
        rows.append(
            {
                "year": year,
                "HWN": len(year_events),
                "HWF": total_days,
                "HWD": max((e.days for e in year_events), default=0),
                "HWM": round(sum(e.mean_exceedance * e.days for e in year_events) / total_days, 2)
                if total_days
                else None,
                "HWA": max((e.peak_tmax for e in year_events), default=None),
                "low_quality": year in low_quality,
            }
        )
    return rows


def analyze(
    tmax: pd.Series, years: range, low_quality: set[int], params: HeatwaveParams = HeatwaveParams()
) -> HeatwaveResult:
    thresholds = compute_thresholds(tmax, params)
    # Detect over the full series so events crossing the range edges are complete,
    # then keep only events that start inside the selected years.
    events = [e for e in detect_events(tmax, thresholds, params.min_days) if e.start.year in years]
    return HeatwaveResult(
        thresholds=[None if np.isnan(t) else round(float(t), 2) for t in thresholds],
        events=events,
        yearly=yearly_metrics(events, years, low_quality),
    )
```

`backend/app/hazards/__init__.py`:
```python
"""Hazard registry. Each analyzer takes (tmax series, years, low-quality years)."""

from app.hazards import heatwave

ANALYZERS = {"heatwave": heatwave.analyze}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_heatwave.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/hazards backend/tests/test_heatwave.py
git commit -m "feat(backend): add percentile-based heatwave detection and yearly metrics"
```

---

### Task 4: Trend statistics (Mann-Kendall, Sen's slope, OLS, rolling mean)

**Files:**
- Create: `backend/app/core/trends.py`
- Test: `backend/tests/test_trends.py`

**Interfaces:**
- Produces: `MIN_YEARS = 10`, `SIGNIFICANCE_LEVEL = 0.05`; `mann_kendall(values) -> tuple[int, float]` (S, p); `sens_slope(x, y) -> tuple[float, float]` (slope, intercept); `ols(x, y) -> tuple[float, float]`; `rolling_mean(values: list[float|None], window=5) -> list[float|None]`; `Trend` dataclass with fields `n_years, sen_per_decade, mk_p, significant, ols_slope, ols_intercept, change_kind ("pct"|"abs"|None), change_value, reason` and `to_dict()`; `analyze_trend(years: list[int], values: list[float|None], excluded: set[int], start_year: int, end_year: int, allow_pct: bool = True) -> Trend`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_trends.py`:
```python
import pytest

from app.core.trends import analyze_trend, mann_kendall, ols, rolling_mean, sens_slope


def test_mann_kendall_on_strictly_increasing_series():
    s, p = mann_kendall([1, 2, 3, 4, 5])
    assert s == 10
    # var = 5*4*15/18 = 16.667; z = (10-1)/sqrt(var) = 2.2045; p = 2*(1-Phi(z))
    assert p == pytest.approx(0.0275, abs=1e-3)


def test_mann_kendall_all_ties_is_not_significant():
    assert mann_kendall([3, 3, 3, 3]) == (0, 1.0)


def test_sens_slope_ignores_an_outlier():
    slope, intercept = sens_slope([0, 1, 2, 3, 4], [0, 1, 2, 3, 100])
    assert slope == 1.0
    assert intercept == 0.0
    ols_slope, _ = ols([0, 1, 2, 3, 4], [0, 1, 2, 3, 100])
    assert ols_slope > 15  # least squares is pulled by the outlier


def test_rolling_mean_is_centred_with_partial_edges():
    assert rolling_mean([1, 2, 3, 4, 5]) == [2.0, 2.5, 3.0, 3.5, 4.0]
    assert rolling_mean([1, None, None, None, 5]) == [None, None, None, None, None]


def test_significant_increase_reports_percent_change():
    years = list(range(2001, 2021))
    trend = analyze_trend(years, [float(v) for v in range(1, 21)], set(), 2001, 2020)
    assert trend.significant is True
    assert trend.sen_per_decade == 10.0
    assert trend.change_kind == "pct"
    assert trend.change_value == 1900.0
    assert trend.reason is None


def test_small_start_value_reports_absolute_change():
    years = list(range(2001, 2021))
    trend = analyze_trend(years, [float(v) for v in range(0, 20)], set(), 2001, 2020)
    assert trend.change_kind == "abs"
    assert trend.change_value == 19.0


def test_pct_disabled_reports_absolute_change():
    years = list(range(2001, 2021))
    trend = analyze_trend(years, [float(v) for v in range(10, 30)], set(), 2001, 2020, allow_pct=False)
    assert trend.change_kind == "abs"


def test_too_few_usable_years_returns_reason():
    years = list(range(2001, 2021))
    values = [1.0] * 20
    values[0] = None
    trend = analyze_trend(years, values, excluded=set(range(2002, 2013)), start_year=2001, end_year=2020)
    assert trend.n_years == 8
    assert trend.reason == "insufficient_years"
    assert trend.sen_per_decade is None and trend.significant is False


def test_flat_noise_is_not_significant():
    years = list(range(2001, 2021))
    values = [5.0, 7.0, 4.0, 6.0, 5.0, 8.0, 3.0, 6.0, 5.0, 7.0, 4.0, 6.0, 5.0, 7.0, 4.0, 6.0, 6.0, 4.0, 5.0, 6.0]
    trend = analyze_trend(years, values, set(), 2001, 2020)
    assert trend.significant is False
    assert trend.mk_p > 0.05
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_trends.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.trends'`.

- [ ] **Step 3: Implement**

`backend/app/core/trends.py`:
```python
"""Trend statistics for yearly hazard metrics.

- Sen's slope: median of all pairwise slopes; robust to outlier years.
- Mann-Kendall: non-parametric test of whether values consistently rise or fall.
- OLS: ordinary least-squares line, used only for drawing the trend line.
"""

import math
from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy.stats import norm

MIN_YEARS = 10
SIGNIFICANCE_LEVEL = 0.05


@dataclass
class Trend:
    n_years: int
    sen_per_decade: float | None = None
    mk_p: float | None = None
    significant: bool = False
    ols_slope: float | None = None
    ols_intercept: float | None = None
    change_kind: Literal["pct", "abs"] | None = None
    change_value: float | None = None
    reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def mann_kendall(values) -> tuple[int, float]:
    y = np.asarray(values, dtype=float)
    n = len(y)
    s = 0
    for i in range(n - 1):
        s += int(np.sign(y[i + 1 :] - y[i]).sum())
    _, tie_counts = np.unique(y, return_counts=True)
    variance = (n * (n - 1) * (2 * n + 5) - sum(t * (t - 1) * (2 * t + 5) for t in tie_counts)) / 18
    if variance <= 0:
        return s, 1.0
    if s > 0:
        z = (s - 1) / math.sqrt(variance)
    elif s < 0:
        z = (s + 1) / math.sqrt(variance)
    else:
        z = 0.0
    return s, float(2 * (1 - norm.cdf(abs(z))))


def sens_slope(x, y) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    slopes = [
        (y[j] - y[i]) / (x[j] - x[i]) for i in range(len(x) - 1) for j in range(i + 1, len(x)) if x[j] != x[i]
    ]
    slope = float(np.median(slopes))
    intercept = float(np.median(y) - slope * np.median(x))
    return slope, intercept


def ols(x, y) -> tuple[float, float]:
    slope, intercept = np.polyfit(np.asarray(x, dtype=float), np.asarray(y, dtype=float), 1)
    return float(slope), float(intercept)


def rolling_mean(values: list[float | None], window: int = 5) -> list[float | None]:
    s = pd.Series([np.nan if v is None else v for v in values], dtype="float64")
    smoothed = s.rolling(window, center=True, min_periods=3).mean()
    return [None if pd.isna(v) else round(float(v), 2) for v in smoothed]


def analyze_trend(
    years: list[int],
    values: list[float | None],
    excluded: set[int],
    start_year: int,
    end_year: int,
    allow_pct: bool = True,
) -> Trend:
    pairs = [(year, v) for year, v in zip(years, values) if v is not None and year not in excluded]
    if len(pairs) < MIN_YEARS:
        return Trend(n_years=len(pairs), reason="insufficient_years")

    x = [p[0] for p in pairs]
    y = [p[1] for p in pairs]
    slope, intercept = sens_slope(x, y)
    _, p_value = mann_kendall(y)
    ols_slope, ols_intercept = ols(x, y)

    # Change along the Sen line, not between two noisy individual years.
    start_value = intercept + slope * start_year
    end_value = intercept + slope * end_year
    if allow_pct and start_value >= 1:
        change_kind, change_value = "pct", (end_value - start_value) / start_value * 100
    else:
        change_kind, change_value = "abs", end_value - start_value

    return Trend(
        n_years=len(pairs),
        sen_per_decade=round(slope * 10, 2),
        mk_p=round(p_value, 4),
        significant=p_value < SIGNIFICANCE_LEVEL,
        ols_slope=round(ols_slope, 4),
        ols_intercept=round(ols_intercept, 4),
        change_kind=change_kind,
        change_value=round(change_value, 1),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_trends.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/trends.py backend/tests/test_trends.py
git commit -m "feat(backend): add Mann-Kendall, Sen's slope and trend summary"
```

---

### Task 5: Rule-based insights and caveats

**Files:**
- Create: `backend/app/services/insights.py`
- Test: `backend/tests/test_insights.py`

**Interfaces:**
- Consumes: `MIN_YEARS` from `app.core.trends`; trend dicts shaped like `Trend.to_dict()`.
- Produces: `describe_trend(metric: str, trend: dict, label: str, start_year: int, end_year: int) -> str`; `build_insights(label: str, start_year: int, end_year: int, yearly: list[dict], trends: dict[str, dict], sources_used: list[str], n_points: int, low_quality_years: list[int]) -> tuple[list[str], list[str]]`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_insights.py`:
```python
from app.services.insights import build_insights, describe_trend


def trend(**overrides) -> dict:
    base = {
        "n_years": 30, "sen_per_decade": 4.2, "mk_p": 0.003, "significant": True, "ols_slope": 0.4,
        "ols_intercept": -800.0, "change_kind": "pct", "change_value": 120.0, "reason": None,
    }
    return base | overrides


def yearly_rows(hwf_values: list[int]) -> list[dict]:
    return [
        {"year": 1991 + i, "HWN": 1 if v else 0, "HWF": v, "HWD": v, "HWM": 1.0 if v else None,
         "HWA": 44.0 if v else None, "low_quality": False}
        for i, v in enumerate(hwf_values)
    ]


def test_significant_increase_sentence():
    text = describe_trend("HWF", trend(), "Delhi, India", 1991, 2020)
    assert text == (
        "Heatwave days in Delhi, India increased by about 120% between 1991 and 2020 "
        "(+4.2 days/decade; statistically significant, p = 0.003)."
    )


def test_significant_absolute_change_sentence():
    text = describe_trend("HWF", trend(change_kind="abs", change_value=6.3), "Delhi", 1991, 2020)
    assert "increased by about 6.3 days between 1991 and 2020" in text


def test_not_significant_sentence_mentions_natural_variability():
    text = describe_trend("HWN", trend(significant=False, mk_p=0.31, sen_per_decade=0.2), "Paris", 1991, 2020)
    assert text == (
        "The number of heatwave events in Paris shows a slight upward change (+0.2 events/decade), "
        "but it is not statistically significant (p = 0.31) and may reflect natural year-to-year variability."
    )


def test_zero_slope_sentence():
    text = describe_trend("HWF", trend(significant=False, mk_p=0.9, sen_per_decade=0.0), "Paris", 1991, 2020)
    assert text == "Heatwave days in Paris show no clear trend between 1991 and 2020 (p = 0.90)."


def test_insufficient_years_sentence():
    text = describe_trend("HWF", {"n_years": 4, "reason": "insufficient_years"}, "Paris", 2017, 2020)
    assert text == "Heatwave days in Paris: not enough complete years (4) to assess a trend; at least 10 are needed."


def test_no_heatwaves_gives_single_plain_statement():
    insights, _ = build_insights("Oslo", 1991, 2020, yearly_rows([0] * 30), {}, ["nasa-power"], 1, [])
    assert insights == [
        "No heatwaves (3+ consecutive days above the local 95th percentile) were detected in Oslo between 1991 and 2020."
    ]


def test_build_insights_has_summary_then_trend_sentences():
    trends = {"HWF": trend(), "HWN": trend(change_value=80.0), "HWD": trend(significant=False, mk_p=0.2)}
    insights, _ = build_insights("Delhi", 1991, 2020, yearly_rows([5] * 30), trends, ["nasa-power"], 1, [])
    assert insights[0].startswith("Delhi averaged 5.0 heatwave days per year")
    assert insights[1].startswith("Heatwave days in Delhi increased")
    assert len(insights) == 4


def test_caveats_cover_fallback_area_average_and_low_quality_years():
    _, caveats = build_insights(
        "Box", 1991, 2020, yearly_rows([5] * 30), {"HWF": trend()},
        ["nasa-power", "open-meteo-era5"], 4, [2015],
    )
    joined = " ".join(caveats)
    assert "fallback" in joined
    assert "average of 4 grid points" in joined
    assert "2015" in joined
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_insights.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.insights'`.

- [ ] **Step 3: Implement**

`backend/app/services/insights.py`:
```python
"""Turns trend statistics into plain-language sentences.

Sentences are generated from fixed rules so the app never claims a trend
the statistics do not support.
"""

from app.core.trends import MIN_YEARS

# metric -> (subject, unit, verb for "show(s)")
METRIC_TEXT = {
    "HWF": ("Heatwave days", "days", "show"),
    "HWN": ("The number of heatwave events", "events", "shows"),
    "HWD": ("The longest heatwave each year", "days", "shows"),
}

SOURCE_NAMES = {
    "nasa-power": "NASA POWER (MERRA-2 reanalysis, ~50 km grid)",
    "open-meteo-era5": "Open-Meteo (ERA5 reanalysis, ~25 km grid)",
}


def describe_trend(metric: str, trend: dict, label: str, start_year: int, end_year: int) -> str:
    subject, unit, verb = METRIC_TEXT[metric]
    if trend.get("reason") == "insufficient_years":
        return (
            f"{subject} in {label}: not enough complete years ({trend['n_years']}) to assess a trend; "
            f"at least {MIN_YEARS} are needed."
        )

    sen = trend["sen_per_decade"]
    p = trend["mk_p"]
    if trend["significant"]:
        direction = "increased" if sen > 0 else "decreased"
        if trend["change_kind"] == "pct":
            amount = f"{abs(trend['change_value']):.0f}%"
        else:
            amount = f"{abs(trend['change_value']):.1f} {unit}"
        return (
            f"{subject} in {label} {direction} by about {amount} between {start_year} and {end_year} "
            f"({sen:+.1f} {unit}/decade; statistically significant, p = {p:.3f})."
        )
    if sen == 0:
        return f"{subject} in {label} {verb} no clear trend between {start_year} and {end_year} (p = {p:.2f})."
    direction = "upward" if sen > 0 else "downward"
    return (
        f"{subject} in {label} {verb} a slight {direction} change ({sen:+.1f} {unit}/decade), "
        f"but it is not statistically significant (p = {p:.2f}) and may reflect natural year-to-year variability."
    )


def build_insights(
    label: str,
    start_year: int,
    end_year: int,
    yearly: list[dict],
    trends: dict[str, dict],
    sources_used: list[str],
    n_points: int,
    low_quality_years: list[int],
) -> tuple[list[str], list[str]]:
    insights: list[str] = []
    total_events = sum(row["HWN"] for row in yearly)
    if total_events == 0:
        insights.append(
            f"No heatwaves (3+ consecutive days above the local 95th percentile) were detected in {label} "
            f"between {start_year} and {end_year}."
        )
    else:
        usable = [row for row in yearly if not row["low_quality"]] or yearly
        avg_days = sum(row["HWF"] for row in usable) / len(usable)
        longest = max(yearly, key=lambda row: row["HWD"])
        insights.append(
            f"{label} averaged {avg_days:.1f} heatwave days per year between {start_year} and {end_year}; "
            f"the longest heatwave lasted {longest['HWD']} days ({longest['year']})."
        )
        for metric in ("HWF", "HWN", "HWD"):
            if metric in trends:
                insights.append(describe_trend(metric, trends[metric], label, start_year, end_year))

    sources = ", ".join(SOURCE_NAMES.get(s, s) for s in sources_used)
    caveats = [
        f"Data: {sources}. Gridded reanalysis smooths local extremes, so a single weather station "
        "may record more or hotter heatwave days.",
        "A heatwave is 3+ consecutive days with daily maximum temperature above the local 95th percentile "
        "for that time of year (1981–2010 baseline, ±7-day window).",
        "Trend significance uses the Mann-Kendall test (p < 0.05); trend size uses Sen's slope.",
    ]
    if n_points > 1:
        caveats.append(
            f"Region results are the average of {n_points} grid points; local hotspots inside the region may differ."
        )
    if "open-meteo-era5" in sources_used:
        caveats.append(
            "Some or all data came from the fallback source Open-Meteo (ERA5) because NASA POWER was unavailable."
        )
    if low_quality_years:
        years = ", ".join(str(y) for y in low_quality_years)
        caveats.append(f"Years with more than 10% missing data ({years}) are excluded from trend calculations.")
    return insights, caveats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_insights.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/insights.py backend/tests/test_insights.py
git commit -m "feat(backend): add rule-based insight sentences and caveats"
```

---

### Task 6: Region resolution, request models and cache keys

**Files:**
- Create: `backend/app/models.py` (request models now; response models added in Task 8), `backend/app/services/region.py`
- Test: `backend/tests/test_region.py`

**Interfaces:**
- Consumes: `DATA_START_YEAR`, `last_complete_year()` from `app.config`.
- Produces: `PointRegion(type="point", lat, lon, label)`, `BoxRegion(type="box", south, west, north, east, label)`, `Region` (discriminated union), `AnalyzeRequest(hazard: Literal["heatwave"], region: Region, start_year: int, end_year: int)`, `MAX_BOX_DEGREES = 5.0`; `LAT_STEP = 0.5`, `LON_STEP = 0.625`, `snap(lat, lon) -> tuple[float, float]`, `grid_points(region) -> list[tuple[float, float]]`, `cell_id(lat, lon) -> str`, `analysis_id(hazard, points, start_year, end_year, algo_version) -> str` (64-char hex).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_region.py`:
```python
import pytest
from pydantic import ValidationError

from app.config import last_complete_year
from app.models import AnalyzeRequest, BoxRegion, PointRegion
from app.services.region import analysis_id, cell_id, grid_points, snap


def test_snap_to_merra2_grid():
    assert snap(28.61, 77.21) == (28.5, 77.5)
    assert snap(-33.87, 151.21) == (-34.0, 151.25)


def test_snap_wraps_east_edge_and_clamps_poles():
    assert snap(-89.9, 179.9) == (-90.0, -180.0)
    assert snap(89.99, 0.1) == (90.0, 0.0)


def test_point_region_is_one_grid_point():
    assert grid_points(PointRegion(type="point", lat=28.61, lon=77.21)) == [(28.5, 77.5)]


def test_small_box_collapses_to_one_point():
    box = BoxRegion(type="box", south=28.5, west=77.2, north=28.7, east=77.4)
    assert grid_points(box) == [(28.5, 77.5)]


def test_large_box_samples_nine_points():
    box = BoxRegion(type="box", south=20.0, west=70.0, north=25.0, east=75.0)
    points = grid_points(box)
    assert len(points) == 9
    assert points == sorted(points)


def test_cell_id_format():
    assert cell_id(28.5, -77.5) == "28.500:-77.500"


def test_analysis_id_is_deterministic_and_sensitive_to_inputs():
    a = analysis_id("heatwave", [(28.5, 77.5)], 1990, 2020, "v1")
    assert a == analysis_id("heatwave", [(28.5, 77.5)], 1990, 2020, "v1")
    assert len(a) == 64
    assert a != analysis_id("heatwave", [(28.5, 77.5)], 1991, 2020, "v1")
    assert a != analysis_id("heatwave", [(28.5, 77.5)], 1990, 2020, "v2")


def valid_request(**overrides) -> dict:
    return {
        "hazard": "heatwave",
        "region": {"type": "point", "lat": 28.6, "lon": 77.2, "label": "Delhi"},
        "start_year": 1990,
        "end_year": 2020,
    } | overrides


def test_analyze_request_accepts_valid_input_and_defaults_hazard():
    body = valid_request()
    del body["hazard"]
    request = AnalyzeRequest.model_validate(body)
    assert request.hazard == "heatwave"
    assert isinstance(request.region, PointRegion)


@pytest.mark.parametrize(
    "overrides",
    [
        {"start_year": 1970},
        {"end_year": last_complete_year() + 1},
        {"start_year": 2010, "end_year": 2000},
        {"hazard": "drought"},
        {"region": {"type": "point", "lat": 91, "lon": 0}},
        {"region": {"type": "point", "lat": float("nan"), "lon": 0}},
        {"region": {"type": "box", "south": 10, "west": 10, "north": 16, "east": 12}},
        {"region": {"type": "box", "south": 12, "west": 10, "north": 10, "east": 12}},
        {"region": {"type": "point", "lat": 1, "lon": 1, "label": "x" * 101}},
        {"unexpected": True},
    ],
)
def test_analyze_request_rejects_invalid_input(overrides):
    with pytest.raises(ValidationError):
        AnalyzeRequest.model_validate(valid_request(**overrides))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_region.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 3: Implement**

`backend/app/models.py`:
```python
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import DATA_START_YEAR, last_complete_year

MAX_BOX_DEGREES = 5.0

Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]
Label = Annotated[str, Field(min_length=1, max_length=100)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PointRegion(StrictModel):
    type: Literal["point"]
    lat: Latitude
    lon: Longitude
    label: Label = "Selected point"


class BoxRegion(StrictModel):
    type: Literal["box"]
    south: Latitude
    west: Longitude
    north: Latitude
    east: Longitude
    label: Label = "Custom box"

    @model_validator(mode="after")
    def check_box(self):
        if self.south >= self.north or self.west >= self.east:
            raise ValueError("Box needs south < north and west < east.")
        if self.north - self.south > MAX_BOX_DEGREES or self.east - self.west > MAX_BOX_DEGREES:
            raise ValueError(f"Box can be at most {MAX_BOX_DEGREES:g}° × {MAX_BOX_DEGREES:g}°.")
        return self


Region = Annotated[PointRegion | BoxRegion, Field(discriminator="type")]


class AnalyzeRequest(StrictModel):
    hazard: Literal["heatwave"] = "heatwave"
    region: Region
    start_year: int
    end_year: int

    @model_validator(mode="after")
    def check_years(self):
        max_year = last_complete_year()
        if not (DATA_START_YEAR <= self.start_year <= self.end_year <= max_year):
            raise ValueError(f"Years must satisfy {DATA_START_YEAR} ≤ start_year ≤ end_year ≤ {max_year}.")
        return self
```

`backend/app/services/region.py`:
```python
"""Turns a user region into data grid points and cache keys.

NASA POWER serves MERRA-2 data on a 0.5° (lat) x 0.625° (lon) grid, so
coordinates are snapped to cell centres: nearby clicks share one cache entry.
"""

import hashlib

from app.models import BoxRegion, PointRegion

LAT_STEP = 0.5
LON_STEP = 0.625
BOX_SAMPLES_PER_SIDE = 3


def snap(lat: float, lon: float) -> tuple[float, float]:
    snapped_lat = min(90.0, max(-90.0, round(lat / LAT_STEP) * LAT_STEP))
    snapped_lon = round(lon / LON_STEP) * LON_STEP
    if snapped_lon >= 180.0:
        snapped_lon -= 360.0
    return round(snapped_lat, 3) + 0.0, round(snapped_lon, 3) + 0.0  # + 0.0 turns -0.0 into 0.0


def grid_points(region: PointRegion | BoxRegion) -> list[tuple[float, float]]:
    if isinstance(region, PointRegion):
        return [snap(region.lat, region.lon)]
    n = BOX_SAMPLES_PER_SIDE
    lat_step = (region.north - region.south) / n
    lon_step = (region.east - region.west) / n
    points = {
        snap(region.south + (i + 0.5) * lat_step, region.west + (j + 0.5) * lon_step)
        for i in range(n)
        for j in range(n)
    }
    return sorted(points)


def cell_id(lat: float, lon: float) -> str:
    return f"{lat:.3f}:{lon:.3f}"


def analysis_id(
    hazard: str, points: list[tuple[float, float]], start_year: int, end_year: int, algo_version: str
) -> str:
    raw = "|".join([hazard, ",".join(cell_id(*p) for p in points), f"{start_year}-{end_year}", algo_version])
    return hashlib.sha256(raw.encode()).hexdigest()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_region.py -v`
Expected: 18 passed (8 named tests + 10 parametrized cases).

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/app/services/region.py backend/tests/test_region.py
git commit -m "feat(backend): add validated request models and grid-based region resolution"
```

---

### Task 7: Upstream provider clients (NASA POWER, Open-Meteo, Nominatim)

**Files:**
- Create: `backend/app/clients/power.py`, `backend/app/clients/openmeteo.py`, `backend/app/clients/nominatim.py`, `backend/tests/fakes.py`
- Test: `backend/tests/test_clients.py`

**Interfaces:**
- Consumes: `UpstreamClient.get_json`, `UpstreamClient.nominatim_slot`, `UpstreamError`, `UpstreamTimeout`, `DailySeries`.
- Produces: `POWER_URL`, `fetch_power(upstream, lat, lon, start: date, end: date) -> DailySeries` (sources `["nasa-power"]`); `ARCHIVE_URL`, `GEOCODE_URL`, `fetch_openmeteo(upstream, lat, lon, start, end) -> DailySeries` (sources `["open-meteo-era5"]`), `search_cities(upstream, q) -> list[dict]` (`{"kind":"city","name","label","lat","lon","bbox":None,"clipped":False}`); `NOMINATIM_URL`, `search_states(upstream, q) -> list[dict]` (`{"name","label","lat","lon","bbox":{"south","west","north","east"}}`). Test fakes: `synthetic_tmax(d) -> float`, `power_payload(lat, lon, start, end, tmax_fn=synthetic_tmax, fill_days=frozenset(), unit="C") -> dict`, `openmeteo_payload(lat, lon, start, end, tmax_fn=synthetic_tmax) -> dict`, `power_responder(...)`, `openmeteo_responder(...)`.

- [ ] **Step 1: Write the test fakes**

`backend/tests/fakes.py`:
```python
"""Synthetic provider responses for tests (no network)."""

import math
from datetime import date, datetime, timedelta

import httpx


def synthetic_tmax(d: date) -> float:
    """Seasonal cycle + deterministic wiggle + steady warming (~2.2 °C over 1981-2025)."""
    doy = d.timetuple().tm_yday
    seasonal = 30 + 8 * math.sin(2 * math.pi * (doy - 100) / 365)
    wiggle = ((d.toordinal() * 7919) % 13 - 6) * 0.4
    warming = 0.05 * (d.year - 1981)
    return round(seasonal + wiggle + warming, 2)


def days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def power_payload(lat, lon, start, end, tmax_fn=synthetic_tmax, fill_days=frozenset(), unit="C") -> dict:
    keys = {d: d.strftime("%Y%m%d") for d in days(start, end)}
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat, 200.0]},
        "properties": {
            "parameter": {
                "T2M_MAX": {k: (-999.0 if d in fill_days else tmax_fn(d)) for d, k in keys.items()},
                "PRECTOTCORR": {k: 0.5 for k in keys.values()},
            }
        },
        "header": {"fill_value": -999.0, "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d")},
        "parameters": {"T2M_MAX": {"units": unit}, "PRECTOTCORR": {"units": "mm/day"}},
    }


def openmeteo_payload(lat, lon, start, end, tmax_fn=synthetic_tmax) -> dict:
    ds = days(start, end)
    return {
        "latitude": lat + 0.02,
        "longitude": lon - 0.03,
        "daily_units": {"time": "iso8601", "temperature_2m_max": "°C", "precipitation_sum": "mm"},
        "daily": {
            "time": [d.isoformat() for d in ds],
            "temperature_2m_max": [tmax_fn(d) for d in ds],
            "precipitation_sum": [0.0 for _ in ds],
        },
    }


def power_responder(tmax_fn=synthetic_tmax, fill_days=frozenset()):
    def respond(request: httpx.Request) -> httpx.Response:
        p = request.url.params
        start = datetime.strptime(p["start"], "%Y%m%d").date()
        end = datetime.strptime(p["end"], "%Y%m%d").date()
        payload = power_payload(float(p["latitude"]), float(p["longitude"]), start, end, tmax_fn, fill_days)
        return httpx.Response(200, json=payload)

    return respond


def openmeteo_responder(tmax_fn=synthetic_tmax):
    def respond(request: httpx.Request) -> httpx.Response:
        p = request.url.params
        payload = openmeteo_payload(
            float(p["latitude"]), float(p["longitude"]),
            date.fromisoformat(p["start_date"]), date.fromisoformat(p["end_date"]), tmax_fn,
        )
        return httpx.Response(200, json=payload)

    return respond
```

- [ ] **Step 2: Write the failing tests**

`backend/tests/test_clients.py`:
```python
import time
from datetime import date

import httpx
import pytest
import respx

from app.clients.http import UpstreamClient
from app.clients.nominatim import NOMINATIM_URL, search_states
from app.clients.openmeteo import ARCHIVE_URL, GEOCODE_URL, fetch_openmeteo, search_cities
from app.clients.power import POWER_URL, fetch_power
from app.config import Settings
from app.errors import UpstreamError, UpstreamTimeout
from tests.fakes import openmeteo_payload, power_payload

START, END = date(2020, 1, 1), date(2020, 1, 3)


@pytest.fixture
async def upstream():
    client = UpstreamClient(Settings(http_backoff_seconds=0, http_retries=2))
    yield client
    await client.aclose()


@respx.mock
async def test_power_maps_fill_values_to_none(upstream):
    payload = power_payload(28.5, 77.5, START, END, lambda d: 30.0, fill_days={date(2020, 1, 2)})
    respx.get(POWER_URL).mock(return_value=httpx.Response(200, json=payload))
    series = await fetch_power(upstream, 28.5, 77.5, START, END)
    assert series.tmax == [30.0, None, 30.0]
    assert series.precip == [0.5, 0.5, 0.5]
    assert series.sources == ["nasa-power"]
    assert series.start == START


@respx.mock
async def test_power_rejects_unexpected_units(upstream):
    payload = power_payload(28.5, 77.5, START, END, unit="F")
    respx.get(POWER_URL).mock(return_value=httpx.Response(200, json=payload))
    with pytest.raises(UpstreamError):
        await fetch_power(upstream, 28.5, 77.5, START, END)


@respx.mock
async def test_power_rejects_missing_days(upstream):
    payload = power_payload(28.5, 77.5, START, date(2020, 1, 2))
    respx.get(POWER_URL).mock(return_value=httpx.Response(200, json=payload))
    with pytest.raises(UpstreamError):
        await fetch_power(upstream, 28.5, 77.5, START, END)


@respx.mock
async def test_power_rejects_far_away_coordinates(upstream):
    payload = power_payload(10.0, 10.0, START, END)
    respx.get(POWER_URL).mock(return_value=httpx.Response(200, json=payload))
    with pytest.raises(UpstreamError):
        await fetch_power(upstream, 28.5, 77.5, START, END)


@respx.mock
async def test_retries_server_errors_then_succeeds(upstream):
    route = respx.get(POWER_URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=power_payload(28.5, 77.5, START, END))]
    )
    series = await fetch_power(upstream, 28.5, 77.5, START, END)
    assert len(series.tmax) == 3
    assert route.call_count == 2


@respx.mock
async def test_client_errors_are_not_retried(upstream):
    route = respx.get(POWER_URL).mock(return_value=httpx.Response(404))
    with pytest.raises(UpstreamError):
        await fetch_power(upstream, 28.5, 77.5, START, END)
    assert route.call_count == 1


@respx.mock
async def test_repeated_timeouts_raise_upstream_timeout(upstream):
    route = respx.get(POWER_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(UpstreamTimeout):
        await fetch_power(upstream, 28.5, 77.5, START, END)
    assert route.call_count == 3


@respx.mock
async def test_openmeteo_parses_daily_values(upstream):
    respx.get(ARCHIVE_URL).mock(
        return_value=httpx.Response(200, json=openmeteo_payload(28.5, 77.5, START, END, lambda d: 31.5))
    )
    series = await fetch_openmeteo(upstream, 28.5, 77.5, START, END)
    assert series.tmax == [31.5, 31.5, 31.5]
    assert series.sources == ["open-meteo-era5"]


@respx.mock
async def test_openmeteo_error_body_with_200_is_upstream_error(upstream):
    body = {"error": True, "reason": "Minutely API request limit exceeded."}
    respx.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, json=body))
    with pytest.raises(UpstreamError):
        await fetch_openmeteo(upstream, 28.5, 77.5, START, END)


@respx.mock
async def test_openmeteo_rejects_wrong_dates(upstream):
    payload = openmeteo_payload(28.5, 77.5, date(2019, 1, 1), date(2019, 1, 3))
    respx.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, json=payload))
    with pytest.raises(UpstreamError):
        await fetch_openmeteo(upstream, 28.5, 77.5, START, END)


@respx.mock
async def test_search_cities_builds_labels(upstream):
    body = {"results": [{"name": "Delhi", "latitude": 28.65, "longitude": 77.23, "country": "India",
                         "admin1": "National Capital Territory of Delhi"}]}
    respx.get(GEOCODE_URL).mock(return_value=httpx.Response(200, json=body))
    assert await search_cities(upstream, "Delhi") == [{
        "kind": "city", "name": "Delhi", "label": "Delhi, National Capital Territory of Delhi, India",
        "lat": 28.65, "lon": 77.23, "bbox": None, "clipped": False,
    }]


@respx.mock
async def test_search_cities_handles_no_results(upstream):
    respx.get(GEOCODE_URL).mock(return_value=httpx.Response(200, json={"generationtime_ms": 0.1}))
    assert await search_cities(upstream, "zzzz") == []


@respx.mock
async def test_search_states_parses_bounding_box_and_throttles(upstream):
    body = [{"name": "Rajasthan", "display_name": "Rajasthan, India", "lat": "26.81", "lon": "73.77",
             "boundingbox": ["23.0586612", "30.1982530", "69.4844368", "78.2720089"]},
            {"name": "No box", "display_name": "No box", "lat": "1", "lon": "1"}]
    route = respx.get(NOMINATIM_URL).mock(return_value=httpx.Response(200, json=body))
    started = time.monotonic()
    first = await search_states(upstream, "Rajasthan")
    await search_states(upstream, "Rajasthan")
    assert time.monotonic() - started >= 0.9
    assert route.call_count == 2
    assert first == [{
        "name": "Rajasthan", "label": "Rajasthan, India", "lat": 26.81, "lon": 73.77,
        "bbox": {"south": 23.0586612, "west": 69.4844368, "north": 30.198253, "east": 78.2720089},
    }]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_clients.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.clients.nominatim'`.

- [ ] **Step 4: Implement**

`backend/app/clients/power.py`:
```python
"""NASA POWER daily point API (MERRA-2 reanalysis). Primary data source."""

from datetime import date, timedelta

from app.clients.http import UpstreamClient
from app.core.series import DailySeries
from app.errors import UpstreamError

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
SOURCE = "nasa-power"
MAX_COORD_DRIFT_DEG = 1.0


async def fetch_power(upstream: UpstreamClient, lat: float, lon: float, start: date, end: date) -> DailySeries:
    payload = await upstream.get_json(
        POWER_URL,
        {
            "parameters": "T2M_MAX,PRECTOTCORR",
            "community": "RE",
            "latitude": lat,
            "longitude": lon,
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "format": "JSON",
        },
    )
    return parse_power(payload, lat, lon, start, end)


def parse_power(payload: dict, lat: float, lon: float, start: date, end: date) -> DailySeries:
    try:
        parameter = payload["properties"]["parameter"]
        tmax_raw = parameter["T2M_MAX"]
        precip_raw = parameter["PRECTOTCORR"]
        tmax_unit = payload["parameters"]["T2M_MAX"]["units"]
        precip_unit = payload["parameters"]["PRECTOTCORR"]["units"]
        resp_lon, resp_lat = payload["geometry"]["coordinates"][:2]
        fill_value = float(payload.get("header", {}).get("fill_value", -999.0))
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise UpstreamError("NASA POWER returned an unexpected response.") from exc

    if tmax_unit != "C" or precip_unit != "mm/day":
        raise UpstreamError("NASA POWER returned unexpected units.")
    if abs(resp_lat - lat) > MAX_COORD_DRIFT_DEG or abs(resp_lon - lon) > MAX_COORD_DRIFT_DEG:
        raise UpstreamError("NASA POWER returned data for a different location.")

    keys = [(start + timedelta(days=i)).strftime("%Y%m%d") for i in range((end - start).days + 1)]
    if any(k not in tmax_raw for k in keys):
        raise UpstreamError("NASA POWER response is missing days.")

    def clean(value) -> float | None:
        # POWER encodes missing data as a fill value (-999), not null.
        if value is None or float(value) == fill_value:
            return None
        return float(value)

    return DailySeries(
        start=start,
        tmax=[clean(tmax_raw[k]) for k in keys],
        precip=[clean(precip_raw.get(k)) for k in keys],
        sources=[SOURCE],
    )
```

`backend/app/clients/openmeteo.py`:
```python
"""Open-Meteo: historical archive (fallback data source) and city geocoding."""

from datetime import date, timedelta

from app.clients.http import UpstreamClient
from app.core.series import DailySeries
from app.errors import UpstreamError

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
SOURCE = "open-meteo-era5"
MAX_COORD_DRIFT_DEG = 1.0


async def fetch_openmeteo(upstream: UpstreamClient, lat: float, lon: float, start: date, end: date) -> DailySeries:
    payload = await upstream.get_json(
        ARCHIVE_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": "temperature_2m_max,precipitation_sum",
            "timezone": "GMT",
        },
    )
    return parse_archive(payload, lat, lon, start, end)


def parse_archive(payload: dict, lat: float, lon: float, start: date, end: date) -> DailySeries:
    if not isinstance(payload, dict) or payload.get("error"):
        raise UpstreamError("Open-Meteo returned an error.")
    try:
        daily = payload["daily"]
        units = payload["daily_units"]
        times = daily["time"]
        tmax = daily["temperature_2m_max"]
        precip = daily["precipitation_sum"]
        resp_lat, resp_lon = float(payload["latitude"]), float(payload["longitude"])
    except (KeyError, TypeError, ValueError) as exc:
        raise UpstreamError("Open-Meteo returned an unexpected response.") from exc

    if units.get("temperature_2m_max") != "°C" or units.get("precipitation_sum") != "mm":
        raise UpstreamError("Open-Meteo returned unexpected units.")
    if abs(resp_lat - lat) > MAX_COORD_DRIFT_DEG or abs(resp_lon - lon) > MAX_COORD_DRIFT_DEG:
        raise UpstreamError("Open-Meteo returned data for a different location.")
    expected = [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]
    if times != expected or len(tmax) != len(expected) or len(precip) != len(expected):
        raise UpstreamError("Open-Meteo returned unexpected dates.")

    return DailySeries(
        start=start,
        tmax=[None if v is None else float(v) for v in tmax],
        precip=[None if v is None else float(v) for v in precip],
        sources=[SOURCE],
    )


async def search_cities(upstream: UpstreamClient, q: str) -> list[dict]:
    payload = await upstream.get_json(GEOCODE_URL, {"name": q, "count": 5, "language": "en", "format": "json"})
    results = []
    for item in payload.get("results", []) if isinstance(payload, dict) else []:
        try:
            parts = [item["name"], item.get("admin1"), item.get("country")]
            results.append(
                {
                    "kind": "city",
                    "name": item["name"],
                    "label": ", ".join(p for p in parts if p),
                    "lat": float(item["latitude"]),
                    "lon": float(item["longitude"]),
                    "bbox": None,
                    "clipped": False,
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return results
```

`backend/app/clients/nominatim.py`:
```python
"""Nominatim (OpenStreetMap) search, used to get a state's bounding box.

Usage policy: at most 1 request per second and an identifying User-Agent.
"""

from app.clients.http import UpstreamClient

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


async def search_states(upstream: UpstreamClient, q: str) -> list[dict]:
    async with upstream.nominatim_slot():
        payload = await upstream.get_json(
            NOMINATIM_URL, {"q": q, "format": "jsonv2", "limit": 5, "featureType": "state"}
        )
    results = []
    for item in payload if isinstance(payload, list) else []:
        try:
            south, north, west, east = (float(v) for v in item["boundingbox"])
            results.append(
                {
                    "name": item["name"],
                    "label": item["display_name"],
                    "lat": float(item["lat"]),
                    "lon": float(item["lon"]),
                    "bbox": {"south": south, "west": west, "north": north, "east": east},
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return results
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_clients.py -v`
Expected: 13 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/clients backend/tests/fakes.py backend/tests/test_clients.py
git commit -m "feat(backend): add NASA POWER, Open-Meteo and Nominatim clients with validation"
```

---

### Task 8: Ingest cache, analysis orchestration and analysis endpoints

**Files:**
- Create: `backend/app/services/ingest.py`, `backend/app/services/analysis.py`, `backend/app/api/analyze.py`
- Modify: `backend/app/models.py` (append response models), `backend/app/main.py` (include router)
- Test: `backend/tests/test_api_analyze.py`

**Interfaces:**
- Consumes: everything from Tasks 1–7.
- Produces: `DATA_START = date(1981, 1, 1)`; `load_points(db, upstream, locks, points, end) -> list[DailySeries]`; `ALGO_VERSION = "v1"`; `get_or_create_analysis(db, upstream, locks, settings, req: AnalyzeRequest) -> dict`; `get_analysis(db, analysis_id) -> dict` (raises `NotFoundError`); `build_chart(doc) -> dict`; `CACHE_CONTROL = "public, max-age=86400"`; `AnalysisId` annotated path type; routes `POST /api/analyze`, `GET /api/analyses/{analysis_id}`; response model `AnalysisOut` (fields per spec §6/§7 plus `id`, `cached`, `chart`).

- [ ] **Step 1: Write the failing API tests**

`backend/tests/test_api_analyze.py`:
```python
from datetime import date, timedelta

import httpx
import pytest
import respx

from app.clients.openmeteo import ARCHIVE_URL
from app.clients.power import POWER_URL
from app.config import last_complete_year
from tests.fakes import openmeteo_responder, power_responder, synthetic_tmax

DELHI = {"type": "point", "lat": 28.61, "lon": 77.21, "label": "Delhi, India"}


def body(**overrides) -> dict:
    return {"hazard": "heatwave", "region": DELHI, "start_year": 1990, "end_year": 2020} | overrides


@pytest.fixture
def providers():
    with respx.mock(assert_all_called=False) as router:
        power = router.get(POWER_URL).mock(side_effect=power_responder())
        openmeteo = router.get(ARCHIVE_URL).mock(side_effect=openmeteo_responder())
        yield power, openmeteo


def test_first_request_computes_then_second_is_served_from_cache(client, mongo, providers):
    power, openmeteo = providers
    first = client.post("/api/analyze", json=body())
    assert first.status_code == 200, first.text
    data = first.json()
    assert data["cached"] is False
    assert data["sources_used"] == ["nasa-power"]
    assert [row["year"] for row in data["yearly"]] == list(range(1990, 2021))
    assert len(data["threshold_by_doy"]) == 365
    assert data["chart"]["years"] == list(range(1990, 2021))
    assert set(data["chart"]["series"]) == {"HWN", "HWF", "HWD", "HWM", "HWA"}
    assert power.call_count == 1 and openmeteo.call_count == 0

    second = client.post("/api/analyze", json=body())
    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert second.json()["id"] == data["id"]
    assert power.call_count == 1
    assert mongo.weather_daily.count_documents({}) == 1
    assert mongo.analyses.count_documents({}) == 1


def test_warming_data_produces_significant_increase(client, providers):
    data = client.post("/api/analyze", json=body(start_year=1981, end_year=last_complete_year())).json()
    hwf = data["trends"]["HWF"]
    assert hwf["significant"] is True
    assert hwf["sen_per_decade"] > 0
    assert any("increased" in sentence for sentence in data["insights"])


def test_different_years_reuse_cached_weather(client, mongo, providers):
    power, _ = providers
    client.post("/api/analyze", json=body())
    response = client.post("/api/analyze", json=body(start_year=2000))
    assert response.json()["cached"] is False
    assert power.call_count == 1


def test_box_fetches_each_grid_point(client, mongo, providers):
    power, _ = providers
    box = {"type": "box", "south": 20.0, "west": 70.0, "north": 25.0, "east": 75.0, "label": "Box"}
    response = client.post("/api/analyze", json=body(region=box))
    assert response.status_code == 200
    assert power.call_count == 9
    assert len(response.json()["region"]["points"]) == 9
    assert any("average of 9 grid points" in c for c in response.json()["caveats"])


def test_falls_back_to_openmeteo_when_power_fails(client, providers):
    power, openmeteo = providers
    power.mock(side_effect=None, return_value=httpx.Response(500))
    response = client.post("/api/analyze", json=body())
    assert response.status_code == 200
    assert response.json()["sources_used"] == ["open-meteo-era5"]
    assert any("fallback" in c for c in response.json()["caveats"])
    assert openmeteo.call_count == 1


def test_both_providers_failing_returns_502_and_caches_nothing(client, mongo, providers):
    power, openmeteo = providers
    power.mock(side_effect=None, return_value=httpx.Response(500))
    openmeteo.mock(side_effect=None, return_value=httpx.Response(200, json={"error": True, "reason": "limit"}))
    response = client.post("/api/analyze", json=body())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"
    assert mongo.analyses.count_documents({}) == 0
    assert mongo.weather_daily.count_documents({}) == 0


def test_both_providers_timing_out_returns_504(client, providers):
    power, openmeteo = providers
    power.mock(side_effect=httpx.ReadTimeout("slow"))
    openmeteo.mock(side_effect=httpx.ReadTimeout("slow"))
    response = client.post("/api/analyze", json=body())
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"


def test_stale_weather_doc_fetches_only_missing_tail(client, mongo, providers):
    power, _ = providers
    old_end = date(last_complete_year() - 1, 12, 31)
    n = (old_end - date(1981, 1, 1)).days + 1
    mongo.weather_daily.insert_one({
        "_id": "28.500:77.500", "lat": 28.5, "lon": 77.5, "start_date": "1981-01-01",
        "end_date": old_end.isoformat(), "units": {"tmax": "°C", "precip": "mm"},
        "tmax": [synthetic_tmax(date(1981, 1, 1) + timedelta(days=i)) for i in range(n)],
        "precip": [0.0] * n, "sources": ["nasa-power"],
    })
    response = client.post("/api/analyze", json=body())
    assert response.status_code == 200
    assert power.call_count == 1
    assert power.calls.last.request.url.params["start"] == f"{last_complete_year()}0101"
    doc = mongo.weather_daily.find_one({"_id": "28.500:77.500"})
    assert doc["end_date"] == f"{last_complete_year()}-12-31"
    assert len(doc["tmax"]) == (date(last_complete_year(), 12, 31) - date(1981, 1, 1)).days + 1


def test_long_outage_flags_year_and_excludes_it_from_trends(client, providers):
    power, _ = providers
    outage = {date(2015, 3, 1) + timedelta(days=i) for i in range(40)}
    power.mock(side_effect=power_responder(fill_days=outage))
    data = client.post("/api/analyze", json=body()).json()
    row_2015 = next(r for r in data["yearly"] if r["year"] == 2015)
    assert row_2015["low_quality"] is True
    assert data["data_quality"]["low_quality_years"] == [2015]
    assert data["trends"]["HWF"]["n_years"] == 30
    assert any("2015" in c for c in data["caveats"])


def test_single_year_range_reports_insufficient_years(client, providers):
    response = client.post("/api/analyze", json=body(start_year=2020, end_year=2020))
    assert response.status_code == 200
    assert response.json()["trends"]["HWF"]["reason"] == "insufficient_years"


@pytest.mark.parametrize(
    "payload",
    [
        body(start_year=1970),
        body(hazard="drought"),
        body(region={"type": "box", "south": 0, "west": 0, "north": 6, "east": 1}),
        body(extra="nope"),
    ],
)
def test_invalid_input_returns_422_without_calling_providers(client, providers, payload):
    power, _ = providers
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert power.call_count == 0


def test_read_analysis_by_id(client, providers):
    created = client.post("/api/analyze", json=body()).json()
    response = client.get(f"/api/analyses/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["cached"] is True
    assert "max-age" in response.headers["cache-control"]


def test_read_analysis_rejects_bad_ids(client):
    assert client.get("/api/analyses/not-a-hash").status_code == 422
    missing = client.get("/api/analyses/" + "0" * 64)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_api_analyze.py -v`
Expected: FAIL — 404s on `/api/analyze` (router not registered).

- [ ] **Step 3: Append response models to `backend/app/models.py`**

```python
from datetime import date, datetime  # add to the imports at the top of the file


class YearlyRow(BaseModel):
    year: int
    HWN: int
    HWF: int
    HWD: int
    HWM: float | None
    HWA: float | None
    low_quality: bool


class EventOut(BaseModel):
    start: date
    end: date
    days: int
    peak_tmax: float
    mean_exceedance: float


class TrendOut(BaseModel):
    n_years: int
    sen_per_decade: float | None
    mk_p: float | None
    significant: bool
    ols_slope: float | None
    ols_intercept: float | None
    change_kind: Literal["pct", "abs"] | None
    change_value: float | None
    reason: str | None


class ChartSeries(BaseModel):
    values: list[float | None]
    rolling5: list[float | None]
    trendline: list[float | None]


class ChartOut(BaseModel):
    years: list[int]
    series: dict[str, ChartSeries]


class DataQuality(BaseModel):
    days: int
    removed: int
    interpolated: int
    low_quality_years: list[int]


class RegionOut(BaseModel):
    type: Literal["point", "box"]
    label: str
    bbox: dict[str, float] | None
    points: list[list[float]]


class YearsOut(BaseModel):
    start: int
    end: int


class ParamsOut(BaseModel):
    percentile: float
    min_days: int
    window: int
    baseline: list[int]


class AnalysisOut(BaseModel):
    id: str
    cached: bool
    hazard: str
    algo_version: str
    region: RegionOut
    sources_used: list[str]
    years: YearsOut
    params: ParamsOut
    yearly: list[YearlyRow]
    events: list[EventOut]
    threshold_by_doy: list[float | None]
    trends: dict[str, TrendOut]
    insights: list[str]
    caveats: list[str]
    data_quality: DataQuality
    chart: ChartOut
    created_at: datetime
```

- [ ] **Step 4: Implement ingest**

`backend/app/services/ingest.py`:
```python
"""Raw weather cache: one `weather_daily` document per grid cell.

A cell is fetched once (1981 -> last complete year) and reused by every
region and year range that touches it. NASA POWER is tried first; Open-Meteo
is the per-cell fallback.
"""

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta

from pymongo.asynchronous.database import AsyncDatabase

from app.clients.http import UpstreamClient
from app.clients.openmeteo import fetch_openmeteo
from app.clients.power import fetch_power
from app.core.series import DailySeries
from app.errors import UpstreamError
from app.locks import KeyedLocks
from app.services.region import cell_id

logger = logging.getLogger(__name__)

DATA_START = date(1981, 1, 1)


def series_from_doc(doc: dict) -> DailySeries:
    return DailySeries(
        start=date.fromisoformat(doc["start_date"]), tmax=doc["tmax"], precip=doc["precip"], sources=doc["sources"]
    )


def doc_from_series(cid: str, lat: float, lon: float, series: DailySeries) -> dict:
    return {
        "_id": cid,
        "lat": lat,
        "lon": lon,
        "start_date": series.start.isoformat(),
        "end_date": series.end.isoformat(),
        "units": {"tmax": "°C", "precip": "mm"},
        "tmax": series.tmax,
        "precip": series.precip,
        "sources": series.sources,
        "fetched_at": datetime.now(UTC),
    }


def append_series(old: DailySeries, tail: DailySeries) -> DailySeries:
    if tail.start != old.end + timedelta(days=1):
        raise ValueError("Tail must start the day after the cached series ends.")
    return DailySeries(
        start=old.start,
        tmax=old.tmax + tail.tmax,
        precip=old.precip + tail.precip,
        sources=sorted(set(old.sources) | set(tail.sources)),
    )


async def fetch_with_fallback(upstream: UpstreamClient, lat: float, lon: float, start: date, end: date) -> DailySeries:
    async with upstream.concurrency:
        try:
            return await fetch_power(upstream, lat, lon, start, end)
        except UpstreamError as exc:
            logger.warning("NASA POWER failed for %s,%s (%s); trying Open-Meteo", lat, lon, exc.message)
            return await fetch_openmeteo(upstream, lat, lon, start, end)


async def load_point(
    db: AsyncDatabase, upstream: UpstreamClient, locks: KeyedLocks, lat: float, lon: float, end: date
) -> DailySeries:
    cid = cell_id(lat, lon)
    async with locks.get(f"cell:{cid}"):
        doc = await db.weather_daily.find_one({"_id": cid})
        if doc is not None:
            cached = series_from_doc(doc)
            if cached.end >= end:
                return cached
            tail = await fetch_with_fallback(upstream, lat, lon, cached.end + timedelta(days=1), end)
            series = append_series(cached, tail)
        else:
            series = await fetch_with_fallback(upstream, lat, lon, DATA_START, end)
        await db.weather_daily.replace_one({"_id": cid}, doc_from_series(cid, lat, lon, series), upsert=True)
        return series


async def load_points(
    db: AsyncDatabase, upstream: UpstreamClient, locks: KeyedLocks, points: list[tuple[float, float]], end: date
) -> list[DailySeries]:
    return list(await asyncio.gather(*(load_point(db, upstream, locks, lat, lon, end) for lat, lon in points)))
```

- [ ] **Step 5: Implement analysis orchestration**

`backend/app/services/analysis.py`:
```python
"""Orchestrates an analysis: cache lookup -> ingest -> clean -> detect -> trends -> store."""

from datetime import UTC, date, datetime, timedelta

import pandas as pd
from pymongo.asynchronous.database import AsyncDatabase

from app.clients.http import UpstreamClient
from app.config import Settings, last_complete_year
from app.core.cleaning import clean_tmax, low_quality_years, to_daily_series
from app.core.trends import analyze_trend, rolling_mean
from app.errors import NotFoundError
from app.hazards import ANALYZERS
from app.hazards.heatwave import METRIC_KEYS, HeatwaveParams
from app.locks import KeyedLocks
from app.models import AnalyzeRequest, BoxRegion
from app.services.ingest import load_points
from app.services.insights import build_insights
from app.services.region import analysis_id, grid_points

ALGO_VERSION = "v1"
PARAMS = HeatwaveParams()
PCT_METRICS = {"HWN", "HWF", "HWD"}  # counts/days; HWM and HWA are °C, so absolute change only


async def get_or_create_analysis(
    db: AsyncDatabase, upstream: UpstreamClient, locks: KeyedLocks, settings: Settings, req: AnalyzeRequest
) -> dict:
    points = grid_points(req.region)
    aid = analysis_id(req.hazard, points, req.start_year, req.end_year, ALGO_VERSION)

    doc = await db.analyses.find_one({"_id": aid})
    if doc is None:
        async with locks.get(f"analysis:{aid}"):
            doc = await db.analyses.find_one({"_id": aid})  # another request may have just finished it
            if doc is None:
                doc = await compute_analysis(db, upstream, locks, settings, req, points, aid)
                await db.analyses.replace_one({"_id": aid}, doc, upsert=True)
                return to_response(doc, cached=False, label=req.region.label)
    return to_response(doc, cached=True, label=req.region.label)


async def get_analysis(db: AsyncDatabase, aid: str) -> dict:
    doc = await db.analyses.find_one({"_id": aid})
    if doc is None:
        raise NotFoundError("Analysis not found. It may have expired; run it again.")
    return to_response(doc, cached=True, label=doc["region"]["label"])


async def compute_analysis(
    db: AsyncDatabase,
    upstream: UpstreamClient,
    locks: KeyedLocks,
    settings: Settings,
    req: AnalyzeRequest,
    points: list[tuple[float, float]],
    aid: str,
) -> dict:
    end = date(last_complete_year(), 12, 31)
    stored = await load_points(db, upstream, locks, points, end)
    raw = [to_daily_series(s.start, s.tmax).loc[: pd.Timestamp(end)] for s in stored]
    cleaned = clean_tmax(raw)

    years = range(req.start_year, req.end_year + 1)
    flagged = low_quality_years(cleaned.tmax, years)
    result = ANALYZERS[req.hazard](cleaned.tmax, years, set(flagged), PARAMS)

    year_list = [row["year"] for row in result.yearly]
    trends = {
        metric: analyze_trend(
            year_list,
            [row[metric] for row in result.yearly],
            set(flagged),
            req.start_year,
            req.end_year,
            allow_pct=metric in PCT_METRICS,
        ).to_dict()
        for metric in METRIC_KEYS
    }
    sources = sorted({source for s in stored for source in s.sources})
    insights, caveats = build_insights(
        req.region.label, req.start_year, req.end_year, result.yearly, trends, sources, len(points), flagged
    )

    selected = cleaned.tmax.loc[f"{req.start_year}-01-01":f"{req.end_year}-12-31"]
    now = datetime.now(UTC)
    bbox = None
    if isinstance(req.region, BoxRegion):
        bbox = {"south": req.region.south, "west": req.region.west, "north": req.region.north, "east": req.region.east}
    return {
        "_id": aid,
        "hazard": req.hazard,
        "algo_version": ALGO_VERSION,
        "region": {"type": req.region.type, "label": req.region.label, "bbox": bbox, "points": [list(p) for p in points]},
        "sources_used": sources,
        "years": {"start": req.start_year, "end": req.end_year},
        "params": {
            "percentile": PARAMS.percentile,
            "min_days": PARAMS.min_days,
            "window": PARAMS.window_days,
            "baseline": list(PARAMS.baseline),
        },
        "yearly": result.yearly,
        "events": [e.to_dict() for e in result.events],
        "threshold_by_doy": result.thresholds,
        "trends": trends,
        "insights": insights,
        "caveats": caveats,
        "data_quality": {
            "days": int(selected.notna().sum()),
            "removed": cleaned.removed,
            "interpolated": cleaned.interpolated,
            "low_quality_years": flagged,
        },
        "created_at": now,
        "expires_at": now + timedelta(days=settings.analysis_ttl_days),
    }


def build_chart(doc: dict) -> dict:
    years = [row["year"] for row in doc["yearly"]]
    series = {}
    for metric in METRIC_KEYS:
        values = [row[metric] for row in doc["yearly"]]
        trend = doc["trends"][metric]
        if trend["ols_slope"] is None:
            trendline = [None] * len(years)
        else:
            trendline = [round(trend["ols_slope"] * y + trend["ols_intercept"], 2) for y in years]
        series[metric] = {"values": values, "rolling5": rolling_mean(values), "trendline": trendline}
    return {"years": years, "series": series}


def to_response(doc: dict, cached: bool, label: str) -> dict:
    out = {k: v for k, v in doc.items() if k not in ("_id", "expires_at")}
    out["id"] = doc["_id"]
    out["cached"] = cached
    out["region"] = {**doc["region"], "label": label}
    out["chart"] = build_chart(doc)
    return out
```

- [ ] **Step 6: Implement routes and register router**

`backend/app/api/analyze.py`:
```python
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response

from app.deps import get_db, get_upstream
from app.models import AnalysisOut, AnalyzeRequest
from app.ratelimit import ANALYZE_LIMIT, READ_LIMIT, limiter
from app.services.analysis import get_analysis, get_or_create_analysis

router = APIRouter(tags=["analysis"])

CACHE_CONTROL = "public, max-age=86400"
AnalysisId = Annotated[str, Path(pattern=r"^[0-9a-f]{64}$", description="Analysis id (sha256 hex)")]


@router.post("/analyze", response_model=AnalysisOut)
@limiter.limit(ANALYZE_LIMIT)
async def analyze(request: Request, body: AnalyzeRequest, db=Depends(get_db), upstream=Depends(get_upstream)):
    state = request.app.state
    return await get_or_create_analysis(db, upstream, state.locks, state.settings, body)


@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
@limiter.limit(READ_LIMIT)
async def read_analysis(request: Request, response: Response, analysis_id: AnalysisId, db=Depends(get_db)):
    response.headers["Cache-Control"] = CACHE_CONTROL
    return await get_analysis(db, analysis_id)
```

In `backend/app/main.py` change the import line to `from app.api import analyze, meta` and add after the meta router:
```python
    app.include_router(analyze.router, prefix="/api")
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_api_analyze.py -v`
Expected: 16 passed (12 named tests + 4 parametrized cases). If `test_warming_data_produces_significant_increase` fails, inspect `data["yearly"]` HWF values; the synthetic warming in `tests/fakes.py` (`0.05 * (d.year - 1981)`) may be raised to `0.08` — that is a fixture tweak, not a logic change.

- [ ] **Step 8: Run the whole backend suite**

Run: `cd backend && uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add backend/app backend/tests/test_api_analyze.py
git commit -m "feat(backend): add cached ingest with provider fallback and analysis endpoints"
```

---

### Task 9: Geocoding and hazard list endpoints

**Files:**
- Create: `backend/app/services/geocode.py`, `backend/app/api/geocode.py`
- Modify: `backend/app/api/meta.py` (add `/hazards`), `backend/app/models.py` (geocode response models), `backend/app/main.py` (include router)
- Test: `backend/tests/test_api_geocode.py`

**Interfaces:**
- Consumes: `search_cities`, `search_states`, `MAX_BOX_DEGREES`, `BadRequestError`, `GEOCODE_LIMIT`, `READ_LIMIT`.
- Produces: `clip_box(bbox: dict, max_deg=MAX_BOX_DEGREES) -> tuple[dict, bool]`; `geocode(db, upstream, settings, q, kind) -> list[dict]`; `GET /api/geocode?q=&kind=city|state` → `{"results": [GeocodeResult]}` where `GeocodeResult = {kind, name, label, lat, lon, bbox|null, clipped}`; `GET /api/hazards` → `{"hazards": [...], "years": {"min": 1981, "max": last_complete_year()}}`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_api_geocode.py`:
```python
import httpx
import respx

from app.clients.nominatim import NOMINATIM_URL
from app.clients.openmeteo import GEOCODE_URL
from app.config import last_complete_year
from app.services.geocode import clip_box

CITY_BODY = {"results": [{"name": "Delhi", "latitude": 28.65, "longitude": 77.23, "country": "India"}]}
STATE_BODY = [{"name": "Rajasthan", "display_name": "Rajasthan, India", "lat": "26.81", "lon": "73.77",
               "boundingbox": ["23.0586612", "30.1982530", "69.4844368", "78.2720089"]}]


def test_clip_box_shrinks_large_boxes_around_centre():
    box, clipped = clip_box({"south": 23.0, "west": 69.0, "north": 31.0, "east": 79.0})
    assert clipped is True
    assert box == {"south": 24.5, "west": 71.5, "north": 29.5, "east": 76.5}


def test_clip_box_keeps_small_boxes():
    box, clipped = clip_box({"south": 1.0, "west": 2.0, "north": 3.0, "east": 4.0})
    assert clipped is False
    assert box == {"south": 1.0, "west": 2.0, "north": 3.0, "east": 4.0}


@respx.mock
def test_city_search_is_cached(client, mongo):
    route = respx.get(GEOCODE_URL).mock(return_value=httpx.Response(200, json=CITY_BODY))
    first = client.get("/api/geocode", params={"q": "Delhi", "kind": "city"})
    second = client.get("/api/geocode", params={"q": "  delhi ", "kind": "city"})
    assert first.status_code == 200
    assert first.json()["results"][0]["label"] == "Delhi, India"
    assert second.json() == first.json()
    assert route.call_count == 1


@respx.mock
def test_state_search_returns_clipped_box(client):
    respx.get(NOMINATIM_URL).mock(return_value=httpx.Response(200, json=STATE_BODY))
    result = client.get("/api/geocode", params={"q": "Rajasthan", "kind": "state"}).json()["results"][0]
    assert result["kind"] == "state"
    assert result["clipped"] is True
    bbox = result["bbox"]
    assert round(bbox["north"] - bbox["south"], 6) == 5.0
    assert round(bbox["east"] - bbox["west"], 6) == 5.0


def test_geocode_validates_query(client):
    assert client.get("/api/geocode", params={"q": " a ", "kind": "city"}).status_code == 422
    assert client.get("/api/geocode", params={"q": "x" * 101, "kind": "city"}).status_code == 422
    assert client.get("/api/geocode", params={"q": "Delhi", "kind": "country"}).status_code == 422


def test_hazards_lists_heatwave_and_year_range(client):
    data = client.get("/api/hazards").json()
    assert data["years"] == {"min": 1981, "max": last_complete_year()}
    statuses = {h["id"]: h["status"] for h in data["hazards"]}
    assert statuses["heatwave"] == "available"
    assert statuses["heavy_rainfall"] == "coming_soon"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_api_geocode.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.geocode'`.

- [ ] **Step 3: Implement**

Append to `backend/app/models.py`:
```python
class BBox(BaseModel):
    south: float
    west: float
    north: float
    east: float


class GeocodeResult(BaseModel):
    kind: Literal["city", "state"]
    name: str
    label: str
    lat: float
    lon: float
    bbox: BBox | None
    clipped: bool


class GeocodeResponse(BaseModel):
    results: list[GeocodeResult]
```

`backend/app/services/geocode.py`:
```python
from datetime import UTC, datetime, timedelta
from typing import Literal

from pymongo.asynchronous.database import AsyncDatabase

from app.clients.http import UpstreamClient
from app.clients.nominatim import search_states
from app.clients.openmeteo import search_cities
from app.config import Settings
from app.models import MAX_BOX_DEGREES


def clip_box(bbox: dict, max_deg: float = MAX_BOX_DEGREES) -> tuple[dict, bool]:
    """Shrink a box to at most max_deg x max_deg around its centre."""
    south, west, north, east = bbox["south"], bbox["west"], bbox["north"], bbox["east"]
    clipped = False
    if north - south > max_deg:
        centre = (north + south) / 2
        south, north = max(-90.0, centre - max_deg / 2), min(90.0, centre + max_deg / 2)
        clipped = True
    if east - west > max_deg:
        centre = (east + west) / 2
        west, east = max(-180.0, centre - max_deg / 2), min(180.0, centre + max_deg / 2)
        clipped = True
    box = {"south": round(south, 4), "west": round(west, 4), "north": round(north, 4), "east": round(east, 4)}
    return box, clipped


async def geocode(
    db: AsyncDatabase, upstream: UpstreamClient, settings: Settings, q: str, kind: Literal["city", "state"]
) -> list[dict]:
    key = f"{kind}:{' '.join(q.lower().split())}"
    cached = await db.geocode_cache.find_one({"_id": key})
    if cached is not None:
        return cached["results"]

    if kind == "city":
        results = await search_cities(upstream, q)
    else:
        results = []
        for state in await search_states(upstream, q):
            box, clipped = clip_box(state["bbox"])
            results.append({**state, "kind": "state", "bbox": box, "clipped": clipped})

    expires_at = datetime.now(UTC) + timedelta(days=settings.geocode_ttl_days)
    await db.geocode_cache.replace_one({"_id": key}, {"results": results, "expires_at": expires_at}, upsert=True)
    return results
```

`backend/app/api/geocode.py`:
```python
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from app.deps import get_db, get_upstream
from app.errors import BadRequestError
from app.models import GeocodeResponse
from app.ratelimit import GEOCODE_LIMIT, limiter
from app.services.geocode import geocode

router = APIRouter(tags=["geocode"])


@router.get("/geocode", response_model=GeocodeResponse)
@limiter.limit(GEOCODE_LIMIT)
async def search_places(
    request: Request,
    q: str = Query(max_length=100, description="Place name"),
    kind: Literal["city", "state"] = "city",
    db=Depends(get_db),
    upstream=Depends(get_upstream),
):
    q = q.strip()
    if len(q) < 2:
        raise BadRequestError("Search text must be at least 2 characters.")
    return {"results": await geocode(db, upstream, request.app.state.settings, q, kind)}
```

In `backend/app/api/meta.py` add (keep the existing health route):
```python
from fastapi import Request

from app.config import DATA_START_YEAR, last_complete_year
from app.ratelimit import READ_LIMIT, limiter

HAZARDS = [
    {
        "id": "heatwave",
        "name": "Heatwave",
        "status": "available",
        "definition": "3+ consecutive days with daily maximum temperature above the local 95th percentile "
        "(1981–2010 baseline, ±7-day window).",
    },
    {"id": "heavy_rainfall", "name": "Heavy rainfall", "status": "coming_soon", "definition": None},
    {"id": "drought", "name": "Drought", "status": "coming_soon", "definition": None},
]


@router.get("/hazards")
@limiter.limit(READ_LIMIT)
async def hazards(request: Request):
    return {"hazards": HAZARDS, "years": {"min": DATA_START_YEAR, "max": last_complete_year()}}
```

In `backend/app/main.py`: `from app.api import analyze, geocode, meta` and `app.include_router(geocode.router, prefix="/api")`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_api_geocode.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests/test_api_geocode.py
git commit -m "feat(backend): add cached city/state geocoding and hazard list endpoints"
```

---

### Task 10: Security and performance checks (rate limits, proxy IPs, CORS, gzip)

**Files:**
- Test: `backend/tests/test_security.py`
- Modify (only if a test exposes a gap): `backend/app/ratelimit.py`, `backend/app/main.py`

**Interfaces:**
- Consumes: `client_ip`, `limiter`, `create_app`, `Settings`.
- Produces: no new code interfaces; verifies behaviour.

- [ ] **Step 1: Write the tests**

`backend/tests/test_security.py`:
```python
from types import SimpleNamespace

from starlette.requests import Request

from app.ratelimit import client_ip


def make_request(hops: int, forwarded: str | None, peer: str = "10.0.0.1") -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    app = SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(trusted_proxy_hops=hops)))
    scope = {"type": "http", "headers": headers, "client": (peer, 1234), "app": app}
    return Request(scope)


def test_client_ip_uses_peer_when_no_trusted_proxy():
    assert client_ip(make_request(0, "1.2.3.4")) == "10.0.0.1"


def test_client_ip_ignores_spoofed_left_entries():
    # Client sent "6.6.6.6"; the trusted proxy appended the real address.
    assert client_ip(make_request(1, "6.6.6.6, 203.0.113.9")) == "203.0.113.9"


def test_client_ip_falls_back_to_peer_when_header_too_short():
    assert client_ip(make_request(2, "203.0.113.9")) == "10.0.0.1"


def test_rate_limit_returns_429_with_retry_after(client):
    for _ in range(60):
        assert client.get("/api/hazards").status_code == 200
    response = client.get("/api/hazards")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert response.json()["error"]["code"] == "RATE_LIMITED"


def test_cors_allows_configured_origin_only(client):
    allowed = client.options(
        "/api/analyze",
        headers={"Origin": "http://allowed.test", "Access-Control-Request-Method": "POST"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://allowed.test"
    blocked = client.options(
        "/api/analyze",
        headers={"Origin": "http://evil.test", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in blocked.headers


def test_large_responses_are_gzipped(client):
    response = client.get("/openapi.json", headers={"Accept-Encoding": "gzip"})
    assert response.headers.get("content-encoding") == "gzip"
```

- [ ] **Step 2: Run tests**

Run: `cd backend && uv run pytest tests/test_security.py -v`
Expected: 6 passed (the behaviour was built in Tasks 1, 8 and 9). If any fail, fix the code in `ratelimit.py`/`main.py` until they pass.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_security.py backend/app
git commit -m "test(backend): cover rate limiting, proxy-aware client IPs, CORS and gzip"
```

---

### Task 11: CSV and PDF export

**Files:**
- Create: `backend/app/services/export.py`
- Modify: `backend/app/api/analyze.py` (two routes)
- Test: `backend/tests/test_export.py`

**Interfaces:**
- Consumes: `get_analysis(db, id) -> dict` (response-shaped dict incl. `chart`), `EXPORT_LIMIT`, `CACHE_CONTROL`, `AnalysisId`.
- Produces: `to_csv(analysis: dict) -> str`; `to_pdf(analysis: dict) -> bytes`; routes `GET /api/analyses/{id}/export.csv` and `GET /api/analyses/{id}/report.pdf`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_export.py`:
```python
import pytest
import respx

from app.clients.power import POWER_URL
from tests.fakes import power_responder

BODY = {"region": {"type": "point", "lat": 28.61, "lon": 77.21, "label": "Delhi"}, "start_year": 1990, "end_year": 2020}


@pytest.fixture
def analysis_id(client):
    with respx.mock:
        respx.get(POWER_URL).mock(side_effect=power_responder())
        return client.post("/api/analyze", json=BODY).json()["id"]


def test_csv_export_has_yearly_and_event_sections(client, analysis_id):
    response = client.get(f"/api/analyses/{analysis_id}/export.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    lines = response.text.splitlines()
    assert lines[0] == "# Heatwave analysis: Delhi, 1990-2020"
    assert "year,HWN,HWF,HWD,HWM,HWA,low_quality" in lines
    assert "start,end,days,peak_tmax,mean_exceedance" in lines
    assert sum(1 for line in lines if line[:4].isdigit() and line[4] == ",") == 31


def test_pdf_report_is_a_pdf(client, analysis_id):
    response = client.get(f"/api/analyses/{analysis_id}/report.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_export_of_unknown_analysis_is_404(client):
    assert client.get("/api/analyses/" + "a" * 64 + "/export.csv").status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_export.py -v`
Expected: FAIL — 404 for the export routes.

- [ ] **Step 3: Implement**

`backend/app/services/export.py`:
```python
import csv
import io
import textwrap

import matplotlib

matplotlib.use("Agg")  # headless backend; must be set before pyplot is imported

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

YEARLY_FIELDS = ["year", "HWN", "HWF", "HWD", "HWM", "HWA", "low_quality"]
EVENT_FIELDS = ["start", "end", "days", "peak_tmax", "mean_exceedance"]


def to_csv(analysis: dict) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    years = analysis["years"]
    out.write(f"# Heatwave analysis: {analysis['region']['label']}, {years['start']}-{years['end']}\n")
    for sentence in analysis["insights"]:
        out.write(f"# {sentence}\n")
    out.write("\n")
    writer.writerow(YEARLY_FIELDS)
    for row in analysis["yearly"]:
        writer.writerow(["" if row[f] is None else row[f] for f in YEARLY_FIELDS])
    out.write("\n")
    writer.writerow(EVENT_FIELDS)
    for event in analysis["events"]:
        writer.writerow([str(event[f]) for f in EVENT_FIELDS])
    return out.getvalue()


def _plot_metric(ax, chart: dict, metric: str, title: str, unit: str) -> None:
    years = chart["years"]
    series = chart["series"][metric]
    ax.bar(years, [v or 0 for v in series["values"]], color="#e8743b", label=title)
    ax.plot(years, series["rolling5"], color="#7a2e0e", linewidth=2, label="5-year average")
    if any(v is not None for v in series["trendline"]):
        ax.plot(years, series["trendline"], color="#333333", linestyle="--", label="Linear trend")
    ax.set_title(title)
    ax.set_ylabel(unit)
    ax.legend(loc="upper left", fontsize=8)


def to_pdf(analysis: dict) -> bytes:
    buffer = io.BytesIO()
    years = analysis["years"]
    with PdfPages(buffer) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))  # A4 portrait
        lines = [f"Heatwave analysis — {analysis['region']['label']}", f"{years['start']}–{years['end']}", ""]
        lines += ["Insights:"] + [f"• {w}" for s in analysis["insights"] for w in textwrap.wrap(s, 95)]
        lines += ["", "Caveats:"] + [f"– {w}" for c in analysis["caveats"] for w in textwrap.wrap(c, 95)]
        fig.text(0.06, 0.95, "\n".join(lines), va="top", fontsize=9, family="DejaVu Sans")
        pdf.savefig(fig)
        plt.close(fig)

        fig, axes = plt.subplots(2, 1, figsize=(8.27, 11.69))
        _plot_metric(axes[0], analysis["chart"], "HWF", "Heatwave days per year", "days")
        _plot_metric(axes[1], analysis["chart"], "HWN", "Heatwave events per year", "events")
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)
    return buffer.getvalue()
```

Append to `backend/app/api/analyze.py`:
```python
from app.ratelimit import EXPORT_LIMIT  # add to the existing ratelimit import
from app.services.export import to_csv, to_pdf


@router.get("/analyses/{analysis_id}/export.csv")
@limiter.limit(EXPORT_LIMIT)
async def export_csv(request: Request, analysis_id: AnalysisId, db=Depends(get_db)):
    analysis = await get_analysis(db, analysis_id)
    return Response(
        content=to_csv(analysis),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="heatwave-{analysis_id[:8]}.csv"',
            "Cache-Control": CACHE_CONTROL,
        },
    )


@router.get("/analyses/{analysis_id}/report.pdf")
@limiter.limit(EXPORT_LIMIT)
async def export_pdf(request: Request, analysis_id: AnalysisId, db=Depends(get_db)):
    analysis = await get_analysis(db, analysis_id)
    return Response(
        content=to_pdf(analysis),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="heatwave-{analysis_id[:8]}.pdf"',
            "Cache-Control": CACHE_CONTROL,
        },
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_export.py -v && uv run pytest -q`
Expected: 3 passed, then the full suite passes.

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests/test_export.py
git commit -m "feat(backend): add CSV and PDF export of analyses"
```

---

### Task 12: Seed script and manual end-to-end check against real APIs

**Files:**
- Create: `backend/scripts/__init__.py`, `backend/scripts/seed.py`

**Interfaces:**
- Consumes: the running API (`POST /api/analyze`).
- Produces: `python -m scripts.seed --api <base url>` pre-warms demo cities.

- [ ] **Step 1: Implement the seed script**

`backend/scripts/__init__.py`: empty.

`backend/scripts/seed.py`:
```python
"""Pre-warm the cache for demo cities by calling the public API.

Usage: uv run python -m scripts.seed --api http://localhost:8000
"""

import argparse
import time

import httpx

DEMO_REGIONS = [
    {"type": "point", "lat": 28.61, "lon": 77.21, "label": "Delhi, India"},
    {"type": "point", "lat": 33.45, "lon": -112.07, "label": "Phoenix, United States"},
    {"type": "point", "lat": 48.86, "lon": 2.35, "label": "Paris, France"},
    {"type": "point", "lat": -33.87, "lon": 151.21, "label": "Sydney, Australia"},
    {"type": "point", "lat": 6.52, "lon": 3.38, "label": "Lagos, Nigeria"},
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--start", type=int, default=1990)
    parser.add_argument("--end", type=int, default=2020)
    args = parser.parse_args()

    with httpx.Client(base_url=args.api, timeout=120) as client:
        for region in DEMO_REGIONS:
            body = {"hazard": "heatwave", "region": region, "start_year": args.start, "end_year": args.end}
            started = time.monotonic()
            response = client.post("/api/analyze", json=body)
            took = time.monotonic() - started
            if response.status_code == 200:
                data = response.json()
                print(f"OK   {region['label']:<28} cached={data['cached']!s:<5} {took:5.1f}s  {data['insights'][0][:70]}")
            else:
                print(f"FAIL {region['label']:<28} HTTP {response.status_code}: {response.text[:120]}")
            time.sleep(7)  # stay under the 10/minute analyze limit


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the API against real providers and seed**

Run (two terminals):
```bash
cd backend && cp -n .env.example .env && uv run uvicorn app.main:app --port 8000
cd backend && uv run python -m scripts.seed --api http://localhost:8000
```
Expected: 5 `OK` lines, each first-time call a few seconds; re-running prints `cached=True` and < 1 s each. Then check `http://localhost:8000/docs` loads, and `curl "http://localhost:8000/api/geocode?q=Rajasthan&kind=state"` returns a clipped box. Record any real-data surprises (e.g. unexpected `-999` runs) as README assumptions.

- [ ] **Step 3: Commit**

```bash
git add backend/scripts
git commit -m "feat(backend): add demo-city seed script"
```

---

### Task 13: Frontend scaffold, API client, types and pure helpers

**Files:**
- Create: `frontend/` (Vite scaffold), `frontend/.env.example`, `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/lib/urlState.ts`, `frontend/src/lib/format.ts`, `frontend/src/lib/region.ts`, `frontend/src/lib/useDebouncedValue.ts`
- Modify: `frontend/vite.config.ts` (Vitest config), `frontend/package.json` (test script)
- Test: `frontend/src/lib/urlState.test.ts`, `frontend/src/lib/format.test.ts`, `frontend/src/lib/region.test.ts`

**Interfaces:**
- Consumes: backend JSON contracts from Tasks 8–9.
- Produces: TS types `MetricKey, PointRegion, BoxRegion, Region, Selection, AnalyzeSelection, YearlyRow, HeatwaveEvent, Trend, ChartSeries, Analysis, GeocodeResult, HazardInfo, MetaResponse, Bounds`; `ApiError(status, code, message, retryAfter, details)`; `api.meta()`, `api.geocode(q, kind, signal?)`, `api.analyze(selection)`, `api.exportUrl(id, kind)`; `DEFAULT_SELECTION`, `selectionToParams(sel)`, `paramsToSelection(params)`; `formatChange(trend, unit)`, `formatP(p)`, `trendBadge(trend)`, `mean(values)`; `MAX_BOX_DEGREES`, `wrapLon(lon)`, `boundsFrom(a, b)`, `boxProblem(region)`, `selectionProblem(sel, minYear, maxYear)`; `useDebouncedValue(value, ms)`.

- [ ] **Step 1: Scaffold and install**

```bash
cd /home/akshit/prudent-assignment
npm create vite@latest frontend -- --template react-ts   # answer "No" if asked to install/start now
cd frontend
npm install
npm install @tanstack/react-query chart.js react-chartjs-2 leaflet react-leaflet
npm install -D vitest @types/leaflet
rm -f src/App.css src/assets/react.svg public/vite.svg
```
`frontend/.env.example`:
```dotenv
VITE_API_BASE_URL=http://localhost:8000
```
Add to `package.json` `"scripts"`: `"test": "vitest run"`.

Replace `frontend/vite.config.ts`:
```ts
/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: { environment: 'node' },
})
```

- [ ] **Step 2: Write the failing tests**

`frontend/src/lib/urlState.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import { DEFAULT_SELECTION, paramsToSelection, selectionToParams } from './urlState'
import type { Selection } from '../api/types'

describe('url state', () => {
  it('round-trips a point selection', () => {
    const sel: Selection = {
      hazard: 'heatwave',
      region: { type: 'point', lat: 28.61, lon: 77.21, label: 'Delhi, India' },
      startYear: 1990,
      endYear: 2020,
    }
    expect(paramsToSelection(selectionToParams(sel))).toEqual(sel)
  })

  it('round-trips a box selection', () => {
    const sel: Selection = {
      hazard: 'heatwave',
      region: { type: 'box', south: 20, west: 70, north: 25, east: 75, label: 'Custom box' },
      startYear: 2000,
      endYear: 2010,
    }
    expect(paramsToSelection(selectionToParams(sel))).toEqual(sel)
  })

  it('falls back to defaults for garbage', () => {
    const params = new URLSearchParams('type=point&lat=abc&lon=1&from=x&to=2020')
    expect(paramsToSelection(params)).toEqual({ ...DEFAULT_SELECTION, endYear: 2020 })
  })
})
```

`frontend/src/lib/format.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import { formatChange, formatP, mean, trendBadge } from './format'
import type { Trend } from '../api/types'

const base: Trend = {
  n_years: 30, sen_per_decade: 4.2, mk_p: 0.003, significant: true, ols_slope: 0.4,
  ols_intercept: -800, change_kind: 'pct', change_value: 120, reason: null,
}

describe('format', () => {
  it('formats percent and absolute changes', () => {
    expect(formatChange(base, 'days')).toBe('+120%')
    expect(formatChange({ ...base, change_kind: 'abs', change_value: -2.34 }, 'days')).toBe('−2.3 days')
    expect(formatChange({ ...base, change_kind: null, change_value: null }, 'days')).toBe('—')
  })

  it('formats p-values', () => {
    expect(formatP(0.0004)).toBe('p < 0.001')
    expect(formatP(0.0312)).toBe('p = 0.031')
    expect(formatP(null)).toBe('—')
  })

  it('labels trend badges', () => {
    expect(trendBadge(base)).toEqual({ label: '▲ Significant increase', tone: 'up' })
    expect(trendBadge({ ...base, sen_per_decade: -1 })).toEqual({ label: '▼ Significant decrease', tone: 'down' })
    expect(trendBadge({ ...base, significant: false })).toEqual({ label: 'No significant trend', tone: 'flat' })
    expect(trendBadge({ ...base, reason: 'insufficient_years' })).toEqual({ label: 'Not enough years', tone: 'na' })
  })

  it('averages ignoring nulls', () => {
    expect(mean([1, null, 3])).toBe(2)
    expect(mean([null])).toBeNull()
  })
})
```

`frontend/src/lib/region.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import { boundsFrom, boxProblem, selectionProblem, wrapLon } from './region'

describe('region helpers', () => {
  it('wraps longitudes into [-180, 180)', () => {
    expect(wrapLon(190)).toBe(-170)
    expect(wrapLon(-181)).toBe(179)
    expect(wrapLon(45)).toBe(45)
  })

  it('builds rounded bounds from two corners in any order', () => {
    expect(boundsFrom({ lat: 25.123, lng: 75.456 }, { lat: 20.001, lng: 70.009 })).toEqual({
      south: 20, west: 70.01, north: 25.12, east: 75.46,
    })
  })

  it('reports box problems', () => {
    expect(boxProblem({ type: 'box', south: 0, west: 0, north: 6, east: 1, label: 'b' })).toMatch(/at most 5°/)
    expect(boxProblem({ type: 'box', south: 2, west: 0, north: 1, east: 1, label: 'b' })).toMatch(/north/)
    expect(boxProblem({ type: 'box', south: 0, west: 0, north: 5, east: 5, label: 'b' })).toBeNull()
    expect(boxProblem({ type: 'point', lat: 0, lon: 0, label: 'p' })).toBeNull()
  })

  it('reports selection problems', () => {
    const region = { type: 'point' as const, lat: 0, lon: 0, label: 'p' }
    expect(selectionProblem({ hazard: 'heatwave', region: null, startYear: 1990, endYear: 2020 }, 1981, 2025)).toMatch(/region/)
    expect(selectionProblem({ hazard: 'heatwave', region, startYear: 2020, endYear: 1990 }, 1981, 2025)).toMatch(/Start year/)
    expect(selectionProblem({ hazard: 'heatwave', region, startYear: 1970, endYear: 1990 }, 1981, 2025)).toMatch(/1981/)
    expect(selectionProblem({ hazard: 'heatwave', region, startYear: 1990, endYear: 2020 }, 1981, 2025)).toBeNull()
  })
})
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd frontend && npm test`
Expected: FAIL — cannot resolve `./urlState`, `./format`, `./region`.

- [ ] **Step 4: Implement**

`frontend/src/api/types.ts`:
```ts
export type MetricKey = 'HWN' | 'HWF' | 'HWD' | 'HWM' | 'HWA'

export type PointRegion = { type: 'point'; lat: number; lon: number; label: string }
export type BoxRegion = { type: 'box'; south: number; west: number; north: number; east: number; label: string }
export type Region = PointRegion | BoxRegion
export type Bounds = { south: number; west: number; north: number; east: number }

export type Selection = { hazard: 'heatwave'; region: Region | null; startYear: number; endYear: number }
export type AnalyzeSelection = Selection & { region: Region }

export type YearlyRow = {
  year: number; HWN: number; HWF: number; HWD: number; HWM: number | null; HWA: number | null; low_quality: boolean
}
export type HeatwaveEvent = { start: string; end: string; days: number; peak_tmax: number; mean_exceedance: number }
export type Trend = {
  n_years: number
  sen_per_decade: number | null
  mk_p: number | null
  significant: boolean
  ols_slope: number | null
  ols_intercept: number | null
  change_kind: 'pct' | 'abs' | null
  change_value: number | null
  reason: string | null
}
export type ChartSeries = { values: (number | null)[]; rolling5: (number | null)[]; trendline: (number | null)[] }

export type Analysis = {
  id: string
  cached: boolean
  hazard: string
  algo_version: string
  region: { type: 'point' | 'box'; label: string; bbox: Bounds | null; points: number[][] }
  sources_used: string[]
  years: { start: number; end: number }
  params: { percentile: number; min_days: number; window: number; baseline: number[] }
  yearly: YearlyRow[]
  events: HeatwaveEvent[]
  threshold_by_doy: (number | null)[]
  trends: Record<MetricKey, Trend>
  insights: string[]
  caveats: string[]
  data_quality: { days: number; removed: number; interpolated: number; low_quality_years: number[] }
  chart: { years: number[]; series: Record<MetricKey, ChartSeries> }
  created_at: string
}

export type GeocodeResult = {
  kind: 'city' | 'state'; name: string; label: string; lat: number; lon: number; bbox: Bounds | null; clipped: boolean
}
export type HazardInfo = { id: string; name: string; status: 'available' | 'coming_soon'; definition: string | null }
export type MetaResponse = { hazards: HazardInfo[]; years: { min: number; max: number } }
```

`frontend/src/api/client.ts`:
```ts
import type { Analysis, AnalyzeSelection, GeocodeResult, MetaResponse } from './types'

const BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  status: number
  code: string
  retryAfter: number | null
  details: string[]

  constructor(status: number, code: string, message: string, retryAfter: number | null, details: string[] = []) {
    super(message)
    this.status = status
    this.code = code
    this.retryAfter = retryAfter
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, init)
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError(0, 'NETWORK_ERROR', 'Could not reach the server. Check your connection and try again.', null)
  }
  if (!response.ok) {
    let code = `HTTP_${response.status}`
    let message = `Request failed (${response.status}).`
    let details: string[] = []
    try {
      const body = await response.json()
      if (body?.error) {
        code = body.error.code
        message = body.error.message
        details = (body.error.details ?? []).map((d: { msg: string }) => d.msg)
      }
    } catch {
      // non-JSON error body; keep the generic message
    }
    const retryAfter = response.headers.get('Retry-After')
    throw new ApiError(response.status, code, message, retryAfter ? Number(retryAfter) : null, details)
  }
  return (await response.json()) as T
}

export const api = {
  meta: () => request<MetaResponse>('/api/hazards'),
  geocode: (q: string, kind: 'city' | 'state', signal?: AbortSignal) =>
    request<{ results: GeocodeResult[] }>(`/api/geocode?${new URLSearchParams({ q, kind })}`, { signal }),
  analyze: (sel: AnalyzeSelection) =>
    request<Analysis>('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hazard: sel.hazard, region: sel.region, start_year: sel.startYear, end_year: sel.endYear }),
    }),
  exportUrl: (id: string, kind: 'csv' | 'pdf') =>
    `${BASE}/api/analyses/${id}/${kind === 'csv' ? 'export.csv' : 'report.pdf'}`,
}
```

`frontend/src/lib/urlState.ts`:
```ts
import type { Region, Selection } from '../api/types'

export const DEFAULT_SELECTION: Selection = { hazard: 'heatwave', region: null, startYear: 1990, endYear: 2020 }

export function selectionToParams(sel: Selection): URLSearchParams {
  const p = new URLSearchParams({ hazard: sel.hazard, from: String(sel.startYear), to: String(sel.endYear) })
  const r = sel.region
  if (r?.type === 'point') {
    p.set('type', 'point'); p.set('lat', String(r.lat)); p.set('lon', String(r.lon)); p.set('label', r.label)
  } else if (r?.type === 'box') {
    p.set('type', 'box'); p.set('s', String(r.south)); p.set('w', String(r.west))
    p.set('n', String(r.north)); p.set('e', String(r.east)); p.set('label', r.label)
  }
  return p
}

function num(params: URLSearchParams, key: string): number | null {
  const raw = params.get(key)
  if (raw === null || raw.trim() === '') return null
  const value = Number(raw)
  return Number.isFinite(value) ? value : null
}

export function paramsToSelection(params: URLSearchParams): Selection {
  const label = (params.get('label') ?? '').slice(0, 100)
  let region: Region | null = null
  if (params.get('type') === 'point') {
    const lat = num(params, 'lat')
    const lon = num(params, 'lon')
    if (lat !== null && lon !== null) region = { type: 'point', lat, lon, label: label || 'Selected point' }
  } else if (params.get('type') === 'box') {
    const [south, west, north, east] = ['s', 'w', 'n', 'e'].map((k) => num(params, k))
    if (south !== null && west !== null && north !== null && east !== null) {
      region = { type: 'box', south, west, north, east, label: label || 'Custom box' }
    }
  }
  return {
    hazard: 'heatwave',
    region,
    startYear: num(params, 'from') ?? DEFAULT_SELECTION.startYear,
    endYear: num(params, 'to') ?? DEFAULT_SELECTION.endYear,
  }
}
```

`frontend/src/lib/format.ts`:
```ts
import type { Trend } from '../api/types'

const MINUS = '−'

export function formatChange(trend: Trend, unit: string): string {
  if (trend.change_kind === null || trend.change_value === null) return '—'
  const v = trend.change_value
  const sign = v > 0 ? '+' : v < 0 ? MINUS : ''
  if (trend.change_kind === 'pct') return `${sign}${Math.abs(Math.round(v))}%`
  return `${sign}${Math.abs(v).toFixed(1)} ${unit}`
}

export function formatP(p: number | null): string {
  if (p === null) return '—'
  return p < 0.001 ? 'p < 0.001' : `p = ${p.toFixed(3)}`
}

export function trendBadge(trend: Trend): { label: string; tone: 'up' | 'down' | 'flat' | 'na' } {
  if (trend.reason || trend.sen_per_decade === null) return { label: 'Not enough years', tone: 'na' }
  if (!trend.significant) return { label: 'No significant trend', tone: 'flat' }
  return trend.sen_per_decade > 0
    ? { label: '▲ Significant increase', tone: 'up' }
    : { label: '▼ Significant decrease', tone: 'down' }
}

export function mean(values: (number | null)[]): number | null {
  const present = values.filter((v): v is number => v !== null)
  return present.length ? present.reduce((a, b) => a + b, 0) / present.length : null
}
```

`frontend/src/lib/region.ts`:
```ts
import type { Bounds, Region, Selection } from '../api/types'

export const MAX_BOX_DEGREES = 5

const round2 = (v: number) => Math.round(v * 100) / 100

export function wrapLon(lon: number): number {
  return ((((lon + 180) % 360) + 360) % 360) - 180
}

export function boundsFrom(a: { lat: number; lng: number }, b: { lat: number; lng: number }): Bounds {
  const clampLat = (v: number) => Math.max(-90, Math.min(90, v))
  return {
    south: round2(clampLat(Math.min(a.lat, b.lat))),
    north: round2(clampLat(Math.max(a.lat, b.lat))),
    west: round2(wrapLon(Math.min(a.lng, b.lng))),
    east: round2(wrapLon(Math.max(a.lng, b.lng))),
  }
}

export function boxProblem(region: Region | null): string | null {
  if (!region || region.type !== 'box') return null
  const height = region.north - region.south
  const width = region.east - region.west
  if (height <= 0 || width <= 0) return 'The box needs north > south and east > west.'
  if (height > MAX_BOX_DEGREES || width > MAX_BOX_DEGREES) {
    return `The box can be at most 5° × 5° (currently ${height.toFixed(1)}° × ${width.toFixed(1)}°).`
  }
  return null
}

export function selectionProblem(sel: Selection, minYear: number, maxYear: number): string | null {
  if (!sel.region) return 'Choose a region: search a city or state, click the map, or draw a box.'
  const box = boxProblem(sel.region)
  if (box) return box
  if (sel.startYear > sel.endYear) return 'Start year must be before or equal to end year.'
  if (sel.startYear < minYear || sel.endYear > maxYear) return `Years must be between ${minYear} and ${maxYear}.`
  return null
}
```

`frontend/src/lib/useDebouncedValue.ts`:
```ts
import { useEffect, useState } from 'react'

export function useDebouncedValue<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return debounced
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npm test`
Expected: 3 files, 11 tests passed.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat(frontend): scaffold Vite React app with API client and tested helpers"
```

---

### Task 14: Frontend controls — hazard, years, region search, map and box drawing

**Files:**
- Create: `frontend/src/components/HazardSelect.tsx`, `YearRange.tsx`, `PlaceSearch.tsx`, `BoxInputs.tsx`, `RegionMap.tsx`, `RegionPicker.tsx`
- Replace: `frontend/src/main.tsx`, `frontend/src/index.css`, `frontend/src/App.tsx` (controls-only version; results added in Task 15)

**Interfaces:**
- Consumes: `api`, types, `useDebouncedValue`, `boundsFrom`, `wrapLon`, `boxProblem`, `selectionProblem`, `paramsToSelection`, `selectionToParams`.
- Produces: `<HazardSelect hazards value onChange/>`, `<YearRange min max start end onChange(start,end)/>`, `<PlaceSearch kind onSelect/>`, `<BoxInputs region onChange/>`, `<RegionMap region mode onPoint onBox/>`, `<RegionPicker region onChange/>`; `App` holds `selection` and `submitted` state.

- [ ] **Step 1: Implement components**

`frontend/src/main.tsx`:
```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import 'leaflet/dist/leaflet.css'
import './index.css'
import App from './App'

const queryClient = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
```

`frontend/src/components/HazardSelect.tsx`:
```tsx
import type { HazardInfo } from '../api/types'

type Props = { hazards: HazardInfo[]; value: string; onChange: (id: 'heatwave') => void }

export function HazardSelect({ hazards, value, onChange }: Props) {
  const options = hazards.length ? hazards : [{ id: 'heatwave', name: 'Heatwave', status: 'available' as const, definition: null }]
  return (
    <label className="field">
      <span className="field-label">Hazard</span>
      <select value={value} onChange={(e) => onChange(e.target.value as 'heatwave')}>
        {options.map((h) => (
          <option key={h.id} value={h.id} disabled={h.status !== 'available'}>
            {h.name}{h.status !== 'available' ? ' (coming soon)' : ''}
          </option>
        ))}
      </select>
    </label>
  )
}
```

`frontend/src/components/YearRange.tsx`:
```tsx
type Props = { min: number; max: number; start: number; end: number; onChange: (start: number, end: number) => void }

export function YearRange({ min, max, start, end, onChange }: Props) {
  const years = Array.from({ length: max - min + 1 }, (_, i) => min + i)
  return (
    <fieldset className="field">
      <legend className="field-label">Years</legend>
      <div className="row">
        <select aria-label="Start year" value={start} onChange={(e) => onChange(Number(e.target.value), end)}>
          {years.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
        <span>–</span>
        <select aria-label="End year" value={end} onChange={(e) => onChange(start, Number(e.target.value))}>
          {years.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>
      {end - start + 1 < 10 && <p className="hint warn">Fewer than 10 years: trends can't be assessed.</p>}
    </fieldset>
  )
}
```

`frontend/src/components/PlaceSearch.tsx`:
```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { GeocodeResult } from '../api/types'
import { useDebouncedValue } from '../lib/useDebouncedValue'

type Props = { kind: 'city' | 'state'; onSelect: (result: GeocodeResult) => void }

export function PlaceSearch({ kind, onSelect }: Props) {
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const q = useDebouncedValue(text.trim(), 350)
  const results = useQuery({
    queryKey: ['geocode', kind, q],
    queryFn: ({ signal }) => api.geocode(q, kind, signal),
    enabled: q.length >= 2,
    staleTime: 5 * 60_000,
    retry: false,
  })

  return (
    <div className="search">
      <input
        type="search"
        value={text}
        maxLength={100}
        aria-label={kind === 'city' ? 'Search city' : 'Search state'}
        placeholder={kind === 'city' ? 'Search a city, e.g. Delhi' : 'Search a state, e.g. Rajasthan'}
        onChange={(e) => { setText(e.target.value); setOpen(true) }}
      />
      {open && q.length >= 2 && (
        <ul className="search-results">
          {results.isFetching && <li className="muted">Searching…</li>}
          {results.error && <li className="error-text">{(results.error as Error).message}</li>}
          {results.data?.results.length === 0 && <li className="muted">No matches</li>}
          {results.data?.results.map((r) => (
            <li key={`${r.label}-${r.lat}-${r.lon}`}>
              <button type="button" onClick={() => { onSelect(r); setText(r.label); setOpen(false) }}>
                {r.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
```

`frontend/src/components/BoxInputs.tsx`:
```tsx
import { useEffect, useState } from 'react'
import type { BoxRegion, Region } from '../api/types'

type Props = { region: Region | null; onChange: (region: BoxRegion) => void }
const KEYS = ['south', 'west', 'north', 'east'] as const

export function BoxInputs({ region, onChange }: Props) {
  const [draft, setDraft] = useState<Record<(typeof KEYS)[number], string>>({ south: '', west: '', north: '', east: '' })

  useEffect(() => {
    if (region?.type === 'box') {
      setDraft({ south: String(region.south), west: String(region.west), north: String(region.north), east: String(region.east) })
    }
  }, [region])

  function update(key: (typeof KEYS)[number], value: string) {
    const next = { ...draft, [key]: value }
    setDraft(next)
    const nums = KEYS.map((k) => Number(next[k]))
    if (KEYS.every((k) => next[k].trim() !== '') && nums.every(Number.isFinite)) {
      const [south, west, north, east] = nums
      onChange({ type: 'box', south, west, north, east, label: 'Custom box' })
    }
  }

  return (
    <div className="box-inputs">
      {KEYS.map((k) => (
        <label key={k}>
          <span>{k}</span>
          <input type="number" step="0.01" value={draft[k]} onChange={(e) => update(k, e.target.value)} />
        </label>
      ))}
    </div>
  )
}
```

`frontend/src/components/RegionMap.tsx`:
```tsx
import { useEffect, useState } from 'react'
import { CircleMarker, MapContainer, Rectangle, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import type { LatLng } from 'leaflet'
import type { Bounds, Region } from '../api/types'
import { boundsFrom, wrapLon } from '../lib/region'

type Props = {
  region: Region | null
  mode: 'city' | 'state' | 'box'
  onPoint: (lat: number, lon: number) => void
  onBox: (bounds: Bounds) => void
}

function FitToRegion({ region }: { region: Region | null }) {
  const map = useMap()
  useEffect(() => {
    if (!region) return
    if (region.type === 'point') map.setView([region.lat, region.lon], Math.max(map.getZoom(), 6))
    else map.fitBounds([[region.south, region.west], [region.north, region.east]], { padding: [20, 20] })
  }, [region, map])
  return null
}

function ClickToPoint({ onPoint }: { onPoint: Props['onPoint'] }) {
  useMapEvents({
    click(e) {
      onPoint(Math.round(e.latlng.lat * 100) / 100, Math.round(wrapLon(e.latlng.lng) * 100) / 100)
    },
  })
  return null
}

function BoxDrawer({ onBox }: { onBox: Props['onBox'] }) {
  const map = useMap()
  const [start, setStart] = useState<LatLng | null>(null)
  const [current, setCurrent] = useState<LatLng | null>(null)

  useEffect(() => {
    map.dragging.disable()
    map.getContainer().style.cursor = 'crosshair'
    return () => {
      map.dragging.enable()
      map.getContainer().style.cursor = ''
    }
  }, [map])

  useMapEvents({
    mousedown(e) { setStart(e.latlng); setCurrent(e.latlng) },
    mousemove(e) { if (start) setCurrent(e.latlng) },
    mouseup(e) {
      if (!start) return
      const bounds = boundsFrom(start, e.latlng)
      setStart(null)
      setCurrent(null)
      if (bounds.north - bounds.south > 0.01 && bounds.east - bounds.west > 0.01) onBox(bounds)
    },
  })

  if (!start || !current) return null
  return <Rectangle bounds={[[start.lat, start.lng], [current.lat, current.lng]]} pathOptions={{ dashArray: '4' }} />
}

export function RegionMap({ region, mode, onPoint, onBox }: Props) {
  return (
    <MapContainer center={[20, 0]} zoom={2} minZoom={2} className="map" worldCopyJump>
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      />
      {region?.type === 'point' && <CircleMarker center={[region.lat, region.lon]} radius={8} />}
      {region?.type === 'box' && <Rectangle bounds={[[region.south, region.west], [region.north, region.east]]} />}
      <FitToRegion region={region} />
      {mode === 'box' ? <BoxDrawer onBox={onBox} /> : <ClickToPoint onPoint={onPoint} />}
    </MapContainer>
  )
}
```

`frontend/src/components/RegionPicker.tsx`:
```tsx
import { useState } from 'react'
import type { Region } from '../api/types'
import { boxProblem } from '../lib/region'
import { BoxInputs } from './BoxInputs'
import { PlaceSearch } from './PlaceSearch'
import { RegionMap } from './RegionMap'

type Mode = 'city' | 'state' | 'box'
type Props = { region: Region | null; onChange: (region: Region) => void }

const TABS: { id: Mode; label: string }[] = [
  { id: 'city', label: 'City' },
  { id: 'state', label: 'State' },
  { id: 'box', label: 'Draw box' },
]

export function RegionPicker({ region, onChange }: Props) {
  const [mode, setMode] = useState<Mode>(region?.type === 'box' ? 'box' : 'city')
  const [note, setNote] = useState<string | null>(null)
  const problem = boxProblem(region)

  return (
    <fieldset className="field">
      <legend className="field-label">Region</legend>
      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={mode === t.id}
            className={mode === t.id ? 'tab active' : 'tab'} onClick={() => { setMode(t.id); setNote(null) }}>
            {t.label}
          </button>
        ))}
      </div>

      {mode === 'city' && (
        <>
          <PlaceSearch kind="city" onSelect={(r) => onChange({ type: 'point', lat: r.lat, lon: r.lon, label: r.label })} />
          <p className="hint">…or click anywhere on the map.</p>
        </>
      )}
      {mode === 'state' && (
        <PlaceSearch
          kind="state"
          onSelect={(r) => {
            if (!r.bbox) return
            onChange({ type: 'box', ...r.bbox, label: r.label })
            setNote(r.clipped ? 'This state is larger than 5° × 5°, so a 5° × 5° box around its centre is analysed.' : null)
          }}
        />
      )}
      {mode === 'box' && (
        <>
          <BoxInputs region={region} onChange={onChange} />
          <p className="hint">Drag on the map to draw a box (max 5° × 5°).</p>
        </>
      )}

      <RegionMap
        region={region}
        mode={mode}
        onPoint={(lat, lon) => onChange({ type: 'point', lat, lon, label: `${lat.toFixed(2)}, ${lon.toFixed(2)}` })}
        onBox={(b) => onChange({ type: 'box', ...b, label: 'Custom box' })}
      />
      {note && <p className="hint">{note}</p>}
      {region && <p className="hint">Selected: <strong>{region.label}</strong></p>}
      {problem && <p className="error-text">{problem}</p>}
    </fieldset>
  )
}
```

`frontend/src/App.tsx` (controls-only for now):
```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from './api/client'
import type { AnalyzeSelection, Selection } from './api/types'
import { HazardSelect } from './components/HazardSelect'
import { RegionPicker } from './components/RegionPicker'
import { YearRange } from './components/YearRange'
import { selectionProblem } from './lib/region'
import { paramsToSelection, selectionToParams } from './lib/urlState'

export default function App() {
  const meta = useQuery({ queryKey: ['meta'], queryFn: api.meta, staleTime: Infinity })
  const minYear = meta.data?.years.min ?? 1981
  const maxYear = meta.data?.years.max ?? new Date().getFullYear() - 1

  const [initial] = useState(() => paramsToSelection(new URLSearchParams(window.location.search)))
  const [selection, setSelection] = useState<Selection>(initial)
  const [submitted, setSubmitted] = useState<AnalyzeSelection | null>(() =>
    initial.region ? { ...initial, region: initial.region } : null,
  )
  const problem = selectionProblem(selection, minYear, maxYear)

  function runAnalysis() {
    if (problem || !selection.region) return
    const next = { ...selection, region: selection.region }
    setSubmitted(next)
    window.history.replaceState(null, '', `?${selectionToParams(next)}`)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Climate Hazard Trend Analyzer</h1>
        <p className="muted">How have heatwaves changed where you live? Data: NASA POWER, 1981 onward.</p>
      </header>
      <main className="layout">
        <aside className="controls">
          <HazardSelect hazards={meta.data?.hazards ?? []} value={selection.hazard} onChange={(hazard) => setSelection({ ...selection, hazard })} />
          <RegionPicker region={selection.region} onChange={(region) => setSelection({ ...selection, region })} />
          <YearRange min={minYear} max={maxYear} start={selection.startYear} end={selection.endYear}
            onChange={(startYear, endYear) => setSelection({ ...selection, startYear, endYear })} />
          <button type="button" className="primary" disabled={problem !== null} onClick={runAnalysis}>Analyze</button>
          {problem && selection.region && <p className="hint">{problem}</p>}
        </aside>
        <section className="results">
          {submitted ? <pre>{JSON.stringify(submitted, null, 2)}</pre> : <p className="muted">Pick a region and press Analyze.</p>}
        </section>
      </main>
    </div>
  )
}
```

`frontend/src/index.css`:
```css
:root {
  --bg: #faf7f2;
  --panel: #ffffff;
  --text: #1f2328;
  --muted: #5f6670;
  --border: #e4ded4;
  --accent: #d9622b;
  --accent-dark: #7a2e0e;
  --up: #b42318;
  --down: #1d6fa5;
  --flat: #5f6670;
  font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  color: var(--text);
  background: var(--bg);
}
* { box-sizing: border-box; }
body { margin: 0; }
h1 { font-size: 1.4rem; margin: 0; }
h2 { font-size: 1.2rem; margin: 0; }
h3 { font-size: 1rem; margin: 0 0 0.5rem; }
button { font: inherit; cursor: pointer; }
select, input { font: inherit; padding: 0.4rem 0.5rem; border: 1px solid var(--border); border-radius: 6px; background: #fff; }

.app { max-width: 1280px; margin: 0 auto; padding: 1rem; }
.app-header { margin-bottom: 1rem; }
.layout { display: grid; grid-template-columns: 360px 1fr; gap: 1rem; align-items: start; }
@media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }

.controls, .card { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 1rem; }
.controls { display: flex; flex-direction: column; gap: 1rem; position: sticky; top: 1rem; }
.results { display: flex; flex-direction: column; gap: 1rem; min-width: 0; }

.field { border: 0; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.4rem; }
.field-label { font-weight: 600; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); }
.row { display: flex; gap: 0.5rem; align-items: center; }
.hint { font-size: 0.85rem; color: var(--muted); margin: 0; }
.hint.warn, .error-text { color: var(--up); font-size: 0.85rem; margin: 0; }
.muted { color: var(--muted); }

.tabs { display: flex; gap: 0.25rem; }
.tab { flex: 1; padding: 0.4rem; border: 1px solid var(--border); background: #fff; border-radius: 6px; }
.tab.active { background: var(--accent); border-color: var(--accent); color: #fff; }

.search { position: relative; }
.search input { width: 100%; }
.search-results { position: absolute; z-index: 1000; left: 0; right: 0; margin: 0; padding: 0.25rem 0; list-style: none;
  background: #fff; border: 1px solid var(--border); border-radius: 6px; box-shadow: 0 6px 20px rgb(0 0 0 / 0.08); }
.search-results li { padding: 0 0.25rem; }
.search-results li.muted, .search-results li.error-text { padding: 0.4rem 0.6rem; }
.search-results button { width: 100%; text-align: left; border: 0; background: none; padding: 0.4rem 0.4rem; border-radius: 4px; }
.search-results button:hover { background: var(--bg); }

.box-inputs { display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem; }
.box-inputs label { display: flex; flex-direction: column; font-size: 0.8rem; color: var(--muted); text-transform: capitalize; }
.map { height: 280px; border-radius: 8px; border: 1px solid var(--border); }

.primary { background: var(--accent); color: #fff; border: 0; border-radius: 8px; padding: 0.7rem; font-weight: 600; }
.primary:disabled { opacity: 0.5; cursor: not-allowed; }
```

- [ ] **Step 2: Type-check, build and manually verify**

Run: `cd frontend && npm run build`
Expected: build succeeds with no TypeScript errors.

Run backend (`cd backend && uv run uvicorn app.main:app --port 8000`) and `cd frontend && cp -n .env.example .env && npm run dev`. In the browser at `http://localhost:5173`: search "Delhi" (city) → marker appears; switch to State, search "Rajasthan" → rectangle + clipped note; Draw box → drag on the map draws a rectangle and fills the four inputs; Analyze becomes enabled and the URL updates on click.

- [ ] **Step 3: Commit**

```bash
git add frontend
git commit -m "feat(frontend): add hazard, year and region controls with Leaflet map and box drawing"
```

---

### Task 15: Frontend results — summary, insights, charts, events, export, loading and error states

**Files:**
- Create: `frontend/src/charts/setup.ts`, `frontend/src/components/SummaryCards.tsx`, `InsightPanel.tsx`, `MetricChart.tsx`, `ThresholdChart.tsx`, `EventsTable.tsx`, `ExportButtons.tsx`, `ErrorBanner.tsx`, `LoadingSkeleton.tsx`, `Results.tsx`
- Modify: `frontend/src/App.tsx` (wire analysis query + results), `frontend/src/index.css` (append results styles)

**Interfaces:**
- Consumes: `Analysis`, `api.analyze`, `api.exportUrl`, `ApiError`, `formatChange`, `formatP`, `trendBadge`, `mean`.
- Produces: `<Results analysis/>`, `<ErrorBanner error onRetry/>`, `<LoadingSkeleton/>`.

- [ ] **Step 1: Implement components**

`frontend/src/charts/setup.ts`:
```ts
import {
  BarController, BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale,
  LineController, LineElement, PointElement, Tooltip,
} from 'chart.js'

ChartJS.register(BarController, BarElement, LineController, LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Legend)
```

`frontend/src/components/SummaryCards.tsx`:
```tsx
import type { Analysis } from '../api/types'
import { formatChange, formatP, mean, trendBadge } from '../lib/format'

export function SummaryCards({ analysis }: { analysis: Analysis }) {
  const usable = analysis.yearly.filter((r) => !r.low_quality)
  const avgDays = mean(usable.map((r) => r.HWF))
  const avgEvents = mean(usable.map((r) => r.HWN))
  const longest = analysis.events.reduce<Analysis['events'][number] | null>(
    (best, e) => (best === null || e.days > best.days ? e : best), null)
  const trend = analysis.trends.HWF
  const badge = trendBadge(trend)

  return (
    <div className="cards">
      <div className="card stat">
        <span className="stat-label">Heatwave days / year</span>
        <span className="stat-value">{avgDays === null ? '—' : avgDays.toFixed(1)}</span>
      </div>
      <div className="card stat">
        <span className="stat-label">Events / year</span>
        <span className="stat-value">{avgEvents === null ? '—' : avgEvents.toFixed(1)}</span>
      </div>
      <div className="card stat">
        <span className="stat-label">Longest heatwave</span>
        <span className="stat-value">{longest ? `${longest.days} days` : '—'}</span>
        {longest && <span className="stat-sub">{longest.start.slice(0, 4)}</span>}
      </div>
      <div className={`card stat tone-${badge.tone}`}>
        <span className="stat-label">Trend in heatwave days</span>
        <span className="stat-value small">{badge.label}</span>
        <span className="stat-sub">{formatChange(trend, 'days')} · {formatP(trend.mk_p)}</span>
      </div>
    </div>
  )
}
```

`frontend/src/components/InsightPanel.tsx`:
```tsx
import type { Analysis } from '../api/types'

export function InsightPanel({ analysis }: { analysis: Analysis }) {
  const q = analysis.data_quality
  return (
    <div className="card">
      <h3>Insights</h3>
      <ul className="insights">
        {analysis.insights.map((s) => <li key={s}>{s}</li>)}
      </ul>
      <details>
        <summary>Method, data quality and caveats</summary>
        <ul className="caveats">
          {analysis.caveats.map((c) => <li key={c}>{c}</li>)}
          <li>
            {q.days.toLocaleString()} days analysed; {q.removed} impossible values removed; {q.interpolated} short gaps
            filled by interpolation.
          </li>
        </ul>
      </details>
    </div>
  )
}
```

`frontend/src/components/MetricChart.tsx`:
```tsx
import { useState } from 'react'
import { Chart } from 'react-chartjs-2'
import type { ChartData, ChartOptions } from 'chart.js'
import type { Analysis, MetricKey } from '../api/types'
import { formatChange, formatP } from '../lib/format'

const METRICS: { key: MetricKey; label: string; unit: string }[] = [
  { key: 'HWF', label: 'Heatwave days', unit: 'days' },
  { key: 'HWN', label: 'Events', unit: 'events' },
  { key: 'HWD', label: 'Longest event', unit: 'days' },
  { key: 'HWM', label: 'Mean intensity', unit: '°C above threshold' },
  { key: 'HWA', label: 'Peak temperature', unit: '°C' },
]

export function MetricChart({ analysis }: { analysis: Analysis }) {
  const [metric, setMetric] = useState<MetricKey>('HWF')
  const info = METRICS.find((m) => m.key === metric)!
  const series = analysis.chart.series[metric]
  const years = analysis.chart.years
  const lowQuality = new Set(analysis.data_quality.low_quality_years)
  const trend = analysis.trends[metric]

  const data: ChartData<'bar' | 'line', (number | null)[], number> = {
    labels: years,
    datasets: [
      {
        type: 'bar', label: info.label, data: series.values, order: 3,
        backgroundColor: years.map((y) => (lowQuality.has(y) ? 'rgba(217, 98, 43, 0.25)' : 'rgba(217, 98, 43, 0.85)')),
      },
      { type: 'line', label: '5-year average', data: series.rolling5, borderColor: '#7a2e0e', pointRadius: 0, tension: 0.3, spanGaps: true, order: 1 },
      { type: 'line', label: 'Linear trend', data: series.trendline, borderColor: '#1f2328', borderDash: [6, 4], pointRadius: 0, order: 2 },
    ],
  }
  const options: ChartOptions<'bar' | 'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    scales: { y: { beginAtZero: metric !== 'HWA', title: { display: true, text: info.unit } } },
    plugins: {
      tooltip: {
        callbacks: {
          footer: (items) => (items.length && lowQuality.has(Number(items[0].label)) ? 'Low data quality: excluded from trend' : ''),
        },
      },
    },
  }

  return (
    <div className="card">
      <div className="chart-head">
        <h3>Yearly {info.label.toLowerCase()}</h3>
        <div className="segmented" role="group" aria-label="Metric">
          {METRICS.map((m) => (
            <button key={m.key} type="button" className={m.key === metric ? 'active' : ''} onClick={() => setMetric(m.key)}>
              {m.label}
            </button>
          ))}
        </div>
      </div>
      <div className="chart-box">
        <Chart type="bar" data={data} options={options} />
      </div>
      <p className="hint">
        {trend.reason
          ? 'Not enough complete years to assess a trend.'
          : `Sen's slope ${trend.sen_per_decade! > 0 ? '+' : ''}${trend.sen_per_decade} ${info.unit}/decade · change ${formatChange(trend, info.unit)} · ${formatP(trend.mk_p)} · ${trend.significant ? 'statistically significant' : 'not significant'}`}
      </p>
    </div>
  )
}
```

`frontend/src/components/ThresholdChart.tsx`:
```tsx
import { Line } from 'react-chartjs-2'

const LABELS = Array.from({ length: 365 }, (_, i) =>
  new Date(Date.UTC(2001, 0, i + 1)).toLocaleDateString('en', { month: 'short', day: 'numeric', timeZone: 'UTC' }))

export function ThresholdChart({ thresholds, baseline }: { thresholds: (number | null)[]; baseline: number[] }) {
  return (
    <div className="card">
      <h3>What counts as "hot" here</h3>
      <p className="hint">
        95th percentile of daily maximum temperature for each day of the year ({baseline[0]}–{baseline[1]} baseline).
        A heatwave is 3+ days in a row above this line.
      </p>
      <div className="chart-box small">
        <Line
          data={{ labels: LABELS, datasets: [{ label: 'Threshold (°C)', data: thresholds, borderColor: '#d9622b', pointRadius: 0, borderWidth: 2 }] }}
          options={{
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { x: { ticks: { maxTicksLimit: 12 } }, y: { title: { display: true, text: '°C' } } },
          }}
        />
      </div>
    </div>
  )
}
```

`frontend/src/components/EventsTable.tsx`:
```tsx
import { useState } from 'react'
import type { HeatwaveEvent } from '../api/types'

type SortKey = 'start' | 'days' | 'peak_tmax'

export function EventsTable({ events }: { events: HeatwaveEvent[] }) {
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: 'start', desc: true })
  const sorted = [...events].sort((a, b) => {
    const cmp = sort.key === 'start' ? a.start.localeCompare(b.start) : a[sort.key] - b[sort.key]
    return sort.desc ? -cmp : cmp
  })
  const header = (key: SortKey, label: string) => (
    <th aria-sort={sort.key === key ? (sort.desc ? 'descending' : 'ascending') : 'none'}>
      <button type="button" onClick={() => setSort({ key, desc: sort.key === key ? !sort.desc : true })}>
        {label}{sort.key === key ? (sort.desc ? ' ↓' : ' ↑') : ''}
      </button>
    </th>
  )

  return (
    <div className="card">
      <h3>Detected heatwaves ({events.length})</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>{header('start', 'Start')}<th>End</th>{header('days', 'Days')}{header('peak_tmax', 'Peak °C')}<th>Avg °C above threshold</th></tr>
          </thead>
          <tbody>
            {sorted.map((e) => (
              <tr key={e.start}>
                <td>{e.start}</td><td>{e.end}</td><td>{e.days}</td><td>{e.peak_tmax.toFixed(1)}</td><td>{e.mean_exceedance.toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

`frontend/src/components/ExportButtons.tsx`:
```tsx
import { api } from '../api/client'

export function ExportButtons({ id }: { id: string }) {
  return (
    <div className="row">
      <a className="button-link" href={api.exportUrl(id, 'csv')} download>Download CSV</a>
      <a className="button-link" href={api.exportUrl(id, 'pdf')} download>Download PDF report</a>
    </div>
  )
}
```

`frontend/src/components/ErrorBanner.tsx`:
```tsx
import { ApiError } from '../api/client'

function messageFor(error: unknown): string {
  if (!(error instanceof ApiError)) return 'Something unexpected went wrong.'
  if (error.status === 429) return `Too many requests. Please retry in ${error.retryAfter ?? 60} seconds.`
  if (error.status === 422) return `Please check your selection. ${error.details.join(' ') || error.message}`
  if (error.status === 502 || error.status === 504) return 'The weather data provider is unavailable right now. Please try again shortly.'
  return error.message
}

export function ErrorBanner({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  return (
    <div role="alert" className="banner error">
      <span>{messageFor(error)}</span>
      <button type="button" onClick={onRetry}>Retry</button>
    </div>
  )
}
```

`frontend/src/components/LoadingSkeleton.tsx`:
```tsx
export function LoadingSkeleton() {
  return (
    <div className="loading" aria-busy="true">
      <p className="muted">Fetching 45 years of daily data and detecting heatwaves… The first request for a region takes a few seconds.</p>
      <div className="cards">{[0, 1, 2, 3].map((i) => <div key={i} className="card skeleton" />)}</div>
      <div className="card skeleton tall" />
    </div>
  )
}
```

`frontend/src/components/Results.tsx`:
```tsx
import type { Analysis } from '../api/types'
import { EventsTable } from './EventsTable'
import { ExportButtons } from './ExportButtons'
import { InsightPanel } from './InsightPanel'
import { MetricChart } from './MetricChart'
import { SummaryCards } from './SummaryCards'
import { ThresholdChart } from './ThresholdChart'

export function Results({ analysis }: { analysis: Analysis }) {
  const noEvents = analysis.events.length === 0
  return (
    <>
      <div className="results-head">
        <h2>{analysis.region.label}</h2>
        <p className="muted">
          {analysis.years.start}–{analysis.years.end} · Heatwave · {analysis.cached ? 'served from cache' : 'freshly computed'}
        </p>
      </div>
      <SummaryCards analysis={analysis} />
      <InsightPanel analysis={analysis} />
      {noEvents ? (
        <p className="banner info">No heatwaves were detected in this period, so there is nothing to chart. Try a longer range or another region.</p>
      ) : (
        <MetricChart analysis={analysis} />
      )}
      <ThresholdChart thresholds={analysis.threshold_by_doy} baseline={analysis.params.baseline} />
      {!noEvents && <EventsTable events={analysis.events} />}
      <ExportButtons id={analysis.id} />
    </>
  )
}
```

- [ ] **Step 2: Wire results into `App.tsx`**

Add imports at the top of `frontend/src/App.tsx`:
```tsx
import './charts/setup'
import { ErrorBanner } from './components/ErrorBanner'
import { LoadingSkeleton } from './components/LoadingSkeleton'
import { Results } from './components/Results'
```
After the `submitted` state add:
```tsx
  const analysis = useQuery({
    queryKey: ['analysis', submitted],
    queryFn: () => api.analyze(submitted!),
    enabled: submitted !== null,
    staleTime: Infinity,
    retry: false,
  })
```
Replace the `<section className="results">…</section>` body with:
```tsx
        <section className="results">
          {!submitted && (
            <div className="card empty">
              <h2>Pick a region to begin</h2>
              <p className="muted">Search a city or state, click the map, or draw a box, then press Analyze.</p>
            </div>
          )}
          {submitted && analysis.isPending && <LoadingSkeleton />}
          {analysis.isError && <ErrorBanner error={analysis.error} onRetry={() => analysis.refetch()} />}
          {analysis.data && <Results analysis={analysis.data} />}
        </section>
```

Append to `frontend/src/index.css`:
```css
.cards { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.75rem; }
@media (max-width: 700px) { .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.stat { display: flex; flex-direction: column; gap: 0.2rem; }
.stat-label { font-size: 0.8rem; color: var(--muted); }
.stat-value { font-size: 1.6rem; font-weight: 700; }
.stat-value.small { font-size: 1rem; }
.stat-sub { font-size: 0.8rem; color: var(--muted); }
.tone-up .stat-value { color: var(--up); }
.tone-down .stat-value { color: var(--down); }
.tone-flat .stat-value, .tone-na .stat-value { color: var(--flat); }

.insights { margin: 0; padding-left: 1.2rem; display: flex; flex-direction: column; gap: 0.4rem; }
.caveats { font-size: 0.85rem; color: var(--muted); padding-left: 1.2rem; }
details summary { cursor: pointer; margin-top: 0.75rem; font-size: 0.9rem; }

.chart-head { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.segmented { display: flex; flex-wrap: wrap; gap: 0.25rem; }
.segmented button { border: 1px solid var(--border); background: #fff; border-radius: 999px; padding: 0.2rem 0.7rem; font-size: 0.85rem; }
.segmented button.active { background: var(--text); color: #fff; border-color: var(--text); }
.chart-box { position: relative; height: 320px; margin: 0.75rem 0; }
.chart-box.small { height: 220px; }

.table-wrap { max-height: 320px; overflow: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
th, td { text-align: left; padding: 0.35rem 0.5rem; border-bottom: 1px solid var(--border); }
th button { border: 0; background: none; font-weight: 600; padding: 0; }
thead th { position: sticky; top: 0; background: var(--panel); }

.button-link { display: inline-block; padding: 0.5rem 0.9rem; border: 1px solid var(--accent); color: var(--accent-dark); border-radius: 8px; text-decoration: none; font-weight: 600; }
.banner { display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: 0.75rem 1rem; border-radius: 8px; margin: 0; }
.banner.error { background: #fdecea; color: #7a1c12; }
.banner.info { background: #eef4fb; color: #1d4f7a; }
.banner button { border: 1px solid currentColor; background: none; color: inherit; border-radius: 6px; padding: 0.3rem 0.8rem; }
.results-head { display: flex; flex-direction: column; gap: 0.2rem; }
.empty { text-align: center; padding: 3rem 1rem; }

.loading { display: flex; flex-direction: column; gap: 0.75rem; }
.skeleton { min-height: 90px; background: linear-gradient(90deg, #f1ece4 25%, #f8f4ee 50%, #f1ece4 75%); background-size: 200% 100%; animation: shimmer 1.4s infinite; }
.skeleton.tall { min-height: 320px; }
@keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }
```

- [ ] **Step 3: Build, test and verify manually**

Run: `cd frontend && npm test && npm run build`
Expected: tests pass; build succeeds with no TypeScript errors.

Manual check with the backend running: Delhi 1990–2020 → loading skeleton, then cards, insights, chart with metric toggles, threshold curve, events table (sortable), CSV/PDF downloads work; reload page → URL restores the same analysis (served from cache); stop the backend and Retry → error banner; choose a box larger than 5° via the inputs → Analyze disabled with message; choose a 1-year range → "Not enough complete years" text.

- [ ] **Step 4: Commit**

```bash
git add frontend
git commit -m "feat(frontend): add results view with charts, insights, events table and exports"
```

---

### Task 16: Deployment config and README

**Files:**
- Create: `backend/Dockerfile`, `backend/.dockerignore`, `render.yaml`, `README.md`

**Interfaces:**
- Consumes: everything.
- Produces: deployable artifacts and documentation.

- [ ] **Step 1: Docker and Render**

`backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MPLBACKEND=Agg UV_COMPILE_BYTECODE=1
WORKDIR /app

RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY scripts ./scripts

EXPOSE 8000
CMD ["sh", "-c", ".venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

`backend/.dockerignore`:
```
.venv
__pycache__
.pytest_cache
tests
.env
```

`render.yaml`:
```yaml
services:
  - type: web
    name: climate-hazard-api
    runtime: docker
    plan: free
    dockerfilePath: ./backend/Dockerfile
    dockerContext: ./backend
    healthCheckPath: /api/health
    envVars:
      - key: MONGO_URI
        sync: false
      - key: MONGO_DB
        value: climate_hazards
      - key: CORS_ORIGINS
        sync: false
      - key: NOMINATIM_USER_AGENT
        sync: false
      - key: TRUSTED_PROXY_HOPS
        value: "1"
```

Run: `cd backend && docker build -t climate-hazard-api . && docker run --rm -p 8001:8000 -e MONGO_URI=mongodb://host.docker.internal:27017 --add-host=host.docker.internal:host-gateway climate-hazard-api` then `curl localhost:8001/api/health`.
Expected: `{"status":"ok","db":"ok"}`.

- [ ] **Step 2: Write README.md**

`README.md`:
````markdown
# Climate Hazard Trend Analyzer — Heatwaves

Pick a city, a state or a lat-lon box and a year range; the app downloads daily maximum temperatures,
detects heatwaves with a percentile rule, tests whether they are really increasing, and shows the result
as charts, a table of events and plain-language insights.

- **Live app:** _add Vercel URL_ · **API docs:** _add Render URL_/docs

## Architecture

```
React + TS (Vercel) ──HTTPS──► FastAPI (Render) ──► NASA POWER (primary) / Open-Meteo (fallback)
                                     │              Open-Meteo geocoding, Nominatim (states)
                                     ▼
                              MongoDB Atlas
                 weather_daily · analyses · geocode_cache
```

`POST /api/analyze` validates input → snaps the region to the MERRA-2 grid (0.5° × 0.625°) → returns the
cached analysis if present → otherwise loads each grid cell's 1981→present daily series from
`weather_daily` (fetching missing cells from NASA POWER, falling back to Open-Meteo) → cleans and
area-averages → detects heatwaves → computes trends and insights → stores the result (30-day TTL).

| Folder | What lives there |
|---|---|
| `backend/app/core` | cleaning, trend statistics (pure functions) |
| `backend/app/hazards` | heatwave detection; registry for future hazards |
| `backend/app/clients` | external APIs: retries, timeouts, validation |
| `backend/app/services` | region resolution, cache/ingest, orchestration, insights, geocoding, export |
| `backend/app/api` | HTTP routes |
| `frontend/src` | React app (Leaflet map, Chart.js charts, TanStack Query) |

## Data sources

| Source | Use |
|---|---|
| [NASA POWER](https://power.larc.nasa.gov/docs/services/api/) daily point API (MERRA-2) | Primary: `T2M_MAX` (°C), `PRECTOTCORR` (mm/day), 1981→present, no key |
| [Open-Meteo Historical](https://open-meteo.com/en/docs/historical-weather-api) (ERA5) | Fallback per grid cell |
| [Open-Meteo Geocoding](https://open-meteo.com/en/docs/geocoding-api) | City search |
| [Nominatim](https://nominatim.org/release-docs/latest/api/Search/) | State bounding boxes (1 req/s, cached 7 days) |

**Why NASA POWER first:** Open-Meteo's free tier counts every ~2 weeks of data as one API call
(10,000/day). A single location's 45-year history costs ~1,170 calls, so only a handful of new places per
day would be possible. NASA POWER returned 45 years for one point in ~2 s with no quota.

## Heatwave logic

1. **Cleaning** — POWER's `-999` fill values and Open-Meteo `null`s become missing; values outside
   −90…60 °C are removed; units are checked; gaps of ≤ 2 days are linearly interpolated, longer gaps stay
   missing (and break heatwave runs); years with > 10% missing days are flagged low-quality and excluded
   from trends.
2. **Threshold** — for each calendar day, the 95th percentile of daily max temperature over 1981–2010
   within a ±7-day window (Feb 29 uses Feb 28's threshold).
3. **Event** — 3+ consecutive days above that day's threshold; counted in the year it starts.
4. **Yearly metrics** — HWN (events), HWF (heatwave days), HWD (longest event), HWM (mean °C above
   threshold), HWA (peak temperature).
5. **Trends** — Sen's slope (robust trend size), Mann-Kendall test (significant if p < 0.05), OLS line for
   the chart, 5-year rolling mean. At least 10 usable years required. % change is computed along the Sen
   line (not between two noisy years) and only when the starting value is ≥ 1; °C metrics use absolute change.
6. **Insights** — sentences generated by fixed rules: a trend is only described as an increase/decrease
   when it is statistically significant.

## API

| Method | Route | Limit / IP |
|---|---|---|
| GET | `/api/health` | — |
| GET | `/api/hazards` | 60/min |
| GET | `/api/geocode?q=&kind=city\|state` | 30/min |
| POST | `/api/analyze` | 10/min |
| GET | `/api/analyses/{id}` | 60/min |
| GET | `/api/analyses/{id}/export.csv`, `/report.pdf` | 10/min |

Errors are always `{"error": {"code", "message"}}` (422 validation, 404, 429 with `Retry-After`, 502/504 upstream).

## Security & performance

- Pydantic validation of every input (coordinate ranges, box ≤ 5° × 5°, year range, enum hazard, no extra fields).
- Database lookups use server-computed SHA-256 ids, never user-supplied query objects.
- Fixed upstream hosts; params URL-encoded by httpx; timeouts, bounded retries, ≤ 3 concurrent fetches,
  Nominatim throttled to 1 req/s; upstream responses validated (units, dates, coordinates) before caching.
- Per-IP rate limiting (slowapi) using the proxy-appended `X-Forwarded-For` entry (spoof-resistant).
- CORS restricted to the frontend origin; GZip; `Cache-Control` on immutable GET responses.
- Two cache layers: raw weather per grid cell (shared across regions/years) and computed analyses (TTL).

## Local setup

Requirements: Docker, Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 20.19+.

```bash
docker compose up -d mongo
cd backend && cp .env.example .env && uv sync && uv run uvicorn app.main:app --reload --port 8000
cd frontend && cp .env.example .env && npm install && npm run dev     # http://localhost:5173
```
Tests: `cd backend && uv run pytest` (needs the Mongo container) · `cd frontend && npm test`.
Pre-warm demo cities: `cd backend && uv run python -m scripts.seed --api http://localhost:8000`.

## Deployment

1. **MongoDB Atlas** (M0 free): create a cluster and a database user; allow access from anywhere
   (`0.0.0.0/0`, Render's free tier has no static IP); copy the connection string.
2. **Render**: New → Blueprint → this repo (uses `render.yaml`). Set `MONGO_URI`,
   `CORS_ORIGINS=["https://<your-app>.vercel.app"]`, `NOMINATIM_USER_AGENT=climate-hazard-analyzer/1.0 (<your email>)`.
   Free instances sleep when idle; the first request can take ~30–60 s.
3. **Vercel**: import the repo, root directory `frontend`, framework Vite, env `VITE_API_BASE_URL=https://<render-app>.onrender.com`.
4. Run the seed script against the Render URL so demo cities load instantly.

## Assumptions

- Reanalysis data (MERRA-2 via NASA POWER; ERA5 fallback) stands in for station observations; it is
  consistent worldwide but smooths local extremes. Analysis starts in 1981 (POWER's first year).
- Baseline 1981–2010 (a WMO 30-year normal) is fixed regardless of the selected years.
- Box and state results are area-averaged over up to 9 grid points; states larger than 5° × 5° are
  clipped to a 5° × 5° box around their centre (the UI says so).
- The last selectable year is the last complete calendar year.
- Single backend instance: in-memory rate limits and per-key locks are sufficient at this scale.

## What I'd improve with more time

- Heavy-rainfall and drought hazards (precipitation is already stored).
- NOAA GHCN station data as a comparison source; pre-1981 history via Copernicus CDS.
- Per-grid-cell heatwave maps instead of only area averages.
- Redis-backed rate limiting and a job queue for multi-instance deployments.
- User-configurable percentile, duration and baseline.
- Playwright end-to-end tests for the frontend.

## AI tools used

- **Claude Code (Claude Opus 5.5)** — used to discuss and explain the climate-statistics concepts
  (percentile thresholds, Sen's slope, Mann-Kendall, interpolation), compare data sources (it measured
  Open-Meteo's quota cost and NASA POWER's speed with live requests, which led to switching the primary
  source), write the design spec and implementation plan, and generate code and tests task by task.
  I reviewed every step, chose the architecture and trade-offs, and ran and verified the tests and the app.
````

- [ ] **Step 3: Final verification**

Run: `cd backend && uv run pytest -q && cd ../frontend && npm test && npm run build`
Expected: all backend tests pass, frontend tests pass, build succeeds.

- [ ] **Step 4: Commit**

```bash
git add backend/Dockerfile backend/.dockerignore render.yaml README.md
git commit -m "docs: add deployment config and README"
```

- [ ] **Step 5: Deployment (performed by the user — needs their accounts)**

Follow README "Deployment" steps 1–4, then fill in the live URLs at the top of README and commit:
```bash
git add README.md && git commit -m "docs: add live URLs"
```
