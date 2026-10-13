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
