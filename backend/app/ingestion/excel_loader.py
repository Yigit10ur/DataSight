import io
import zipfile

import pandas as pd

from app.config import settings
from app.ingestion.validator import DatasetValidationError


def load_excel(content: bytes) -> pd.DataFrame:
    """Parse the first sheet of an .xlsx workbook."""
    check_unpacked_size(content, settings.max_workbook_bytes)
    try:
        frame = pd.read_excel(io.BytesIO(content), sheet_name=0, engine="openpyxl")
    except (ValueError, zipfile.BadZipFile) as error:
        raise DatasetValidationError(f"The Excel file could not be parsed: {error}") from error
    frame.columns = text_column_names(frame.columns)
    return frame


def check_unpacked_size(content: bytes, max_bytes: int) -> None:
    """Refuse a workbook that would unpack to more than max_bytes, before reading it.

    The sizes come from the zip's own directory, which the file chooses. That is
    still a bound: zipfile stops reading each entry at its declared size, so an
    entry that claims less than it holds is cut short rather than read in full.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            unpacked = sum(entry.file_size for entry in archive.infolist())
    except zipfile.BadZipFile as error:
        raise DatasetValidationError(
            "The Excel file could not be parsed: it is not an .xlsx workbook."
        ) from error
    if unpacked > max_bytes:
        limit_mb = max_bytes / (1024 * 1024)
        raise DatasetValidationError(
            f"This workbook unpacks to {unpacked / (1024 * 1024):,.0f} MB, more than the "
            f"{limit_mb:,.0f} MB limit. Save the sheet as CSV and upload that instead."
        )


def text_column_names(columns: pd.Index) -> list[str]:
    """Every column name as text, still unique.

    A workbook header keeps its cells' types, so a sheet of years has columns named
    2023 and 2024 — integers. Everything downstream names columns as text, as a CSV
    header always does, and looked up "2023" in a frame that only had 2023. Turning
    names into text can make two equal (a number 2023 beside the text "2023"), so a
    repeat is suffixed the way pandas suffixes repeated CSV headers.
    """
    names: list[str] = []
    taken: set[str] = set()
    for column in columns:
        name = base = str(column)
        repeat = 0
        while name in taken:
            repeat += 1
            name = f"{base}.{repeat}"
        taken.add(name)
        names.append(name)
    return names
