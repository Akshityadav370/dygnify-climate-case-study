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
from app.services.insights import REGION_TOKEN, build_insights
from app.services.region import analysis_id, grid_points

ALGO_VERSION = "v2"  # v2: region label filled in per response; p-value wording; count change clamped at 0
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
        REGION_TOKEN, req.start_year, req.end_year, result.yearly, trends, sources, len(points), flagged
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
    out["insights"] = [sentence.replace(REGION_TOKEN, label) for sentence in doc["insights"]]
    out["chart"] = build_chart(doc)
    return out
