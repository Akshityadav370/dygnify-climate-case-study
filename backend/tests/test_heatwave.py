from datetime import date

import numpy as np
import pandas as pd

from app.hazards.heatwave import (
    HeatwaveEvent,
    HeatwaveParams,
    analyze,
    compute_thresholds,
    day_of_year_365,
    detect_events,
    yearly_metrics,
)

PARAMS = HeatwaveParams()


def make_series(start="1981-01-01", end="2012-12-31", value=30.0) -> pd.Series:
    index = pd.date_range(start, end, freq="D")
    return pd.Series(value, index=index, dtype="float64")


def test_day_of_year_maps_feb29_onto_feb28_and_keeps_march_aligned():
    index = pd.DatetimeIndex(["2000-02-28", "2000-02-29", "2000-03-01", "2001-03-01", "2000-12-31", "2001-12-31"])
    assert list(day_of_year_365(index)) == [59, 59, 60, 60, 365, 365]


def test_constant_series_gives_constant_thresholds():
    thresholds = compute_thresholds(make_series(), PARAMS)
    assert thresholds.shape == (365,)
    assert np.allclose(thresholds, 30.0)


def test_threshold_window_wraps_around_year_end():
    s = make_series(end="2010-12-31", value=10.0)
    s[(s.index.month == 12) & (s.index.day >= 25)] = 50.0
    thresholds = compute_thresholds(s, PARAMS)
    assert thresholds[0] == 50.0  # Jan 1 window includes Dec 25-31
    assert thresholds[179] == 10.0  # late June window is all 10s


def test_four_hot_days_make_one_event():
    s = make_series()
    s["2011-07-01":"2011-07-04"] = 40.0
    events = detect_events(s, compute_thresholds(s, PARAMS), min_days=3)
    assert events == [HeatwaveEvent(date(2011, 7, 1), date(2011, 7, 4), 4, 40.0, 10.0)]


def test_two_short_hot_spells_are_not_a_heatwave():
    s = make_series()
    s["2011-07-01":"2011-07-02"] = 40.0
    s["2011-07-04":"2011-07-05"] = 40.0
    assert detect_events(s, compute_thresholds(s, PARAMS), min_days=3) == []


def test_missing_day_breaks_a_hot_run():
    s = make_series()
    s["2011-07-01":"2011-07-05"] = 40.0
    s["2011-07-03"] = np.nan
    assert detect_events(s, compute_thresholds(s, PARAMS), min_days=3) == []


def test_event_crossing_new_year_counts_in_start_year():
    s = make_series()
    s["2011-12-30":"2012-01-02"] = 40.0
    result = analyze(s, range(2011, 2013), set(), PARAMS)
    assert [(e.start, e.days) for e in result.events] == [(date(2011, 12, 30), 4)]
    assert [(r["year"], r["HWN"], r["HWF"]) for r in result.yearly] == [(2011, 1, 4), (2012, 0, 0)]


def test_yearly_metrics_combine_events():
    events = [
        HeatwaveEvent(date(2011, 6, 1), date(2011, 6, 4), 4, 40.0, 1.0),
        HeatwaveEvent(date(2011, 7, 1), date(2011, 7, 4), 4, 42.0, 2.0),
    ]
    rows = yearly_metrics(events, range(2011, 2013), low_quality={2012})
    assert rows[0] == {"year": 2011, "HWN": 2, "HWF": 8, "HWD": 4, "HWM": 1.5, "HWA": 42.0, "low_quality": False}
    assert rows[1] == {"year": 2012, "HWN": 0, "HWF": 0, "HWD": 0, "HWM": None, "HWA": None, "low_quality": True}


def test_analyze_only_reports_events_inside_selected_years():
    s = make_series()
    s["2011-07-01":"2011-07-04"] = 40.0
    s["2012-07-01":"2012-07-04"] = 40.0
    result = analyze(s, range(2012, 2013), set(), PARAMS)
    assert [e.start.year for e in result.events] == [2012]
    assert len(result.thresholds) == 365


def test_event_to_dict_uses_iso_dates():
    event = HeatwaveEvent(date(2011, 7, 1), date(2011, 7, 4), 4, 40.0, 10.0)
    assert event.to_dict() == {
        "start": "2011-07-01", "end": "2011-07-04", "days": 4, "peak_tmax": 40.0, "mean_exceedance": 10.0,
    }
