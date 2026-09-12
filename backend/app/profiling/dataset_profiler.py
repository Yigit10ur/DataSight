from collections import Counter

import pandas as pd

from app.profiling.models import DatasetProfile
from app.profiling.schema_detector import detect_schema


def profile_dataset(dataset_id: str, filename: str, frame: pd.DataFrame) -> DatasetProfile:
    """Produce the dataset-level overview shown immediately after upload."""
    rows, columns = frame.shape
    column_schemas = detect_schema(frame)
    type_counts = Counter(schema.inferred_type for schema in column_schemas)
    missing_cells = int(frame.isna().sum().sum())
    total_cells = rows * columns

    return DatasetProfile(
        dataset_id=dataset_id,
        filename=filename,
        rows=rows,
        columns=columns,
        type_counts=dict(type_counts),
        missing_cells=missing_cells,
        missing_ratio=missing_cells / total_cells if total_cells else 0.0,
        duplicate_rows=int(frame.duplicated().sum()),
        column_schemas=column_schemas,
    )
