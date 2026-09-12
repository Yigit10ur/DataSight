import pandas as pd

from app.ingestion.csv_loader import load_csv
from app.ingestion.excel_loader import load_excel
from app.ingestion.validator import (
    SUPPORTED_EXTENSIONS,
    DatasetValidationError,
    validate_dataframe,
    validate_upload,
)

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "DatasetValidationError",
    "load_dataset",
    "validate_dataframe",
    "validate_upload",
]


def load_dataset(filename: str, content: bytes, max_bytes: int) -> pd.DataFrame:
    """Validate an uploaded file and parse it into a DataFrame."""
    extension = validate_upload(filename, len(content), max_bytes)
    frame = load_csv(content) if extension == ".csv" else load_excel(content)
    validate_dataframe(frame)
    return frame
