from datetime import UTC, datetime, timedelta
from typing import Literal

from pymongo.asynchronous.database import AsyncDatabase

from app.clients.http import UpstreamClient
from app.clients.nominatim import search_states
from app.clients.openmeteo import search_cities
from app.config import Settings
from app.models import MAX_BOX_DEGREES


def clip_box(bbox: dict, centre: tuple[float, float] | None = None, max_deg: float = MAX_BOX_DEGREES) -> tuple[dict, bool]:
    """Shrink a box to at most max_deg x max_deg around `centre` (default: the box centre).

    Pass the place's own coordinates as `centre`: the bounding-box centre can lie outside
    irregular shapes, and for regions crossing the antimeridian (west≈-180, east≈180)
    it lands on the opposite side of the globe.
    """
    south, west, north, east = bbox["south"], bbox["west"], bbox["north"], bbox["east"]
    centre_lat, centre_lon = centre if centre else ((north + south) / 2, (east + west) / 2)
    clipped = False
    if north - south > max_deg:
        south, north = max(-90.0, centre_lat - max_deg / 2), min(90.0, centre_lat + max_deg / 2)
        clipped = True
    if east - west > max_deg:
        west, east = max(-180.0, centre_lon - max_deg / 2), min(180.0, centre_lon + max_deg / 2)
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
            box, clipped = clip_box(state["bbox"], centre=(state["lat"], state["lon"]))
            results.append({**state, "kind": "state", "bbox": box, "clipped": clipped})

    expires_at = datetime.now(UTC) + timedelta(days=settings.geocode_ttl_days)
    await db.geocode_cache.replace_one({"_id": key}, {"results": results, "expires_at": expires_at}, upsert=True)
    return results
