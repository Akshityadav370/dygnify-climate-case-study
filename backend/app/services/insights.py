"""Turns trend statistics into plain-language sentences.

Sentences are generated from fixed rules so the app never claims a trend
the statistics do not support.
"""

from app.core.trends import MIN_YEARS

# metric -> (subject, unit, verb for "show(s)")
METRIC_TEXT = {
    "HWF": ("Heatwave days", "days", "show"),
    "HWN": ("The number of heatwave events", "events", "shows"),
    "HWD": ("The longest heatwave each year", "days", "shows"),
}

# Insights are stored with this token and the region label is filled in per response,
# because one cached analysis can be requested under different labels.
REGION_TOKEN = "{region}"

SOURCE_NAMES = {
    "nasa-power": "NASA POWER (MERRA-2 reanalysis, ~50 km grid)",
    "open-meteo-era5": "Open-Meteo (ERA5 reanalysis, ~25 km grid)",
}


def format_p(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def describe_trend(metric: str, trend: dict, label: str, start_year: int, end_year: int) -> str:
    subject, unit, verb = METRIC_TEXT[metric]
    if trend.get("reason") == "insufficient_years":
        return (
            f"{subject} in {label}: not enough complete years ({trend['n_years']}) to assess a trend; "
            f"at least {MIN_YEARS} are needed."
        )

    sen = trend["sen_per_decade"]
    p = trend["mk_p"]
    if trend["significant"] and sen == 0:
        # Mann-Kendall can detect a consistent tendency in sparse counts while the
        # typical (median) change is zero; don't call that an increase or decrease.
        return (
            f"{subject} in {label} {verb} a statistically consistent tendency ({format_p(p)}), "
            f"but its typical size is close to zero ({sen:+.1f} {unit}/decade)."
        )
    if trend["significant"]:
        direction = "increased" if sen > 0 else "decreased"
        if trend["change_kind"] == "pct":
            amount = f"{abs(trend['change_value']):.0f}%"
        else:
            amount = f"{abs(trend['change_value']):.1f} {unit}"
        return (
            f"{subject} in {label} {direction} by about {amount} between {start_year} and {end_year} "
            f"({sen:+.1f} {unit}/decade; statistically significant, {format_p(p)})."
        )
    if sen == 0:
        return f"{subject} in {label} {verb} no clear trend between {start_year} and {end_year} ({format_p(p)})."
    direction = "upward" if sen > 0 else "downward"
    return (
        f"{subject} in {label} {verb} a slight {direction} change ({sen:+.1f} {unit}/decade), "
        f"but it is not statistically significant ({format_p(p)}) and may reflect natural year-to-year variability."
    )


def build_insights(
    label: str,
    start_year: int,
    end_year: int,
    yearly: list[dict],
    trends: dict[str, dict],
    sources_used: list[str],
    n_points: int,
    low_quality_years: list[int],
) -> tuple[list[str], list[str]]:
    insights: list[str] = []
    total_events = sum(row["HWN"] for row in yearly)
    if total_events == 0:
        insights.append(
            f"No heatwaves (3+ consecutive days above the local 95th percentile) were detected in {label} "
            f"between {start_year} and {end_year}."
        )
    else:
        usable = [row for row in yearly if not row["low_quality"]] or yearly
        avg_days = sum(row["HWF"] for row in usable) / len(usable)
        longest = max(yearly, key=lambda row: row["HWD"])
        insights.append(
            f"{label} averaged {avg_days:.1f} heatwave days per year between {start_year} and {end_year}; "
            f"the longest heatwave lasted {longest['HWD']} days ({longest['year']})."
        )
        for metric in ("HWF", "HWN", "HWD"):
            if metric in trends:
                insights.append(describe_trend(metric, trends[metric], label, start_year, end_year))

    sources = ", ".join(SOURCE_NAMES.get(s, s) for s in sources_used)
    caveats = [
        f"Data: {sources}. Gridded reanalysis smooths local extremes, so a single weather station "
        "may record more or hotter heatwave days.",
        "A heatwave is 3+ consecutive days with daily maximum temperature above the local 95th percentile "
        "for that time of year (1981–2010 baseline, ±7-day window).",
        "Trend significance uses the Mann-Kendall test (p < 0.05); trend size uses Sen's slope.",
    ]
    if n_points > 1:
        caveats.append(
            f"Region results are the average of {n_points} grid points; local hotspots inside the region may differ."
        )
    if "open-meteo-era5" in sources_used:
        caveats.append(
            "Some or all data came from the fallback source Open-Meteo (ERA5) because NASA POWER was unavailable."
        )
    if low_quality_years:
        years = ", ".join(str(y) for y in low_quality_years)
        caveats.append(f"Years with more than 10% missing data ({years}) are excluded from trend calculations.")
    return insights, caveats
