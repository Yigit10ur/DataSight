import numpy as np
import pandas as pd
import pytest

from app.analysis import (
    analyze_categorical,
    analyze_correlations,
    analyze_dataset,
    analyze_groups,
    analyze_numeric,
    analyze_timeline,
    build_timelines,
    compare_groups,
)
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


def test_group_comparison_ranks_groups_and_measures_the_gap():
    frame = pd.DataFrame(
        {
            "segment": ["enterprise"] * 30 + ["smb"] * 30,
            "revenue": [*np.linspace(200, 280, 30), *np.linspace(80, 120, 30)],
        }
    )
    comparison = analyze_groups(frame, "segment", "revenue")

    assert comparison.highest_group == "enterprise"
    assert comparison.lowest_group == "smb"
    assert comparison.mean_ratio == pytest.approx(240 / 100, rel=0.01)
    assert comparison.sample_size == 60
    assert comparison.effect_size > 0.5
    assert comparison.p_value < 0.01


def test_group_comparison_drops_groups_that_are_too_small():
    frame = pd.DataFrame(
        {
            "segment": ["smb"] * 30 + ["enterprise"] * 30 + ["tiny"] * 2,
            "revenue": np.linspace(10, 100, 62),
        }
    )
    comparison = analyze_groups(frame, "segment", "revenue")

    assert {group.name for group in comparison.groups} == {"smb", "enterprise"}
    assert comparison.ignored_group_count == 1
    assert comparison.sample_size == 60


def test_group_comparison_needs_two_usable_groups():
    frame = pd.DataFrame({"segment": ["smb"] * 30, "revenue": np.linspace(10, 100, 30)})
    assert analyze_groups(frame, "segment", "revenue") is None


def test_identical_groups_have_a_negligible_effect_size():
    frame = pd.DataFrame(
        {
            "segment": ["a"] * 30 + ["b"] * 30,
            "revenue": [*np.linspace(10, 40, 30)] * 2,
        }
    )
    comparison = analyze_groups(frame, "segment", "revenue")

    assert comparison.effect_size < 0.05
    assert comparison.p_value > 0.5


def test_group_stats_carry_the_box_plot_shape():
    frame = pd.DataFrame(
        {
            "segment": ["a"] * 20 + ["b"] * 20,
            "revenue": [*range(1, 21), *range(101, 121)],
        }
    )
    group = analyze_groups(frame, "segment", "revenue").groups[-1]

    assert group.lower_whisker <= group.q1 <= group.median <= group.q3 <= group.upper_whisker
    assert group.minimum <= group.lower_whisker
    assert group.upper_whisker <= group.maximum


def test_negative_baseline_reports_a_difference_but_no_ratio():
    frame = pd.DataFrame(
        {
            "segment": ["profit"] * 10 + ["loss"] * 10,
            "margin": [*np.linspace(5, 15, 10), *np.linspace(-20, -10, 10)],
        }
    )
    comparison = analyze_groups(frame, "segment", "margin")

    assert comparison.mean_ratio is None
    assert comparison.median_difference > 0


def test_group_comparisons_are_ranked_by_effect_size():
    rng = np.random.default_rng(0)
    frame = pd.DataFrame(
        {
            "segment": ["a"] * 40 + ["b"] * 40,
            "separated": [*rng.normal(0, 1, 40), *rng.normal(20, 1, 40)],
            "mixed": rng.normal(0, 1, 80),
        }
    )
    comparisons = compare_groups(frame, ["segment"], ["separated", "mixed"])

    assert [comparison.value_column for comparison in comparisons] == ["separated", "mixed"]


def test_timeline_reports_a_rising_trend():
    frame = pd.DataFrame(
        {
            "day": pd.date_range("2024-01-01", periods=90).astype(str),
            "revenue": np.linspace(100, 200, 90),
        }
    )
    timeline = analyze_timeline(frame, "day", "revenue")

    assert timeline.trend == "rising"
    assert timeline.aggregation == "daily mean"
    assert timeline.change_ratio > 0.5
    assert timeline.monotonicity == pytest.approx(1.0)
    assert timeline.start == "2024-01-01"
    assert timeline.end == "2024-03-30"


def test_timeline_reports_a_falling_trend():
    frame = pd.DataFrame(
        {
            "day": pd.date_range("2024-01-01", periods=60).astype(str),
            "revenue": np.linspace(500, 100, 60),
        }
    )
    timeline = analyze_timeline(frame, "day", "revenue")

    assert timeline.trend == "falling"
    assert timeline.change_ratio < 0
    assert timeline.slope_per_period < 0


def test_noise_around_a_constant_level_is_flat():
    rng = np.random.default_rng(3)
    frame = pd.DataFrame(
        {
            "day": pd.date_range("2024-01-01", periods=120).astype(str),
            "revenue": 100 + rng.normal(0, 1, 120),
        }
    )
    assert analyze_timeline(frame, "day", "revenue").trend == "flat"


def test_one_jump_is_not_mistaken_for_a_steady_climb():
    values = np.concatenate([np.full(45, 100.0), np.full(45, 300.0)])
    frame = pd.DataFrame(
        {"day": pd.date_range("2024-01-01", periods=90).astype(str), "revenue": values}
    )
    timeline = analyze_timeline(frame, "day", "revenue")

    assert timeline.trend == "rising"
    assert timeline.largest_change.delta == pytest.approx(200.0)
    assert timeline.largest_change.period == "2024-02-15"
    assert timeline.largest_change.previous_period == "2024-02-14"


