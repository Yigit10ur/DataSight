import re

import numpy as np
import pandas as pd

from app.analysis import analyze_dataset
from app.insights import build_insights, generate_insights
from app.insights.formatting import multiple, number, percent
from app.profiling import profile_dataset
from app.quality import check_dataset_quality
from app.visualization import build_charts


def insights_for(frame: pd.DataFrame):
    """Everything the generator finds, before the ranker decides what survives."""
    profile = profile_dataset("x", "f.csv", frame)
    analysis = analyze_dataset(frame, profile)
    charts = build_charts(frame, profile, analysis)
    quality = check_dataset_quality(frame, profile)
    return generate_insights(profile, analysis, quality, charts.charts)


def ranked_for(frame: pd.DataFrame):
    profile = profile_dataset("x", "f.csv", frame)
    analysis = analyze_dataset(frame, profile)
    charts = build_charts(frame, profile, analysis)
    quality = check_dataset_quality(frame, profile)
    return build_insights(profile, analysis, quality, charts.charts).insights


def types_for(frame: pd.DataFrame) -> list[str]:
    return [insight.insight_type for insight in insights_for(frame)]


def insight_of(frame: pd.DataFrame, insight_type: str):
    return next(
        insight for insight in insights_for(frame) if insight.insight_type == insight_type
    )


def test_a_strong_correlation_becomes_an_insight():
    spend = np.linspace(1, 200, 200)
    frame = pd.DataFrame({"spend": spend, "revenue": spend * 3 + 5})
    insight = insight_of(frame, "correlation")

    assert insight.columns == ["spend", "revenue"]
    assert "move together" in insight.message
    assert insight.metrics["pearson"] > 0.99
    assert insight.strength > 0.99


def test_a_negative_relationship_is_described_as_opposite():
    base = np.linspace(1, 200, 200)
    frame = pd.DataFrame({"price": base, "units": 500 - base * 2})
    insight = insight_of(frame, "correlation")

    assert "move in opposite directions" in insight.message


def test_a_weak_correlation_produces_nothing():
    rng = np.random.default_rng(0)
    frame = pd.DataFrame({"a": rng.normal(size=300), "b": rng.normal(size=300)})
    assert "correlation" not in types_for(frame)


def test_every_correlation_insight_warns_against_reading_it_as_cause():
    spend = np.linspace(1, 200, 200)
    frame = pd.DataFrame({"spend": spend, "revenue": spend * 3})
    insight = insight_of(frame, "correlation")

    assert any("causes" in caveat for caveat in insight.caveats)


def test_a_large_group_difference_becomes_an_insight():
    rng = np.random.default_rng(1)
    frame = pd.DataFrame(
        {
            "segment": ["enterprise"] * 60 + ["smb"] * 60,
            "revenue": [*rng.normal(240, 10, 60), *rng.normal(100, 10, 60)],
        }
    )
    insight = insight_of(frame, "group_difference")

    assert insight.metrics["highest_group"] == "enterprise"
    assert insight.metrics["mean_ratio"] > 2
    assert "2.4x" in insight.message
    assert insight.strength == 1.0


def test_a_real_but_tiny_group_difference_is_not_worth_saying():
    rng = np.random.default_rng(2)
    # Significant at n = 4000 and meaningless at any n: the groups overlap almost
    # completely, which is what the effect size measures and the p-value does not.
    frame = pd.DataFrame(
        {
            "plan": ["monthly"] * 2000 + ["annual"] * 2000,
            "score": [*rng.normal(50.0, 10, 2000), *rng.normal(50.7, 10, 2000)],
        }
    )
    comparison = analyze_dataset(
        frame, profile_dataset("x", "f.csv", frame)
    ).groups[0]

    assert comparison.p_value < 0.05
    assert comparison.effect_size < 0.06
    assert "group_difference" not in types_for(frame)


