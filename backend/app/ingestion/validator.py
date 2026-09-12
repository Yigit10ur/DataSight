from pathlib import Path

import pandas as pd

SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}


class DatasetValidationError(Exception):
    """Raised when an uploaded file cannot be accepted as a dataset."""


def validate_upload(filename: str, size_bytes: int, max_bytes: int) -> str:
    """Check the file before parsing it and return its normalised extension."""
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise DatasetValidationError(
            f"Unsupported file type '{extension or filename}'. Supported types: {supported}."
        )
    if size_bytes == 0:
        raise DatasetValidationError("The uploaded file is empty.")
    if size_bytes > max_bytes:
        limit_mb = max_bytes / (1024 * 1024)
        raise DatasetValidationError(f"File is larger than the {limit_mb:.0f} MB upload limit.")
    return extension


def validate_dataframe(frame: pd.DataFrame) -> None:
    """Check that a parsed file is usable as a dataset."""
    if frame.shape[1] == 0:
        raise DatasetValidationError("No columns could be parsed from the file.")
    if frame.shape[0] == 0:
        raise DatasetValidationError("The file contains headers but no data rows.")
