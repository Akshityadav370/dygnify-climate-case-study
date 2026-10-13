"""Synthetic provider responses for tests (no network)."""

import math
import random
from datetime import date, datetime, timedelta

import httpx


def synthetic_tmax(d: date) -> float:
    """Seasonal cycle + multi-day warm/cool spells + seeded noise + steady warming (~2.2 °C over 1981-2025)."""
    doy = d.timetuple().tm_yday
    seasonal = 30 + 8 * math.sin(2 * math.pi * (doy - 100) / 365)
    spells = 2.5 * math.sin(2 * math.pi * d.toordinal() / 11)
    noise = random.Random(d.toordinal()).uniform(-1.5, 1.5)
    warming = 0.05 * (d.year - 1981)
    return round(seasonal + spells + noise + warming, 2)


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


def openmeteo_payload(lat, lon, start, end, tmax_fn=synthetic_tmax, missing_days=frozenset()) -> dict:
    ds = days(start, end)
    return {
        "latitude": lat + 0.02,
        "longitude": lon - 0.03,
        "daily_units": {"time": "iso8601", "temperature_2m_max": "°C", "precipitation_sum": "mm"},
        "daily": {
            "time": [d.isoformat() for d in ds],
            "temperature_2m_max": [None if d in missing_days else tmax_fn(d) for d in ds],
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


def openmeteo_responder(tmax_fn=synthetic_tmax, missing_days=frozenset()):
    def respond(request: httpx.Request) -> httpx.Response:
        p = request.url.params
        payload = openmeteo_payload(
            float(p["latitude"]), float(p["longitude"]),
            date.fromisoformat(p["start_date"]), date.fromisoformat(p["end_date"]), tmax_fn, missing_days,
        )
        return httpx.Response(200, json=payload)

    return respond
