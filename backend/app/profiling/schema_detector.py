import re

import pandas as pd

from app.profiling.models import ColumnSchema, ColumnType

HIGH_CARDINALITY_MIN_UNIQUE = 50
TEXT_UNIQUE_RATIO = 0.5
TEXT_MEAN_LENGTH = 40
ID_UNIQUE_RATIO = 0.99
DATETIME_PARSE_RATIO = 0.9
DATETIME_SAMPLE_SIZE = 200
SAMPLE_VALUE_COUNT = 3

BOOLEAN_TOKENS = {"true", "false", "yes", "no", "y", "n", "evet", "hayır", "hayir", "0", "1"}
ID_NAME_PATTERN = re.compile(r"(^|[_\s])id$|^id$|_?(uuid|guid)$", re.IGNORECASE)


def _is_boolean(series: pd.Series) -> bool:
    if pd.api.types.is_bool_dtype(series):
        return True
    values = series.dropna().unique()
    if len(values) == 0 or len(values) > 2:
        return False
    return all(str(value).strip().lower() in BOOLEAN_TOKENS for value in values)


def _is_datetime(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if not pd.api.types.is_object_dtype(series):
        return False

    sample = series.dropna().head(DATETIME_SAMPLE_SIZE).astype(str)
    if sample.empty:
        return False
    # Bare numbers (e.g. a year column) parse as dates, so never treat them as datetimes.
    if pd.to_numeric(sample, errors="coerce").notna().all():
        return False

    parsed = pd.to_datetime(sample, errors="coerce", format="mixed", dayfirst=False)
    return parsed.notna().mean() >= DATETIME_PARSE_RATIO


def _is_text(series: pd.Series, unique_count: int, non_null_count: int) -> bool:
    if non_null_count == 0:
        return False
    unique_ratio = unique_count / non_null_count
    if unique_count > HIGH_CARDINALITY_MIN_UNIQUE and unique_ratio > TEXT_UNIQUE_RATIO:
        return True
    mean_length = series.dropna().astype(str).str.len().mean()
    return bool(mean_length and mean_length > TEXT_MEAN_LENGTH)


def detect_column_type(series: pd.Series) -> ColumnType:
    """Infer the semantic type of a column, independently of its pandas dtype."""
    non_null = series.dropna()
    if non_null.empty:
        return "empty"
    if _is_boolean(series):
        return "boolean"
    if _is_datetime(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if _is_text(series, non_null.nunique(), len(non_null)):
        return "text"
    return "categorical"


def is_probable_id(series: pd.Series, inferred_type: ColumnType, row_count: int) -> bool:
    """Flag columns that look like row identifiers rather than analysable features."""
    if row_count < 2 or inferred_type in {"boolean", "empty", "datetime"}:
        return False
    if pd.api.types.is_float_dtype(series):
        return False
    if series.nunique(dropna=True) / row_count < ID_UNIQUE_RATIO:
        return False
    if ID_NAME_PATTERN.search(str(series.name)):
        return True
    # Free text and measured numbers are near-unique too, so without an id-like name
    # only short repeated-token columns are treated as identifiers.
    return inferred_type == "categorical"


def profile_column(series: pd.Series, row_count: int) -> ColumnSchema:
    """Build the schema description for a single column."""
    missing_count = int(series.isna().sum())
    unique_count = int(series.nunique(dropna=True))
    inferred_type = detect_column_type(series)
    samples = series.dropna().unique()[:SAMPLE_VALUE_COUNT]

    return ColumnSchema(
        name=str(series.name),
        dtype=str(series.dtype),
        inferred_type=inferred_type,
        missing_count=missing_count,
        missing_ratio=missing_count / row_count if row_count else 0.0,
        unique_count=unique_count,
        is_constant=unique_count <= 1,
        is_probable_id=is_probable_id(series, inferred_type, row_count),
        is_high_cardinality=(
            inferred_type in {"categorical", "text"} and unique_count > HIGH_CARDINALITY_MIN_UNIQUE
        ),
        sample_values=[str(value) for value in samples],
    )


def detect_schema(frame: pd.DataFrame) -> list[ColumnSchema]:
    """Describe every column in the dataset."""
    row_count = len(frame)
    return [profile_column(frame[column], row_count) for column in frame.columns]
