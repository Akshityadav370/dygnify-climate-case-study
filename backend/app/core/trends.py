"""Trend statistics for yearly hazard metrics.

- Sen's slope: median of all pairwise slopes; robust to outlier years.
- Mann-Kendall: non-parametric test of whether values consistently rise or fall.
- OLS: ordinary least-squares line, used only for drawing the trend line.
"""

import math
from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy.stats import norm

MIN_YEARS = 10
SIGNIFICANCE_LEVEL = 0.05


@dataclass
class Trend:
    n_years: int
    sen_per_decade: float | None = None
    mk_p: float | None = None
    significant: bool = False
    ols_slope: float | None = None
    ols_intercept: float | None = None
    change_kind: Literal["pct", "abs"] | None = None
    change_value: float | None = None
    reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def mann_kendall(values) -> tuple[int, float]:
    y = np.asarray(values, dtype=float)
    n = len(y)
    s = 0
    for i in range(n - 1):
        s += int(np.sign(y[i + 1 :] - y[i]).sum())
    _, tie_counts = np.unique(y, return_counts=True)
    variance = (n * (n - 1) * (2 * n + 5) - sum(t * (t - 1) * (2 * t + 5) for t in tie_counts)) / 18
    if variance <= 0:
        return s, 1.0
    if s > 0:
        z = (s - 1) / math.sqrt(variance)
    elif s < 0:
        z = (s + 1) / math.sqrt(variance)
    else:
        z = 0.0
    return s, float(2 * (1 - norm.cdf(abs(z))))


def sens_slope(x, y) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    slopes = [
        (y[j] - y[i]) / (x[j] - x[i]) for i in range(len(x) - 1) for j in range(i + 1, len(x)) if x[j] != x[i]
    ]
    slope = float(np.median(slopes))
    intercept = float(np.median(y) - slope * np.median(x))
    return slope, intercept


def ols(x, y) -> tuple[float, float]:
    slope, intercept = np.polyfit(np.asarray(x, dtype=float), np.asarray(y, dtype=float), 1)
    return float(slope), float(intercept)


def rolling_mean(values: list[float | None], window: int = 5) -> list[float | None]:
    s = pd.Series([np.nan if v is None else v for v in values], dtype="float64")
    smoothed = s.rolling(window, center=True, min_periods=3).mean()
    return [None if pd.isna(v) else round(float(v), 2) for v in smoothed]


def analyze_trend(
    years: list[int],
    values: list[float | None],
    excluded: set[int],
    start_year: int,
    end_year: int,
    allow_pct: bool = True,
) -> Trend:
    pairs = [(year, v) for year, v in zip(years, values) if v is not None and year not in excluded]
    if len(pairs) < MIN_YEARS:
        return Trend(n_years=len(pairs), reason="insufficient_years")

    x = [p[0] for p in pairs]
    y = [p[1] for p in pairs]
    slope, intercept = sens_slope(x, y)
    _, p_value = mann_kendall(y)
    ols_slope, ols_intercept = ols(x, y)

    # Change along the Sen line, not between two noisy individual years.
    start_value = intercept + slope * start_year
    end_value = intercept + slope * end_year
    if allow_pct:
        # Counts and day totals cannot go below zero, even if the fitted line does.
        start_value, end_value = max(start_value, 0.0), max(end_value, 0.0)
    if allow_pct and start_value >= 1:
        change_kind, change_value = "pct", (end_value - start_value) / start_value * 100
    else:
        change_kind, change_value = "abs", end_value - start_value

    reported_p = round(p_value, 4)
    return Trend(
        n_years=len(pairs),
        sen_per_decade=round(slope * 10, 2),
        mk_p=reported_p,
        significant=reported_p < SIGNIFICANCE_LEVEL,  # decide on the value we show, so text never contradicts it
        ols_slope=round(ols_slope, 4),
        ols_intercept=round(ols_intercept, 4),
        change_kind=change_kind,
        change_value=round(change_value, 1),
    )
