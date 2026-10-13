import pytest
from pydantic import ValidationError

from app.config import last_complete_year
from app.models import AnalyzeRequest, BoxRegion, PointRegion
from app.services.region import analysis_id, cell_id, grid_points, snap


def test_snap_to_merra2_grid():
    assert snap(28.61, 77.21) == (28.5, 77.5)
    assert snap(-33.87, 151.21) == (-34.0, 151.25)


def test_snap_wraps_east_edge_and_clamps_poles():
    assert snap(-89.9, 179.9) == (-90.0, -180.0)
    assert snap(89.99, 0.1) == (90.0, 0.0)


def test_point_region_is_one_grid_point():
    assert grid_points(PointRegion(type="point", lat=28.61, lon=77.21)) == [(28.5, 77.5)]


def test_small_box_collapses_to_one_point():
    box = BoxRegion(type="box", south=28.5, west=77.2, north=28.7, east=77.4)
    assert grid_points(box) == [(28.5, 77.5)]


def test_large_box_samples_nine_points():
    box = BoxRegion(type="box", south=20.0, west=70.0, north=25.0, east=75.0)
    points = grid_points(box)
    assert len(points) == 9
    assert points == sorted(points)


def test_cell_id_format():
    assert cell_id(28.5, -77.5) == "28.500:-77.500"


def test_analysis_id_is_deterministic_and_sensitive_to_inputs():
    a = analysis_id("heatwave", [(28.5, 77.5)], 1990, 2020, "v1")
    assert a == analysis_id("heatwave", [(28.5, 77.5)], 1990, 2020, "v1")
    assert len(a) == 64
    assert a != analysis_id("heatwave", [(28.5, 77.5)], 1991, 2020, "v1")
    assert a != analysis_id("heatwave", [(28.5, 77.5)], 1990, 2020, "v2")


def valid_request(**overrides) -> dict:
    return {
        "hazard": "heatwave",
        "region": {"type": "point", "lat": 28.6, "lon": 77.2, "label": "Delhi"},
        "start_year": 1990,
        "end_year": 2020,
    } | overrides


def test_analyze_request_accepts_valid_input_and_defaults_hazard():
    body = valid_request()
    del body["hazard"]
    request = AnalyzeRequest.model_validate(body)
    assert request.hazard == "heatwave"
    assert isinstance(request.region, PointRegion)


@pytest.mark.parametrize(
    "overrides",
    [
        {"start_year": 1970},
        {"end_year": last_complete_year() + 1},
        {"start_year": 2010, "end_year": 2000},
        {"hazard": "drought"},
        {"region": {"type": "point", "lat": 91, "lon": 0}},
        {"region": {"type": "point", "lat": float("nan"), "lon": 0}},
        {"region": {"type": "box", "south": 10, "west": 10, "north": 16, "east": 12}},
        {"region": {"type": "box", "south": 12, "west": 10, "north": 10, "east": 12}},
        {"region": {"type": "point", "lat": 1, "lon": 1, "label": "x" * 101}},
        {"unexpected": True},
    ],
)
def test_analyze_request_rejects_invalid_input(overrides):
    with pytest.raises(ValidationError):
        AnalyzeRequest.model_validate(valid_request(**overrides))