def test_a_group_split_by_spelling_carries_a_caveat():
    rng = np.random.default_rng(3)
    frame = pd.DataFrame(
        {
            "city": ["Istanbul"] * 40 + ["istanbul"] * 40 + ["Ankara"] * 40,
            "revenue": [*rng.normal(300, 10, 80), *rng.normal(100, 10, 40)],
        }
    )
    insight = insight_of(frame, "group_difference")

    assert any("split" in caveat for caveat in insight.caveats)


def test_a_clean_group_column_carries_no_caveat():
    rng = np.random.default_rng(4)
    frame = pd.DataFrame(
        {
            "city": ["Istanbul"] * 60 + ["Ankara"] * 60,
            "revenue": [*rng.normal(300, 10, 60), *rng.normal(100, 10, 60)],
        }
    )
    assert insight_of(frame, "group_difference").caveats == []


def test_a_rising_series_becomes_a_trend_insight():
    frame = pd.DataFrame(
        {
            "day": pd.date_range("2024-01-01", periods=120).astype(str),
            "revenue": np.linspace(100, 300, 120),
        }
    )
    insight = insight_of(frame, "trend")

    assert "rose" in insight.message
    assert insight.metrics["change_ratio"] > 0.5


def test_a_flat_series_produces_no_trend_insight():
    rng = np.random.default_rng(5)
    frame = pd.DataFrame(
        {
            "day": pd.date_range("2024-01-01", periods=120).astype(str),
            "revenue": 100 + rng.normal(0, 1, 120),
        }
    )
    assert "trend" not in types_for(frame)


def test_a_yearly_cycle_becomes_a_seasonality_insight():
    months = pd.date_range("2020-01-01", periods=48, freq="MS")
    frame = pd.DataFrame(
        {
            "month": months.astype(str),
            "revenue": [100 + 50 * np.sin(2 * np.pi * month.month / 12) for month in months],
        }
    )
    insight = insight_of(frame, "seasonality")

    assert insight.metrics["strongest"] == "March"
    assert "month of year" in insight.message


def test_a_step_change_becomes_a_sudden_change_insight():
    values = np.concatenate([np.full(60, 100.0), np.full(60, 300.0)])
    frame = pd.DataFrame(
        {"day": pd.date_range("2024-01-01", periods=120).astype(str), "revenue": values}
    )
    insight = insight_of(frame, "sudden_change")

    assert "jumped" in insight.message
    assert insight.metrics["period"] == "2024-03-01"
    assert insight.metrics["delta"] == 200


def test_extreme_values_become_an_outlier_insight():
    frame = pd.DataFrame({"revenue": [*np.linspace(100, 200, 190), *np.full(10, 50000.0)]})
    insight = insight_of(frame, "outliers")

    assert insight.metrics["outlier_count"] == 10
    assert "5.0%" in insight.message


def test_a_long_tail_becomes_a_skew_insight():
    frame = pd.DataFrame({"revenue": [*np.full(180, 100.0), *np.linspace(1000, 9000, 20)]})
    insight = insight_of(frame, "skewed_distribution")

    assert "long tail of high values" in insight.message
    assert insight.metrics["mean"] > insight.metrics["median"]


def test_one_value_covering_most_rows_becomes_a_dominant_category_insight():
    frame = pd.DataFrame({"city": ["Ankara"] * 85 + ["Izmir"] * 10 + ["Bursa"] * 5})
    insight = insight_of(frame, "dominant_category")

    assert insight.metrics["value"] == "Ankara"
    assert "85.0%" in insight.message


def test_a_constant_column_is_not_a_dominant_category():
    frame = pd.DataFrame({"country": ["TR"] * 50, "revenue": np.linspace(1, 50, 50)})
    assert "dominant_category" not in types_for(frame)


def test_a_long_tail_of_categories_becomes_a_rare_categories_insight():
    frame = pd.DataFrame(
        {"city": ["Ankara"] * 400 + [f"village-{index}" for index in range(20)]}
    )
    insight = insight_of(frame, "rare_categories")

    assert insight.metrics["rare_category_count"] == 20


