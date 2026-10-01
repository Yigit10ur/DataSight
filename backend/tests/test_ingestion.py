import codecs
import csv
import io

import pandas as pd
import pytest

from app.config import settings
from app.ingestion import DatasetValidationError, load_dataset
from app.ingestion.csv_loader import SNIFF_BYTES
from app.ingestion.validator import MAX_COLUMNS

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


@pytest.mark.parametrize("delimiter", [",", ";", "\t", "|"])
def test_sniffs_common_delimiters(delimiter):
    content = f"name{delimiter}age\nAda{delimiter}36\nGrace{delimiter}45\n".encode()
    frame = load_dataset("people.csv", content, MAX_BYTES)
    assert list(frame.columns) == ["name", "age"]
    assert frame["age"].tolist() == [36, 45]


def test_single_column_is_not_split_on_a_letter():
    frame = load_dataset("names.csv", b"name\nAda\nGrace\n", MAX_BYTES)
    assert list(frame.columns) == ["name"]
    assert frame["name"].tolist() == ["Ada", "Grace"]


def test_byte_order_mark_is_not_part_of_the_first_column_name():
    content = codecs.BOM_UTF8 + "name,city\nAda,İstanbul\n".encode()
    frame = load_dataset("people.csv", content, MAX_BYTES)
    assert list(frame.columns) == ["name", "city"]
    assert frame["city"].tolist() == ["İstanbul"]


def test_quoting_and_leading_spaces_are_kept_as_written():
    """Only the delimiter is sniffed; quality checks report the spaces themselves."""
    quoted = b'name,note\nAda,"hello, world"\nGrace,"a ""quoted"" word"\n'
    frame = load_dataset("notes.csv", quoted, MAX_BYTES)
    assert frame["note"].tolist() == ["hello, world", 'a "quoted" word']

    spaced = load_dataset("spaced.csv", b"name, channel\nAda, Online\n", MAX_BYTES)
    assert list(spaced.columns) == ["name", " channel"]
    assert spaced[" channel"].tolist() == [" Online"]


def test_carriage_return_line_endings():
    frame = load_dataset("old-mac.csv", b"a,b,c\r" + b"1,2,3\r" * 600, MAX_BYTES)
    assert frame.shape == (600, 3)


def test_sniffing_reads_a_bounded_sample_of_a_long_first_line(monkeypatch):
    """pandas' sep=None sniffed the whole first line, taking minutes on a long one."""
    sniffed = []
    sniff = csv.Sniffer.sniff

    def recording_sniff(self, sample, delimiters=None):
        sniffed.append(len(sample))
        return sniff(self, sample, delimiters)

    monkeypatch.setattr(csv.Sniffer, "sniff", recording_sniff)
    with pytest.raises(DatasetValidationError, match="no data rows"):
        load_dataset("long.csv", b"a" * 3_000_000, MAX_BYTES)
    assert sniffed and max(sniffed) <= SNIFF_BYTES


def test_rejects_a_header_with_too_many_columns():
    content = b"," * 5_000_000 + b"\n1\n"
    with pytest.raises(DatasetValidationError, match=f"at most {MAX_COLUMNS} are supported"):
        load_dataset("wide.csv", content, MAX_BYTES)


def test_rejects_a_workbook_with_too_many_columns():
    buffer = io.BytesIO()
    pd.DataFrame([range(MAX_COLUMNS + 1)]).to_excel(buffer, index=False)
    with pytest.raises(DatasetValidationError, match=f"at most {MAX_COLUMNS} are supported"):
        load_dataset("wide.xlsx", buffer.getvalue(), MAX_BYTES)


def test_accepts_the_maximum_number_of_columns():
    header = ",".join(f"c{i}" for i in range(MAX_COLUMNS))
    row = ",".join("1" for _ in range(MAX_COLUMNS))
    frame = load_dataset("wide.csv", f"{header}\n{row}\n".encode(), MAX_BYTES)
    assert frame.shape == (1, MAX_COLUMNS)


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


def test_names_excel_columns_as_text():
    buffer = io.BytesIO()
    pd.DataFrame([["North", 10, 12, 1]], columns=["region", 2023, 2024, "2023"]).to_excel(
        buffer, index=False
    )
    frame = load_dataset("sales.xlsx", buffer.getvalue(), MAX_BYTES)
    assert list(frame.columns) == ["region", "2023", "2024", "2023.1"]


def test_rejects_a_workbook_that_unpacks_past_the_limit(monkeypatch):
    buffer = io.BytesIO()
    pd.DataFrame({"a": ["x" * 100] * 1000}).to_excel(buffer, index=False)
    monkeypatch.setattr(settings, "max_workbook_bytes", 50_000)
    with pytest.raises(DatasetValidationError, match="unpacks to"):
        load_dataset("big.xlsx", buffer.getvalue(), MAX_BYTES)


def test_rejects_an_xlsx_that_is_not_a_workbook():
    with pytest.raises(DatasetValidationError, match="not an .xlsx workbook"):
        load_dataset("notes.xlsx", b"name,age\nAda,36\n", MAX_BYTES)


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
