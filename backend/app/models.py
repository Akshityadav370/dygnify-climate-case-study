from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import DATA_START_YEAR, last_complete_year

MAX_BOX_DEGREES = 5.0

Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]
Label = Annotated[str, Field(min_length=1, max_length=100)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PointRegion(StrictModel):
    type: Literal["point"]
    lat: Latitude
    lon: Longitude
    label: Label = "Selected point"


class BoxRegion(StrictModel):
    type: Literal["box"]
    south: Latitude
    west: Longitude
    north: Latitude
    east: Longitude
    label: Label = "Custom box"

    @model_validator(mode="after")
    def check_box(self):
        if self.south >= self.north or self.west >= self.east:
            raise ValueError("Box needs south < north and west < east.")
        if self.north - self.south > MAX_BOX_DEGREES or self.east - self.west > MAX_BOX_DEGREES:
            raise ValueError(f"Box can be at most {MAX_BOX_DEGREES:g}° × {MAX_BOX_DEGREES:g}°.")
        return self


Region = Annotated[PointRegion | BoxRegion, Field(discriminator="type")]


class AnalyzeRequest(StrictModel):
    hazard: Literal["heatwave"] = "heatwave"
    region: Region
    start_year: int
    end_year: int

    @model_validator(mode="after")
    def check_years(self):
        max_year = last_complete_year()
        if not (DATA_START_YEAR <= self.start_year <= self.end_year <= max_year):
            raise ValueError(f"Years must satisfy {DATA_START_YEAR} ≤ start_year ≤ end_year ≤ {max_year}.")
        return self


class YearlyRow(BaseModel):
    year: int
    HWN: int
    HWF: int
    HWD: int
    HWM: float | None
    HWA: float | None
    low_quality: bool


class EventOut(BaseModel):
    start: date
    end: date
    days: int
    peak_tmax: float
    mean_exceedance: float


class TrendOut(BaseModel):
    n_years: int
    sen_per_decade: float | None
    mk_p: float | None
    significant: bool
    ols_slope: float | None
    ols_intercept: float | None
    change_kind: Literal["pct", "abs"] | None
    change_value: float | None
    reason: str | None


class ChartSeries(BaseModel):
    values: list[float | None]
    rolling5: list[float | None]
    trendline: list[float | None]


class ChartOut(BaseModel):
    years: list[int]
    series: dict[str, ChartSeries]


class DataQuality(BaseModel):
    days: int
    removed: int
    interpolated: int
    low_quality_years: list[int]


class RegionOut(BaseModel):
    type: Literal["point", "box"]
    label: str
    bbox: dict[str, float] | None
    points: list[list[float]]


class YearsOut(BaseModel):
    start: int
    end: int


class ParamsOut(BaseModel):
    percentile: float
    min_days: int
    window: int
    baseline: list[int]


class AnalysisOut(BaseModel):
    id: str
    cached: bool
    hazard: str
    algo_version: str
    region: RegionOut
    sources_used: list[str]
    years: YearsOut
    params: ParamsOut
    yearly: list[YearlyRow]
    events: list[EventOut]
    threshold_by_doy: list[float | None]
    trends: dict[str, TrendOut]
    insights: list[str]
    caveats: list[str]
    data_quality: DataQuality
    chart: ChartOut
    created_at: datetime
