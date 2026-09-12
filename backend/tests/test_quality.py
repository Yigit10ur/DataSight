import numpy as np
import pandas as pd

from app.profiling import profile_dataset
from app.quality import check_dataset_quality, normalise_category


def issues_for(frame: pd.DataFrame):
    return check_dataset_quality(frame, profile_dataset("x", "f.csv", frame)).issues


def types_for(frame: pd.DataFrame) -> list[str]:
    return [issue.issue_type for issue in issues_for(frame)]


def issue_of(frame: pd.DataFrame, issue_type: str):
    return next(issue for issue in issues_for(frame) if issue.issue_type == issue_type)


def test_missing_values_are_reported_with_severity_by_share():
    frame = pd.DataFrame({"age": [1.0, None, None, None]})
    issue = issue_of(frame, "missing_values")

    assert issue.severity == "serious"
    assert issue.metrics["missing_count"] == 3


def test_small_share_of_missing_values_is_only_informational():
    frame = pd.DataFrame({"age": [*np.arange(195, dtype=float), *[None] * 5]})
    assert issue_of(frame, "missing_values").severity == "info"


def test_negligible_missing_values_are_not_reported():
    frame = pd.DataFrame({"age": [*np.arange(999, dtype=float), None]})
    assert "missing_values" not in types_for(frame)


def test_fully_empty_column_is_reported_as_empty_not_as_missing():
    frame = pd.DataFrame({"note": [None, None, None], "age": [1.0, 2.0, 3.0]})
    types = types_for(frame)

    assert "empty_column" in types
    assert "missing_values" not in types


def test_duplicate_rows_are_reported():
    frame = pd.DataFrame({"a": [1, 2, 1, 2], "b": ["x", "y", "x", "y"]})
    issue = issue_of(frame, "duplicate_rows")

    assert issue.metrics["duplicate_rows"] == 2
    assert issue.severity == "warning"


def test_outliers_are_reported_for_numeric_columns():
    frame = pd.DataFrame({"revenue": [*np.arange(1, 100, dtype=float), 50000.0]})
    issue = issue_of(frame, "outliers")

    assert issue.metrics["outlier_count"] == 1
    assert issue.metrics["maximum"] == 50000.0


def test_clean_numeric_column_reports_no_outliers():
    frame = pd.DataFrame({"revenue": np.arange(100, dtype=float)})
    assert "outliers" not in types_for(frame)


def test_turkish_spellings_of_one_city_are_flagged_as_one_category():
    frame = pd.DataFrame({"city": ["İstanbul", "istanbul", "Istanbul", "Ankara"] * 5})
    issue = issue_of(frame, "suspicious_categories")

    assert issue.metrics["group_count"] == 1
    assert sorted(issue.metrics["groups"][0]) == sorted(["İstanbul", "istanbul", "Istanbul"])


def test_distinct_categories_are_not_flagged():
    frame = pd.DataFrame({"city": ["Ankara", "Izmir", "Bursa"] * 5})
    assert "suspicious_categories" not in types_for(frame)


def test_stray_whitespace_is_reported():
    frame = pd.DataFrame({"city": ["Ankara", " Ankara", "Izmir "] * 4})
    assert issue_of(frame, "inconsistent_formatting").metrics["affected_rows"] == 8


def test_numbers_stored_as_text_are_reported():
    frame = pd.DataFrame({"amount": ["1", "2", "3", "4", "n/a"] * 4})
    issue = issue_of(frame, "mistyped_column")

    assert issue.metrics["numeric_ratio"] >= 0.75


def test_genuine_text_column_is_not_reported_as_mistyped():
    frame = pd.DataFrame({"city": ["Ankara", "Izmir", "Bursa"] * 5})
    assert "mistyped_column" not in types_for(frame)


def test_constant_and_identifier_columns_are_reported():
    frame = pd.DataFrame(
        {
            "customer_id": [f"C{i}" for i in range(10)],
            "country": ["TR"] * 10,
        }
    )
    types = types_for(frame)

    assert "constant_column" in types
    assert "identifier_column" in types


def test_identifier_column_is_not_also_reported_as_high_cardinality():
    frame = pd.DataFrame({"customer_id": [f"C{i}" for i in range(100)]})
    types = types_for(frame)

    assert types.count("identifier_column") == 1
    assert "high_cardinality" not in types


def test_issues_are_sorted_most_severe_first():
    frame = pd.DataFrame(
        {
            "country": ["TR"] * 10,
            "age": [1.0, None, None, None, None, None, None, None, None, None],
        }
    )
    severities = [issue.severity for issue in issues_for(frame)]

    assert severities == sorted(severities, key=["serious", "warning", "info"].index)


def test_clean_dataset_reports_nothing():
    frame = pd.DataFrame(
        {
            "city": ["Ankara", "Izmir", "Bursa"] * 10,
            "revenue": np.linspace(100, 400, 30),
        }
    )
    assert issues_for(frame) == []


def test_normalisation_folds_case_accents_and_spacing():
    assert normalise_category("  İSTANBUL  ") == normalise_category("istanbul")
    assert normalise_category("New  York") == normalise_category("new york")
    assert normalise_category("Ankara") != normalise_category("Izmir")
