import io

import pandas as pd

from app.ingestion.validator import DatasetValidationError

ENCODINGS = ("utf-8", "utf-8-sig", "latin-1")


def load_csv(content: bytes) -> pd.DataFrame:
    """Parse CSV bytes, sniffing the delimiter and falling back across encodings."""
    last_error: Exception | None = None
    for encoding in ENCODINGS:
        try:
            # sep=None asks pandas to sniff the delimiter, which requires the python engine.
            return pd.read_csv(io.BytesIO(content), sep=None, engine="python", encoding=encoding)
        except UnicodeDecodeError as error:
            last_error = error
        except pd.errors.EmptyDataError as error:
            raise DatasetValidationError("The CSV file contains no parsable data.") from error
        except pd.errors.ParserError as error:
            raise DatasetValidationError(f"The CSV file could not be parsed: {error}") from error

    raise DatasetValidationError(
        f"The CSV file could not be decoded using {', '.join(ENCODINGS)}."
    ) from last_error
