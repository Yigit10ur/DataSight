from typing import Literal

from pydantic import BaseModel


class Histogram(BaseModel):
    bin_edges: list[float]
    counts: list[int]


class NumericSummary(BaseModel):
    column: str
    count: int
    missing_count: int
    mean: float | None
    median: float | None
    std: float | None
    minimum: float | None
    maximum: float | None
    q1: float | None
    q3: float | None
    skewness: float | None
    outlier_count: int
    outlier_ratio: float
    histogram: Histogram


class CategoryCount(BaseModel):
    value: str
    count: int
    ratio: float


class CategoricalSummary(BaseModel):
    column: str
    count: int
    missing_count: int
    unique_count: int
    top_categories: list[CategoryCount]
    rare_category_count: int


class CorrelationPair(BaseModel):
    column_a: str
    column_b: str
    pearson: float
    spearman: float | None
    sample_size: int


class GroupStats(BaseModel):
    """One group of a categorical column, described over a numeric column.

    The quartiles and whiskers are the box-plot shape, computed here so that the
    chart layer only has to relabel them.
    """

    name: str
    count: int
    mean: float
    median: float
    std: float
    minimum: float
    maximum: float
    q1: float
    q3: float
    lower_whisker: float
    upper_whisker: float


class GroupComparison(BaseModel):
    group_column: str
    value_column: str
    groups: list[GroupStats]
    sample_size: int
    ignored_group_count: int
    highest_group: str
    lowest_group: str
    mean_ratio: float | None
    median_difference: float
    effect_size: float | None
    p_value: float | None


class TimelinePoint(BaseModel):
    period: str
    value: float | None


class TimelineChange(BaseModel):
    period: str
    previous_period: str
    delta: float
    ratio: float | None


class Seasonality(BaseModel):
    cycle: str
    strongest: str
    weakest: str
    strength: float


class Timeline(BaseModel):
    time_column: str
    value_column: str
    aggregation: str
    points: list[TimelinePoint]
    start: str
    end: str
    sample_size: int
    window_periods: int
    first_window_mean: float
    last_window_mean: float
    change_ratio: float | None
    trend: Literal["rising", "falling", "flat"]
    slope_per_period: float
    monotonicity: float | None
    largest_change: TimelineChange | None
    seasonality: Seasonality | None


class DatasetAnalysis(BaseModel):
    dataset_id: str
    numeric: list[NumericSummary]
    categorical: list[CategoricalSummary]
    correlations: list[CorrelationPair]
    groups: list[GroupComparison]
    timelines: list[Timeline]
