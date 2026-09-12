import numpy as np
import pandas as pd

from app.profiling import detect_column_type, profile_dataset


def test_detects_numeric_column():
    assert detect_column_type(pd.Series([1.5, 2.5, 3.0])) == "numeric"


def test_detects_boolean_column():
    assert detect_column_type(pd.Series([True, False, True])) == "boolean"
    assert detect_column_type(pd.Series(["yes", "no", "yes"])) == "boolean"


def test_detects_datetime_column():
    assert detect_column_type(pd.Series(["2024-01-01", "2024-02-15", "2024-03-30"])) == "datetime"


def test_numeric_strings_are_not_datetimes():
    assert detect_column_type(pd.Series(["1990", "2001", "2014", "1977"])) != "datetime"


def test_detects_categorical_column():
    assert detect_column_type(pd.Series(["Istanbul", "Ankara", "Izmir", "Ankara"])) == "categorical"


def test_detects_text_column():
    sentences = pd.Series([f"This is a reasonably long free-text comment number {i}" for i in range(60)])
    assert detect_column_type(sentences) == "text"


def test_detects_empty_column():
    assert detect_column_type(pd.Series([None, np.nan, None])) == "empty"


def test_profile_reports_dataset_overview():
    frame = pd.DataFrame(
        {
            "customer_id": ["a", "b", "c", "c"],
            "age": [30, None, 41, 41],
            "city": ["Ankara", "Izmir", "Ankara", "Ankara"],
            "country": ["TR", "TR", "TR", "TR"],
        }
    )
    profile = profile_dataset("abc123", "customers.csv", frame)

    assert profile.rows == 4
    assert profile.columns == 4
    assert profile.duplicate_rows == 1
    assert profile.missing_cells == 1
    assert profile.missing_ratio == 1 / 16
    assert profile.type_counts["categorical"] >= 2
    assert profile.type_counts["numeric"] == 1


def test_profile_flags_id_and_constant_columns():
    frame = pd.DataFrame(
        {
            "customer_id": ["a", "b", "c", "d"],
            "country": ["TR", "TR", "TR", "TR"],
        }
    )
    schemas = {schema.name: schema for schema in profile_dataset("x", "f.csv", frame).column_schemas}

    assert schemas["customer_id"].is_probable_id
    assert schemas["country"].is_constant
    assert not schemas["country"].is_probable_id


def test_near_unique_free_text_is_not_an_id():
    frame = pd.DataFrame(
        {"note": [f"Customer left a fairly long free text comment number {i}" for i in range(200)]}
    )
    schema = profile_dataset("x", "f.csv", frame).column_schemas[0]

    assert schema.inferred_type == "text"
    assert not schema.is_probable_id


def test_high_cardinality_applies_only_to_categorical_and_text():
    frame = pd.DataFrame(
        {
            "revenue": np.linspace(100, 900, 200),
            "city": [f"city_{i}" for i in range(200)],
        }
    )
    schemas = {schema.name: schema for schema in profile_dataset("x", "f.csv", frame).column_schemas}

    assert not schemas["revenue"].is_high_cardinality
    assert schemas["city"].is_high_cardinality


def test_profile_reports_missing_ratio_per_column():
    frame = pd.DataFrame({"age": [30, None, None, 41]})
    schema = profile_dataset("x", "f.csv", frame).column_schemas[0]

    assert schema.missing_count == 2
    assert schema.missing_ratio == 0.5
