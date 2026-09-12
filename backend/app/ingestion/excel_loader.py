import io

import pandas as pd

from app.ingestion.validator import DatasetValidationError


def load_excel(content: bytes) -> pd.DataFrame:
    """Parse the first sheet of an .xlsx workbook."""
    try:
        return pd.read_excel(io.BytesIO(content), sheet_name=0, engine="openpyxl")
    except ValueError as error:
        raise DatasetValidationError(f"The Excel file could not be parsed: {error}") from error
