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


class DatasetAnalysis(BaseModel):
    dataset_id: str
    numeric: list[NumericSummary]
    categorical: list[CategoricalSummary]
    correlations: list[CorrelationPair]
