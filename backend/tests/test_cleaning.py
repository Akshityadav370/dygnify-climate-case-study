from datetime import date

import numpy as np
import pandas as pd

from app.core.cleaning import clean_tmax, low_quality_years, to_daily_series
from app.core.series import DailySeries


def values(series: pd.Series) -> list:
    return [None if np.isnan(v) else round(float(v), 4) for v in series]


def test_daily_series_end_date():
    s = DailySeries(start=date(2020, 2, 27), tmax=[1.0, 2.0, 3.0], precip=[0, 0, 0], sources=["nasa-power"])
    assert s.end == date(2020, 2, 29)


def test_to_daily_series_converts_none_to_nan_with_daily_index():
    s = to_daily_series(date(2020, 1, 1), [1.0, None, 3.0])
    assert list(s.index.strftime("%Y-%m-%d")) == ["2020-01-01", "2020-01-02", "2020-01-03"]
    assert values(s) == [1.0, None, 3.0]


def test_out_of_range_values_are_removed_then_short_gap_interpolated():
    result = clean_tmax([to_daily_series(date(2020, 1, 1), [30.0, 75.0, 32.0])])
    assert result.removed == 1
    assert result.interpolated == 1
    assert values(result.tmax) == [30.0, 31.0, 32.0]


def test_two_day_gap_is_interpolated():
    result = clean_tmax([to_daily_series(date(2020, 1, 1), [30.0, None, None, 33.0])])
    assert values(result.tmax) == [30.0, 31.0, 32.0, 33.0]
    assert result.interpolated == 2


def test_three_day_gap_is_left_missing():
    result = clean_tmax([to_daily_series(date(2020, 1, 1), [30.0, None, None, None, 34.0])])
    assert values(result.tmax) == [30.0, None, None, None, 34.0]
    assert result.interpolated == 0


def test_leading_gap_is_not_extrapolated():
    result = clean_tmax([to_daily_series(date(2020, 1, 1), [None, 30.0, 31.0])])
    assert values(result.tmax) == [None, 30.0, 31.0]


def test_multiple_points_are_area_averaged_ignoring_missing():
    a = to_daily_series(date(2020, 1, 1), [30.0, 40.0])
    b = to_daily_series(date(2020, 1, 1), [32.0, None])
    assert values(clean_tmax([a, b]).tmax) == [31.0, 40.0]


def test_low_quality_years_flags_more_than_ten_percent_missing():
    raw = [20.0] * (365 * 2)
    for i in range(40):  # 2001: 40 missing days (11%)
        raw[100 + i] = None
    for i in range(30):  # 2002: 30 missing days (8%)
        raw[365 + 100 + i] = None
    s = to_daily_series(date(2001, 1, 1), raw)
    assert low_quality_years(s, range(2001, 2003)) == [2001]


def test_year_absent_from_series_counts_as_low_quality():
    s = to_daily_series(date(2001, 1, 1), [20.0] * 365)
    assert low_quality_years(s, [2001, 2002]) == [2002]
