"""Heatwave detection.

Definition: a heatwave is >= `min_days` consecutive days whose daily maximum
temperature is above the `percentile` of that calendar day's baseline
climatology (baseline years, +/- `window_days` around the day).
"""

from dataclasses import asdict, dataclass
from datetime import date

import numpy as np
import pandas as pd

METRIC_KEYS = ("HWN", "HWF", "HWD", "HWM", "HWA")


@dataclass(frozen=True)
class HeatwaveParams:
    percentile: float = 95.0
    window_days: int = 7
    min_days: int = 3
    baseline: tuple[int, int] = (1981, 2010)


@dataclass
class HeatwaveEvent:
    start: date
    end: date
    days: int
    peak_tmax: float
    mean_exceedance: float  # mean degrees C above the threshold over the event

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start"] = self.start.isoformat()
        d["end"] = self.end.isoformat()
        return d


@dataclass
class HeatwaveResult:
    thresholds: list[float | None]  # 365 values, index = day-of-year - 1
    events: list[HeatwaveEvent]
    yearly: list[dict]


def day_of_year_365(index: pd.DatetimeIndex) -> np.ndarray:
    """Day of year on a 365-day calendar: Feb 29 shares Feb 28's slot (59)."""
    doy = index.dayofyear.to_numpy()
    shift = np.asarray(index.is_leap_year) & (doy >= 60)
    return np.where(shift, doy - 1, doy)


def compute_thresholds(tmax: pd.Series, params: HeatwaveParams) -> np.ndarray:
    start_year, end_year = params.baseline
    base = tmax.loc[f"{start_year}-01-01":f"{end_year}-12-31"]
    keys = day_of_year_365(base.index)
    values = base.to_numpy()
    thresholds = np.full(365, np.nan)
    for day in range(1, 366):
        distance = np.abs(keys - day)
        distance = np.minimum(distance, 365 - distance)  # circular: Dec 31 is next to Jan 1
        window = values[distance <= params.window_days]
        window = window[~np.isnan(window)]
        if window.size:
            thresholds[day - 1] = np.percentile(window, params.percentile)
    return thresholds


def detect_events(tmax: pd.Series, thresholds: np.ndarray, min_days: int) -> list[HeatwaveEvent]:
    threshold_per_day = thresholds[day_of_year_365(tmax.index) - 1]
    values = tmax.to_numpy()
    hot = values > threshold_per_day  # NaN compares False, so missing days break runs
    events: list[HeatwaveEvent] = []
    i, n = 0, len(values)
    while i < n:
        if not hot[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and hot[j + 1]:
            j += 1
        length = j - i + 1
        if length >= min_days:
            segment = values[i : j + 1]
            exceedance = segment - threshold_per_day[i : j + 1]
            events.append(
                HeatwaveEvent(
                    start=tmax.index[i].date(),
                    end=tmax.index[j].date(),
                    days=length,
                    peak_tmax=round(float(segment.max()), 2),
                    mean_exceedance=round(float(exceedance.mean()), 2),
                )
            )
        i = j + 1
    return events


def yearly_metrics(events: list[HeatwaveEvent], years: range, low_quality: set[int]) -> list[dict]:
    rows = []
    for year in years:
        year_events = [e for e in events if e.start.year == year]
        total_days = sum(e.days for e in year_events)
        rows.append(
            {
                "year": year,
                "HWN": len(year_events),
                "HWF": total_days,
                "HWD": max((e.days for e in year_events), default=0),
                "HWM": round(sum(e.mean_exceedance * e.days for e in year_events) / total_days, 2)
                if total_days
                else None,
                "HWA": max((e.peak_tmax for e in year_events), default=None),
                "low_quality": year in low_quality,
            }
        )
    return rows


def analyze(
    tmax: pd.Series, years: range, low_quality: set[int], params: HeatwaveParams = HeatwaveParams()
) -> HeatwaveResult:
    thresholds = compute_thresholds(tmax, params)
    # Detect over the full series so events crossing the range edges are complete,
    # then keep only events that start inside the selected years.
    events = [e for e in detect_events(tmax, thresholds, params.min_days) if e.start.year in years]
    return HeatwaveResult(
        thresholds=[None if np.isnan(t) else round(float(t), 2) for t in thresholds],
        events=events,
        yearly=yearly_metrics(events, years, low_quality),
    )
