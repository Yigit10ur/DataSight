from typing import Literal

from pydantic import BaseModel

ChartType = Literal["histogram", "bar", "scatter", "line", "box", "heatmap"]


class HistogramData(BaseModel):
    bin_edges: list[float]
    counts: list[int]


class BarData(BaseModel):
    categories: list[str]
    counts: list[int]
    other_count: int


class ScatterData(BaseModel):
    x: list[float]
    y: list[float]
    sampled_from: int


class LineData(BaseModel):
    x: list[str]
    y: list[float | None]
    aggregation: str


class BoxGroup(BaseModel):
    name: str
    count: int
    lower: float
    q1: float
    median: float
    q3: float
    upper: float


class BoxData(BaseModel):
    groups: list[BoxGroup]


class HeatmapData(BaseModel):
    columns: list[str]
    matrix: list[list[float | None]]


ChartData = HistogramData | BarData | ScatterData | LineData | BoxData | HeatmapData


class ChartSpec(BaseModel):
    id: str
    chart_type: ChartType
    title: str
    columns: list[str]
    x_label: str
    y_label: str
    data: ChartData


class ChartCollection(BaseModel):
    dataset_id: str
    charts: list[ChartSpec]
