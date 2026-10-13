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
