import numpy as np
import pandas as pd
import pytest

from app.analysis import analyze_categorical, analyze_correlations, analyze_dataset, analyze_numeric
from app.profiling import profile_dataset


def test_numeric_summary_reports_descriptive_statistics():
    summary = analyze_numeric(pd.Series([1, 2, 3, 4, 5], name="value"))

    assert summary.count == 5
    assert summary.mean == 3
    assert summary.median == 3
    assert summary.minimum == 1
    assert summary.maximum == 5
    assert summary.q1 == 2
    assert summary.q3 == 4


def test_numeric_summary_excludes_missing_values():
    summary = analyze_numeric(pd.Series([10, None, 20, None], name="value"))

    assert summary.count == 2
    assert summary.missing_count == 2
    assert summary.mean == 15


def test_numeric_summary_flags_iqr_outliers():
    summary = analyze_numeric(pd.Series([*range(1, 21), 500], name="value"))

    assert summary.outlier_count == 1
    assert summary.outlier_ratio == 1 / 21


def test_constant_column_has_no_outliers_and_no_spread():
    summary = analyze_numeric(pd.Series([7.0] * 10, name="value"))

    assert summary.outlier_count == 0
    assert summary.std == 0
    assert summary.skewness is None or summary.skewness == 0


def test_single_value_column_returns_null_statistics_instead_of_nan():
    summary = analyze_numeric(pd.Series([5.0], name="value"))

    assert summary.std is None
    assert summary.skewness is None
    assert summary.mean == 5


def test_histogram_covers_the_value_range():
    summary = analyze_numeric(pd.Series(np.arange(100), name="value"))

    assert sum(summary.histogram.counts) == 100
    assert summary.histogram.bin_edges[0] == 0
    assert summary.histogram.bin_edges[-1] == 99


def test_categorical_summary_ranks_categories_by_frequency():
    series = pd.Series(["a", "b", "a", "c", "a", "b"], name="letter")
    summary = analyze_categorical(series)

    assert summary.unique_count == 3
    assert summary.top_categories[0].value == "a"
    assert summary.top_categories[0].count == 3
    assert summary.top_categories[0].ratio == 0.5


def test_categorical_summary_counts_rare_categories():
    series = pd.Series(["common"] * 300 + ["rare_one", "rare_two"], name="label")
    summary = analyze_categorical(series)

    assert summary.rare_category_count == 2


def test_correlation_detects_a_strong_positive_relationship():
    frame = pd.DataFrame({"spend": [1, 2, 3, 4, 5], "revenue": [2, 4, 6, 8, 10]})
    pairs = analyze_correlations(frame, ["spend", "revenue"])

    assert len(pairs) == 1
    assert pairs[0].pearson == pytest.approx(1.0)
    assert pairs[0].sample_size == 5


def test_correlation_skips_constant_columns():
    frame = pd.DataFrame({"spend": [1, 2, 3, 4], "flat": [7, 7, 7, 7]})
    assert analyze_correlations(frame, ["spend", "flat"]) == []


def test_correlation_pairs_are_sorted_by_absolute_strength():
    rng = np.random.default_rng(0)
    base = np.arange(50, dtype=float)
    frame = pd.DataFrame(
        {
            "a": base,
            "b": -base,
            "c": rng.normal(size=50),
        }
    )
    pairs = analyze_correlations(frame, ["a", "b", "c"])

    assert (pairs[0].column_a, pairs[0].column_b) == ("a", "b")
    assert pairs[0].pearson == pytest.approx(-1.0)
    assert abs(pairs[0].pearson) >= abs(pairs[-1].pearson)


def test_analysis_skips_identifier_columns():
    frame = pd.DataFrame(
        {
            "order_id": [f"ORD-{i}" for i in range(10)],
            "amount": np.arange(10, dtype=float),
            "city": ["Ankara", "Izmir"] * 5,
        }
    )
    profile = profile_dataset("x", "f.csv", frame)
    analysis = analyze_dataset(frame, profile)

    assert [summary.column for summary in analysis.numeric] == ["amount"]
    assert [summary.column for summary in analysis.categorical] == ["city"]


def test_boolean_columns_are_analysed_as_categorical():
    frame = pd.DataFrame({"is_returned": ["yes", "no", "yes", "yes"]})
    analysis = analyze_dataset(frame, profile_dataset("x", "f.csv", frame))

    assert [summary.column for summary in analysis.categorical] == ["is_returned"]
