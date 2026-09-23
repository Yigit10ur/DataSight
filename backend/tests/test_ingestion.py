import io

import pandas as pd
import pytest

from app.ingestion import DatasetValidationError, load_dataset

MAX_BYTES = 10 * 1024 * 1024


def test_loads_comma_separated_csv():
    content = b"name,age\nAda,36\nGrace,45\n"
    frame = load_dataset("people.csv", content, MAX_BYTES)
    assert list(frame.columns) == ["name", "age"]
    assert len(frame) == 2


def test_sniffs_semicolon_delimiter():
    content = b"name;age\nAda;36\nGrace;45\n"
    frame = load_dataset("people.csv", content, MAX_BYTES)
    assert list(frame.columns) == ["name", "age"]


def test_falls_back_to_latin1_encoding():
    content = "city,count\nİstanbul,5\n".encode("latin-1", errors="replace")
    frame = load_dataset("cities.csv", content, MAX_BYTES)
    assert len(frame) == 1


def test_loads_excel():
    buffer = io.BytesIO()
    pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}).to_excel(buffer, index=False)
    frame = load_dataset("data.xlsx", buffer.getvalue(), MAX_BYTES)
    assert list(frame.columns) == ["a", "b"]
    assert len(frame) == 2


def test_rejects_unsupported_extension():
    with pytest.raises(DatasetValidationError, match="Unsupported file type"):
        load_dataset("notes.txt", b"hello", MAX_BYTES)


def test_rejects_empty_file():
    with pytest.raises(DatasetValidationError, match="empty"):
        load_dataset("empty.csv", b"", MAX_BYTES)


def test_rejects_file_over_size_limit():
    with pytest.raises(DatasetValidationError, match="upload limit"):
        load_dataset("big.csv", b"a,b\n1,2\n", max_bytes=4)


def test_rejects_header_only_file():
    with pytest.raises(DatasetValidationError, match="no data rows"):
        load_dataset("headers.csv", b"name,age\n", MAX_BYTES)


def test_workbook_xml_is_parsed_with_defusedxml():
    """openpyxl guards against XML entity attacks only when defusedxml is installed."""
    from openpyxl.xml import DEFUSEDXML

    assert DEFUSEDXML
