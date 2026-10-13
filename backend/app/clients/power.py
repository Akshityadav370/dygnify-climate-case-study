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
