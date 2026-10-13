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
