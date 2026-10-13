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
