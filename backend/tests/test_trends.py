import pytest

from app.core.trends import analyze_trend, mann_kendall, ols, rolling_mean, sens_slope


def test_mann_kendall_on_strictly_increasing_series():
    s, p = mann_kendall([1, 2, 3, 4, 5])
    assert s == 10
    # var = 5*4*15/18 = 16.667; z = (10-1)/sqrt(var) = 2.2045; p = 2*(1-Phi(z))
    assert p == pytest.approx(0.0275, abs=1e-3)


def test_mann_kendall_all_ties_is_not_significant():
    assert mann_kendall([3, 3, 3, 3]) == (0, 1.0)


def test_sens_slope_ignores_an_outlier():
    slope, intercept = sens_slope([0, 1, 2, 3, 4], [0, 1, 2, 3, 100])
    assert slope == 1.0
    assert intercept == 0.0
    ols_slope, _ = ols([0, 1, 2, 3, 4], [0, 1, 2, 3, 100])
    assert ols_slope > 15  # least squares is pulled by the outlier


def test_rolling_mean_is_centred_with_partial_edges():
    assert rolling_mean([1, 2, 3, 4, 5]) == [2.0, 2.5, 3.0, 3.5, 4.0]
    assert rolling_mean([1, None, None, None, 5]) == [None, None, None, None, None]


def test_significant_increase_reports_percent_change():
    years = list(range(2001, 2021))
    trend = analyze_trend(years, [float(v) for v in range(1, 21)], set(), 2001, 2020)
    assert trend.significant is True
    assert trend.sen_per_decade == 10.0
    assert trend.change_kind == "pct"
    assert trend.change_value == 1900.0
    assert trend.reason is None


def test_small_start_value_reports_absolute_change():
    years = list(range(2001, 2021))
    trend = analyze_trend(years, [float(v) for v in range(0, 20)], set(), 2001, 2020)
    assert trend.change_kind == "abs"
    assert trend.change_value == 19.0


def test_pct_disabled_reports_absolute_change():
    years = list(range(2001, 2021))
    trend = analyze_trend(years, [float(v) for v in range(10, 30)], set(), 2001, 2020, allow_pct=False)
    assert trend.change_kind == "abs"


def test_too_few_usable_years_returns_reason():
    years = list(range(2001, 2021))
    values = [1.0] * 20
    values[0] = None
    trend = analyze_trend(years, values, excluded=set(range(2002, 2013)), start_year=2001, end_year=2020)
    assert trend.n_years == 8
    assert trend.reason == "insufficient_years"
    assert trend.sen_per_decade is None and trend.significant is False


def test_flat_noise_is_not_significant():
    years = list(range(2001, 2021))
    values = [5.0, 7.0, 4.0, 6.0, 5.0, 8.0, 3.0, 6.0, 5.0, 7.0, 4.0, 6.0, 5.0, 7.0, 4.0, 6.0, 6.0, 4.0, 5.0, 6.0]
    trend = analyze_trend(years, values, set(), 2001, 2020)
    assert trend.significant is False
    assert trend.mk_p > 0.05



def test_declining_counts_never_report_more_than_minus_100_percent():
    years = list(range(2001, 2021))
    values = [12.0, 10.0, 8.0, 6.0, 4.0, 2.0] + [0.0] * 14  # Sen line goes below zero by 2020
    trend = analyze_trend(years, values, set(), 2001, 2020)
    assert trend.change_kind == "pct"
    assert trend.change_value == -100.0


def test_significance_uses_the_reported_rounded_p_value(monkeypatch):
    import app.core.trends as trends

    monkeypatch.setattr(trends, "mann_kendall", lambda y: (5, 0.04996))
    trend = analyze_trend(list(range(2001, 2021)), [float(v) for v in range(1, 21)], set(), 2001, 2020)
    assert trend.mk_p == 0.05
    assert trend.significant is False