def test_long_span_is_aggregated_into_months():
    frame = pd.DataFrame(
        {
            "day": pd.date_range("2015-01-01", periods=3000).astype(str),
            "revenue": np.linspace(100, 200, 3000),
        }
    )
    timeline = analyze_timeline(frame, "day", "revenue")

    assert timeline.aggregation == "monthly mean"
    assert len(timeline.points) < 200
    assert timeline.sample_size == 3000


def test_repeating_yearly_pattern_is_detected_as_seasonality():
    months = pd.date_range("2020-01-01", periods=48, freq="MS")
    # A clean 12-month cycle, so the month explains most of the variation.
    values = [100 + 50 * np.sin(2 * np.pi * month.month / 12) for month in months]
    frame = pd.DataFrame({"month": months.astype(str), "revenue": values})
    timeline = analyze_timeline(frame, "month", "revenue")

    assert timeline.seasonality.cycle == "month of year"
    assert timeline.seasonality.strength > 0.9
    assert timeline.seasonality.strongest == "March"
    assert timeline.seasonality.weakest == "September"


def test_short_series_reports_no_seasonality():
    frame = pd.DataFrame(
        {
            "day": pd.date_range("2024-01-01", periods=5).astype(str),
            "revenue": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )
    assert analyze_timeline(frame, "day", "revenue").seasonality is None


def test_timeline_needs_more_than_two_observations():
    frame = pd.DataFrame({"day": ["2024-01-01", "2024-01-02"], "revenue": [1.0, 2.0]})
    assert analyze_timeline(frame, "day", "revenue") is None


def test_gaps_in_time_become_empty_points_not_observations():
    frame = pd.DataFrame(
        {
            "day": ["2024-01-01", "2024-01-02", "2024-01-10", "2024-01-11"],
            "revenue": [1.0, 2.0, 3.0, 4.0],
        }
    )
    timeline = analyze_timeline(frame, "day", "revenue")

    assert len(timeline.points) == 11
    assert timeline.points[2].value is None
    assert timeline.sample_size == 4


def test_timelines_are_ranked_by_how_much_they_moved():
    days = pd.date_range("2024-01-01", periods=60)
    frame = pd.DataFrame(
        {
            "day": days.astype(str),
            "steady": np.full(60, 50.0),
            "growing": np.linspace(10, 200, 60),
        }
    )
    timelines = build_timelines(frame, ["day"], ["steady", "growing"])

    assert [timeline.value_column for timeline in timelines] == ["growing", "steady"]


def test_only_the_first_datetime_column_becomes_a_timeline():
    days = pd.date_range("2024-01-01", periods=30)
    frame = pd.DataFrame(
        {
            "created_at": days.astype(str),
            "updated_at": days.astype(str),
            "revenue": np.linspace(1, 30, 30),
        }
    )
    timelines = build_timelines(frame, ["created_at", "updated_at"], ["revenue"])

    assert [timeline.time_column for timeline in timelines] == ["created_at"]


def test_dataset_analysis_includes_group_and_timeline_results():
    frame = pd.DataFrame(
        {
            "day": pd.date_range("2024-01-01", periods=60).astype(str),
            "segment": ["smb", "enterprise"] * 30,
            "revenue": np.linspace(100, 300, 60),
        }
    )
    analysis = analyze_dataset(frame, profile_dataset("x", "f.csv", frame))

    assert [comparison.value_column for comparison in analysis.groups] == ["revenue"]
    assert [timeline.value_column for timeline in analysis.timelines] == ["revenue"]


def test_high_cardinality_categorical_is_not_used_as_a_group_column():
    frame = pd.DataFrame(
        {
            "code": [f"code-{index % 25}" for index in range(250)],
            "amount": np.linspace(1, 250, 250),
        }
    )
    analysis = analyze_dataset(frame, profile_dataset("x", "f.csv", frame))

    assert analysis.groups == []


def test_monthly_rows_are_not_bucketed_into_empty_weeks():
    months = pd.date_range("2021-01-01", periods=36, freq="MS")
    frame = pd.DataFrame({"month": months.astype(str), "revenue": np.linspace(10, 100, 36)})
    timeline = analyze_timeline(frame, "month", "revenue")

    assert timeline.aggregation == "monthly mean"
    assert all(point.value is not None for point in timeline.points)


def test_infinite_values_are_treated_as_missing_not_as_measurements():
    summary = analyze_numeric(pd.Series([1.0, 2.0, 3.0, np.inf, -np.inf], name="value"))

    assert summary.count == 3
    assert summary.mean == 2
    assert summary.maximum == 3
    assert summary.histogram.counts


def test_a_single_infinite_cell_does_not_break_the_dataset_analysis():
    frame = pd.DataFrame(
        {
            "segment": ["a"] * 10 + ["b"] * 10,
            "ratio": [np.inf, *np.linspace(1, 19, 19)],
        }
    )
    analysis = analyze_dataset(frame, profile_dataset("x", "f.csv", frame))

    assert analysis.numeric[0].count == 19
    assert analysis.groups[0].sample_size == 19