def test_a_mostly_empty_column_becomes_a_missing_data_insight():
    frame = pd.DataFrame(
        {
            "city": ["Ankara", "Izmir"] * 50,
            "age": [*np.linspace(20, 60, 60), *[None] * 40],
        }
    )
    insight = insight_of(frame, "missing_data")

    assert insight.metrics["missing_count"] == 40
    assert "40.0%" in insight.message


def test_a_barely_incomplete_column_is_not_worth_saying():
    frame = pd.DataFrame(
        {
            "city": ["Ankara", "Izmir"] * 50,
            "age": [*np.linspace(20, 60, 97), *[None] * 3],
        }
    )
    assert "missing_data" not in types_for(frame)


def test_structureless_data_produces_no_insights():
    rng = np.random.default_rng(6)
    frame = pd.DataFrame(
        {
            "city": rng.choice(["Ankara", "Izmir", "Bursa"], 300),
            "revenue": rng.normal(1000, 100, 300),
            "age": rng.normal(40, 8, 300),
        }
    )
    assert insights_for(frame) == []


def test_each_insight_points_at_a_chart_that_exists():
    frame = pd.DataFrame(
        {
            "day": pd.date_range("2024-01-01", periods=120).astype(str),
            "segment": ["enterprise"] * 60 + ["smb"] * 60,
            "spend": np.linspace(1, 120, 120),
            "revenue": np.linspace(100, 400, 120),
        }
    )
    profile = profile_dataset("x", "f.csv", frame)
    analysis = analyze_dataset(frame, profile)
    charts = build_charts(frame, profile, analysis)
    quality = check_dataset_quality(frame, profile)
    insights = build_insights(profile, analysis, quality, charts.charts)

    chart_ids = {chart.id for chart in charts.charts}
    linked = [insight for insight in insights.insights if insight.chart_id is not None]

    assert linked
    assert all(insight.chart_id in chart_ids for insight in linked)


INLINE_FORMATS = ("{:.2f}",)


def untraceable_numbers(insight) -> set[str]:
    """Numbers printed in the message that no metric can account for.

    The renderings are produced by the same helpers the generator writes with, so
    a message that starts formatting a number some other way fails here until the
    format is added deliberately.
    """
    text = insight.message
    for value in insight.metrics.values():
        if isinstance(value, str):
            text = text.replace(value, " ")
    for column in insight.columns:
        text = text.replace(column, " ")

    renderings: set[str] = set()
    for value in insight.metrics.values():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        renderings.update({str(value), number(value), percent(value), multiple(value)})
        renderings.update(template.format(value) for template in INLINE_FORMATS)

    printed = set(re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?[%x]?", text))
    return printed - renderings


def test_no_message_contains_a_number_that_is_not_in_its_metrics():
    frames = [
        pd.DataFrame(
            {
                "day": pd.date_range("2024-01-01", periods=120).astype(str),
                "segment": ["enterprise"] * 60 + ["smb"] * 60,
                "spend": np.linspace(1, 120, 120),
                "revenue": np.concatenate([np.full(59, 100.0), np.full(61, 400.0)]),
                "age": [*np.linspace(20, 60, 80), *[None] * 40],
            }
        ),
        pd.DataFrame({"revenue": [*np.full(180, 100.0), *np.linspace(1000, 9000, 20)]}),
        pd.DataFrame({"city": ["Ankara"] * 400 + [f"village-{index}" for index in range(20)]}),
        pd.DataFrame(
            {
                "month": pd.date_range("2020-01-01", periods=48, freq="MS").astype(str),
                "revenue": [
                    100 + 50 * np.sin(2 * np.pi * month.month / 12)
                    for month in pd.date_range("2020-01-01", periods=48, freq="MS")
                ],
            }
        ),
    ]

    checked = 0
    for frame in frames:
        for insight in insights_for(frame):
            assert untraceable_numbers(insight) == set(), insight.message
            checked += 1

    assert checked >= 8
