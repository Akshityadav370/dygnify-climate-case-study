import calendar
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

# Values outside this range are physically impossible for 2 m air temperature.
TMAX_MIN_C = -90.0
TMAX_MAX_C = 60.0


@dataclass
class CleanResult:
    tmax: pd.Series  # daily DatetimeIndex, NaN = missing
    removed: int  # values dropped as physically impossible
    interpolated: int  # missing days filled by interpolation


def to_daily_series(start: date, values: Sequence[float | None]) -> pd.Series:
    index = pd.date_range(start=start, periods=len(values), freq="D")
    return pd.Series([np.nan if v is None else float(v) for v in values], index=index, dtype="float64")


def fill_short_gaps(s: pd.Series, max_gap_days: int) -> tuple[pd.Series, int]:
    """Linearly interpolate runs of missing days no longer than `max_gap_days`.

    Longer gaps stay missing (we never invent long stretches of weather), and
    gaps at the very start or end are not extrapolated.
    """
    missing = s.isna()
    if not missing.any():
        return s, 0
    run_id = missing.ne(missing.shift(fill_value=False)).cumsum()
    run_length = missing.groupby(run_id).transform("size")
    fillable = missing & (run_length <= max_gap_days)
    interpolated = s.interpolate(method="linear", limit_area="inside")
    out = s.where(~fillable, interpolated)
    return out, int((fillable & out.notna()).sum())


def clean_tmax(points: Sequence[pd.Series], max_gap_days: int = 2) -> CleanResult:
    """Remove impossible values per point, area-average the points, fill short gaps."""
    removed = 0
    bounded = []
    for s in points:
        bad = (s < TMAX_MIN_C) | (s > TMAX_MAX_C)
        removed += int(bad.sum())
        bounded.append(s.mask(bad))
    regional = pd.concat(bounded, axis=1).mean(axis=1, skipna=True)
    filled, interpolated = fill_short_gaps(regional, max_gap_days)
    return CleanResult(tmax=filled, removed=removed, interpolated=interpolated)


def low_quality_years(s: pd.Series, years: Iterable[int], max_missing_fraction: float = 0.10) -> list[int]:
    """Years where more than `max_missing_fraction` of calendar days have no value."""
    flagged = []
    for year in years:
        expected = 366 if calendar.isleap(year) else 365
        present = int(s.loc[f"{year}-01-01":f"{year}-12-31"].notna().sum())
        if (expected - present) / expected > max_missing_fraction:
            flagged.append(year)
    return flagged
