import codecs
import csv
import io

import pandas as pd

from app.ingestion.validator import MAX_COLUMNS, DatasetValidationError, too_many_columns

# utf-8-sig reads plain UTF-8 too, and drops a byte-order mark instead of leaving it
# on the first column name.
ENCODINGS = ("utf-8-sig", "latin-1")

DELIMITERS = ",;\t|:"

# The delimiter is read off the header line, and only this much of it. pandas'
# own sniffing (sep=None) reads the whole first line with the python engine: one
# long line took minutes and gigabytes, and an uploaded file chooses its lines.
SNIFF_BYTES = 4 * 1024


def load_csv(content: bytes) -> pd.DataFrame:
    """Parse CSV bytes, sniffing the delimiter and falling back across encodings."""
    delimiter = sniff_delimiter(content)
    # Counted on the raw header before pandas builds a column for every field.
    line_ends = [end for end in (content.find(b"\n"), content.find(b"\r")) if end != -1]
    header = content[: min(line_ends)] if line_ends else content
    fields = header.count(delimiter.encode()) + 1
    if fields > MAX_COLUMNS:
        raise DatasetValidationError(too_many_columns(fields))

    last_error: Exception | None = None
    for encoding in ENCODINGS:
        try:
            return pd.read_csv(io.BytesIO(content), sep=delimiter, encoding=encoding)
        except UnicodeDecodeError as error:
            last_error = error
        except pd.errors.EmptyDataError as error:
            raise DatasetValidationError("The CSV file contains no parsable data.") from error
        except pd.errors.ParserError as error:
            raise DatasetValidationError(f"The CSV file could not be parsed: {error}") from error

    raise DatasetValidationError(
        f"The CSV file could not be decoded using {', '.join(ENCODINGS)}."
    ) from last_error


def sniff_delimiter(content: bytes) -> str:
    """The header line's delimiter, or a comma when there is none to find.

    Only the delimiter is taken from the sniffed dialect, as pandas did. Its other
    guesses would turn off "" escapes and strip the leading spaces the quality
    checks report.

    latin-1 decodes any bytes and every candidate delimiter is ASCII, so the
    sample finds the same delimiter whatever the file's real encoding.
    """
    sample = bytes(content[:SNIFF_BYTES]).removeprefix(codecs.BOM_UTF8).decode("latin-1")
    header = sample.splitlines()[0] if sample else ""
    try:
        return csv.Sniffer().sniff(header, delimiters=DELIMITERS).delimiter
    except csv.Error:
        # A single column has no delimiter to find.
        return ","
