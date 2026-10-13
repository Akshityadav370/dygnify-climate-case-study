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
