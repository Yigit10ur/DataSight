import json
from typing import Any

import pandas as pd
from pydantic import BaseModel

MAX_PREVIEW_ROWS = 200


class DatasetPreview(BaseModel):
    dataset_id: str
    columns: list[str]
    rows: list[dict[str, Any]]
    total_rows: int


def build_preview(dataset_id: str, frame: pd.DataFrame, limit: int) -> DatasetPreview:
    """Return the first rows of a dataset as JSON-safe records."""
    limit = max(1, min(limit, MAX_PREVIEW_ROWS))
    head = frame.head(limit)
    # to_json normalises NaN to null and numpy/datetime scalars to JSON primitives.
    rows = json.loads(head.to_json(orient="records", date_format="iso"))

    return DatasetPreview(
        dataset_id=dataset_id,
        columns=[str(column) for column in frame.columns],
        rows=rows,
        total_rows=len(frame),
    )
