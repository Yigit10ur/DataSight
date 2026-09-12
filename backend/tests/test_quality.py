import numpy as np
import pandas as pd
import pytest

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


def score_for(frame: pd.DataFrame):
    return check_dataset_quality(frame, profile_dataset("x", "f.csv", frame)).score


def dimension_of(frame: pd.DataFrame, name: str):
    return next(dimension for dimension in score_for(frame).dimensions if dimension.name == name)


def test_clean_dataset_scores_full_marks():
    frame = pd.DataFrame(
        {
            "city": ["Ankara", "Izmir", "Bursa"] * 10,
            "revenue": np.linspace(100, 400, 30),
        }
    )
    score = score_for(frame)

    assert score.score == 100
    assert all(dimension.score == 100 for dimension in score.dimensions)


def test_missing_values_lower_completeness_in_proportion():
    frame = pd.DataFrame(
        {
            "a": [1.0] * 100,
            "b": [1.0] * 50 + [None] * 50,
        }
    )
    completeness = dimension_of(frame, "completeness")

    # A quarter of the cells are gone, against a tolerance of one half.
    assert completeness.observed == 0.25
    assert completeness.score == 50


def test_an_empty_column_costs_the_share_of_cells_it_holds():
    frame = pd.DataFrame({"a": [1.0] * 20, "b": [1.0] * 20, "empty": [None] * 20})
    completeness = dimension_of(frame, "completeness")

    assert completeness.observed == pytest.approx(1 / 3)
    assert completeness.contributions[0].columns == ["empty"]
    assert completeness.contributions[0].share == pytest.approx(1 / 3)


def test_duplicate_rows_lower_the_duplicate_dimension():
    frame = pd.DataFrame({"city": ["Ankara"] * 10 + ["Izmir"] * 10, "n": [1] * 10 + [2] * 10})
    duplicates = dimension_of(frame, "duplicates")

    assert duplicates.observed == pytest.approx(18 / 20)
    assert duplicates.score == 0


def test_one_inconsistent_column_of_two_halves_the_consistency_score():
    frame = pd.DataFrame(
        {
            "city": ["Istanbul", "istanbul"] * 15,
            "segment": ["smb", "enterprise"] * 15,
        }
    )
    consistency = dimension_of(frame, "consistency")

    assert consistency.observed == 0.5
    assert consistency.score == 0
    assert consistency.contributions[0].columns == ["city"]


def test_two_problems_in_one_column_count_as_one_inconsistent_column():
    frame = pd.DataFrame(
        {
            "city": [" Istanbul", "istanbul ", "Ankara", "Bursa"] * 10,
            "a": ["x", "y"] * 20,
            "b": ["x", "y"] * 20,
            "c": ["x", "y"] * 20,
        }
    )
    consistency = dimension_of(frame, "consistency")

    assert consistency.observed == 0.25
    assert len(consistency.contributions) == 1
    assert len(consistency.contributions[0].issue_ids) == 2


def test_a_column_stored_as_text_lowers_type_consistency():
    frame = pd.DataFrame(
        {
            "score_text": [f"{value}" for value in range(40)],
            "city": ["Ankara", "Izmir"] * 20,
        }
    )
    type_consistency = dimension_of(frame, "type_consistency")

    assert type_consistency.observed == 0.5
    assert type_consistency.score == 0


def test_a_text_only_dataset_cannot_be_scored_for_outliers():
    frame = pd.DataFrame({"city": ["Ankara", "Izmir", "Bursa"] * 10})
    outliers = dimension_of(frame, "outliers")

    assert outliers.applicable is False
    assert outliers.weight == 0


def test_weight_of_an_unmeasurable_dimension_moves_to_the_others():
    frame = pd.DataFrame({"city": ["Ankara", "Izmir", "Bursa"] * 10})
    score = score_for(frame)
    measurable = [dimension for dimension in score.dimensions if dimension.applicable]

    assert sum(dimension.weight for dimension in measurable) == pytest.approx(1.0)
    assert all(dimension.weight == 0 for dimension in score.dimensions if not dimension.applicable)


def test_an_unmeasurable_dimension_does_not_lift_the_total():
    # Only the two spellings of one city, repeated: consistency and duplicates both
    # score 0, completeness and type consistency both score 100, and there are no
    # numbers to judge for outliers.
    frame = pd.DataFrame({"city": ["Istanbul", "istanbul"] * 15})
    score = score_for(frame)

    measurable = 0.30 + 0.20 + 0.20 + 0.15
    assert score.score == round(100 * (0.30 + 0.20) / measurable)
    # Had the unmeasurable outlier dimension kept its free 100, this would be 65.
    assert score.score < 65


def test_the_score_never_leaves_the_scale():
    frame = pd.DataFrame(
        {
            "city": ["Istanbul", "istanbul "] * 15,
            "text_number": [f"{value % 3}" for value in range(30)],
            "broken": [None] * 30,
        }
    )
    score = score_for(frame)

    assert 0 <= score.score <= 100
    assert all(0 <= dimension.score <= 100 for dimension in score.dimensions)


def test_structural_notes_are_not_counted_against_the_score():
    frame = pd.DataFrame(
        {
            "order_id": [f"ORD-{index}" for index in range(30)],
            "country": ["TR"] * 30,
            "revenue": np.linspace(100, 400, 30),
        }
    )
    score = score_for(frame)

    assert {issue.issue_type for issue in issues_for(frame)} == {
        "identifier_column",
        "constant_column",
    }
    assert score.score == 100


def test_every_contribution_names_a_reported_issue():
    frame = pd.DataFrame(
        {
            "city": ["Istanbul", "istanbul", "Ankara", None] * 10,
            "revenue": [*np.linspace(100, 200, 39), 90000.0],
        }
    )
    report = check_dataset_quality(frame, profile_dataset("x", "f.csv", frame))
    reported = {issue.id for issue in report.issues}

    for dimension in report.score.dimensions:
        for contribution in dimension.contributions:
            assert set(contribution.issue_ids) <= reported
