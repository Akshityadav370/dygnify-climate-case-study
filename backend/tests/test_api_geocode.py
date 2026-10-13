import httpx
import respx

from app.clients.nominatim import NOMINATIM_URL
from app.clients.openmeteo import GEOCODE_URL
from app.config import last_complete_year
from app.services.geocode import clip_box

CITY_BODY = {"results": [{"name": "Delhi", "latitude": 28.65, "longitude": 77.23, "country": "India"}]}
STATE_BODY = [{"name": "Rajasthan", "display_name": "Rajasthan, India", "lat": "26.81", "lon": "73.77",
               "boundingbox": ["23.0586612", "30.1982530", "69.4844368", "78.2720089"]}]


def test_clip_box_shrinks_large_boxes_around_centre():
    box, clipped = clip_box({"south": 23.0, "west": 69.0, "north": 31.0, "east": 79.0})
    assert clipped is True
    assert box == {"south": 24.5, "west": 71.5, "north": 29.5, "east": 76.5}


def test_clip_box_centres_on_given_point_and_handles_antimeridian():
    box, clipped = clip_box({"south": 51.0, "west": -179.9, "north": 71.5, "east": 179.9}, centre=(64.4, -150.0))
    assert clipped is True
    assert box == {"south": 61.9, "west": -152.5, "north": 66.9, "east": -147.5}


def test_clip_box_keeps_small_boxes():
    box, clipped = clip_box({"south": 1.0, "west": 2.0, "north": 3.0, "east": 4.0})
    assert clipped is False
    assert box == {"south": 1.0, "west": 2.0, "north": 3.0, "east": 4.0}


@respx.mock
def test_city_search_is_cached(client, mongo):
    route = respx.get(GEOCODE_URL).mock(return_value=httpx.Response(200, json=CITY_BODY))
    first = client.get("/api/geocode", params={"q": "Delhi", "kind": "city"})
    second = client.get("/api/geocode", params={"q": "  delhi ", "kind": "city"})
    assert first.status_code == 200
    assert first.json()["results"][0]["label"] == "Delhi, India"
    assert second.json() == first.json()
    assert route.call_count == 1


@respx.mock
def test_state_search_returns_clipped_box(client):
    respx.get(NOMINATIM_URL).mock(return_value=httpx.Response(200, json=STATE_BODY))
    result = client.get("/api/geocode", params={"q": "Rajasthan", "kind": "state"}).json()["results"][0]
    assert result["kind"] == "state"
    assert result["clipped"] is True
    bbox = result["bbox"]
    assert round(bbox["north"] - bbox["south"], 6) == 5.0
    assert round(bbox["east"] - bbox["west"], 6) == 5.0


def test_geocode_validates_query(client):
    assert client.get("/api/geocode", params={"q": " a ", "kind": "city"}).status_code == 422
    assert client.get("/api/geocode", params={"q": "x" * 101, "kind": "city"}).status_code == 422
    assert client.get("/api/geocode", params={"q": "Delhi", "kind": "country"}).status_code == 422


def test_hazards_lists_heatwave_and_year_range(client):
    data = client.get("/api/hazards").json()
    assert data["years"] == {"min": 1981, "max": last_complete_year()}
    statuses = {h["id"]: h["status"] for h in data["hazards"]}
    assert statuses["heatwave"] == "available"
    assert statuses["heavy_rainfall"] == "coming_soon"
