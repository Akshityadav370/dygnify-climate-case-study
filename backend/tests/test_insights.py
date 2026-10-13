from app.services.insights import build_insights, describe_trend


def trend(**overrides) -> dict:
    base = {
        "n_years": 30, "sen_per_decade": 4.2, "mk_p": 0.003, "significant": True, "ols_slope": 0.4,
        "ols_intercept": -800.0, "change_kind": "pct", "change_value": 120.0, "reason": None,
    }
    return base | overrides


def yearly_rows(hwf_values: list[int]) -> list[dict]:
    return [
        {"year": 1991 + i, "HWN": 1 if v else 0, "HWF": v, "HWD": v, "HWM": 1.0 if v else None,
         "HWA": 44.0 if v else None, "low_quality": False}
        for i, v in enumerate(hwf_values)
    ]


def test_significant_increase_sentence():
    text = describe_trend("HWF", trend(), "Delhi, India", 1991, 2020)
    assert text == (
        "Heatwave days in Delhi, India increased by about 120% between 1991 and 2020 "
        "(+4.2 days/decade; statistically significant, p = 0.003)."
    )


def test_significant_absolute_change_sentence():
    text = describe_trend("HWF", trend(change_kind="abs", change_value=6.3), "Delhi", 1991, 2020)
    assert "increased by about 6.3 days between 1991 and 2020" in text


def test_not_significant_sentence_mentions_natural_variability():
    text = describe_trend("HWN", trend(significant=False, mk_p=0.31, sen_per_decade=0.2), "Paris", 1991, 2020)
    assert text == (
        "The number of heatwave events in Paris shows a slight upward change (+0.2 events/decade), "
        "but it is not statistically significant (p = 0.310) and may reflect natural year-to-year variability."
    )


def test_zero_slope_sentence():
    text = describe_trend("HWF", trend(significant=False, mk_p=0.9, sen_per_decade=0.0), "Paris", 1991, 2020)
    assert text == "Heatwave days in Paris show no clear trend between 1991 and 2020 (p = 0.900)."


def test_insufficient_years_sentence():
    text = describe_trend("HWF", {"n_years": 4, "reason": "insufficient_years"}, "Paris", 2017, 2020)
    assert text == "Heatwave days in Paris: not enough complete years (4) to assess a trend; at least 10 are needed."


def test_no_heatwaves_gives_single_plain_statement():
    insights, _ = build_insights("Oslo", 1991, 2020, yearly_rows([0] * 30), {}, ["nasa-power"], 1, [])
    assert insights == [
        "No heatwaves (3+ consecutive days above the local 95th percentile) were detected in Oslo between 1991 and 2020."
    ]


def test_build_insights_has_summary_then_trend_sentences():
    trends = {"HWF": trend(), "HWN": trend(change_value=80.0), "HWD": trend(significant=False, mk_p=0.2)}
    insights, _ = build_insights("Delhi", 1991, 2020, yearly_rows([5] * 30), trends, ["nasa-power"], 1, [])
    assert insights[0].startswith("Delhi averaged 5.0 heatwave days per year")
    assert insights[1].startswith("Heatwave days in Delhi increased")
    assert len(insights) == 4


def test_caveats_cover_fallback_area_average_and_low_quality_years():
    _, caveats = build_insights(
        "Box", 1991, 2020, yearly_rows([5] * 30), {"HWF": trend()},
        ["nasa-power", "open-meteo-era5"], 4, [2015],
    )
    joined = " ".join(caveats)
    assert "fallback" in joined
    assert "average of 4 grid points" in joined
    assert "2015" in joined


def test_significant_trend_with_zero_slope_does_not_claim_a_change():
    text = describe_trend("HWN", trend(sen_per_decade=0.0, mk_p=0.0004, change_kind="abs", change_value=0.0),
                          "Oslo", 1991, 2020)
    assert "increased" not in text and "decreased" not in text
    assert "close to zero" in text
    assert "p < 0.001" in text


def test_p_values_use_three_decimals_or_less_than_bound():
    not_sig = describe_trend("HWF", trend(significant=False, mk_p=0.0502, sen_per_decade=-2.3), "Delhi", 1991, 2020)
    assert "p = 0.050" in not_sig
    sig = describe_trend("HWF", trend(mk_p=0.0001), "Delhi", 1991, 2020)
    assert "p < 0.001" in sig
