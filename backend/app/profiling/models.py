from typing import Literal

from pydantic import BaseModel

ColumnType = Literal["numeric", "categorical", "boolean", "datetime", "text", "empty"]


class ColumnSchema(BaseModel):
    name: str
    dtype: str
    inferred_type: ColumnType
    missing_count: int
    missing_ratio: float
    unique_count: int
    is_constant: bool
    is_probable_id: bool
    is_high_cardinality: bool
    sample_values: list[str]


class DatasetProfile(BaseModel):
    dataset_id: str
    filename: str
    rows: int
    columns: int
    type_counts: dict[str, int]
    missing_cells: int
    missing_ratio: float
    duplicate_rows: int
    column_schemas: list[ColumnSchema]
