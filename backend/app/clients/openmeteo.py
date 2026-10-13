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
