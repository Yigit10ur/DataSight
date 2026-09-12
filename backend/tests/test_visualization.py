import numpy as np
import pandas as pd

from app.analysis import analyze_dataset
from app.analysis.categorical_analysis import TOP_CATEGORY_COUNT
from app.profiling import profile_dataset
from app.visualization import build_charts


def charts_for(frame: pd.DataFrame):
    profile = profile_dataset("x", "f.csv", frame)
    analysis = analyze_dataset(frame, profile)
    return build_charts(frame, profile, analysis).charts


def chart_types(frame: pd.DataFrame) -> list[str]:
    return [chart.chart_type for chart in charts_for(frame)]


def test_numeric_column_gets_a_histogram():
    frame = pd.DataFrame({"revenue": np.arange(100, dtype=float)})
    assert chart_types(frame) == ["histogram"]


def test_categorical_column_gets_a_bar_chart():
    frame = pd.DataFrame({"city": ["Ankara", "Izmir", "Ankara", "Bursa"] * 10})
    assert chart_types(frame) == ["bar"]


def test_correlated_numeric_pair_gets_a_scatter_first():
    spend = np.arange(50, dtype=float)
    frame = pd.DataFrame({"spend": spend, "revenue": spend * 2 + 3})
    types = chart_types(frame)

    assert types[0] == "scatter"
    assert types.count("histogram") == 2


def test_outliers_masking_pearson_still_produce_a_scatter():
    spend = np.arange(1, 201, dtype=float)
    revenue = spend * 3
    revenue[:4] = [30000, 31000, 29000, 32000]
    frame = pd.DataFrame({"spend": spend, "revenue": revenue})

    scatter = next(chart for chart in charts_for(frame) if chart.chart_type == "scatter")
    assert "ρ" in scatter.title


def test_uncorrelated_columns_get_no_scatter():
    rng = np.random.default_rng(0)
    frame = pd.DataFrame({"a": rng.normal(size=200), "b": rng.normal(size=200)})
    assert "scatter" not in chart_types(frame)


def test_datetime_and_numeric_get_a_line_chart():
    frame = pd.DataFrame(
        {
            "day": pd.date_range("2024-01-01", periods=90).astype(str),
            "revenue": np.linspace(100, 200, 90),
        }
    )
    charts = charts_for(frame)
    line = next(chart for chart in charts if chart.chart_type == "line")

    assert line.columns == ["day", "revenue"]
    assert len(line.data.x) == len(line.data.y)
    assert line.data.aggregation == "daily mean"


def test_long_time_span_is_aggregated_to_months():
    frame = pd.DataFrame(
        {
            "day": pd.date_range("2015-01-01", periods=3000).astype(str),
            "revenue": np.linspace(100, 200, 3000),
        }
    )
    line = next(chart for chart in charts_for(frame) if chart.chart_type == "line")

    assert line.data.aggregation == "monthly mean"
    assert len(line.data.x) < 200


def test_categorical_and_numeric_get_a_box_chart():
    frame = pd.DataFrame(
        {
            "segment": ["smb"] * 30 + ["enterprise"] * 30,
            "revenue": [*np.linspace(10, 40, 30), *np.linspace(100, 180, 30)],
        }
    )
    box = next(chart for chart in charts_for(frame) if chart.chart_type == "box")
    groups = {group.name: group for group in box.data.groups}

    assert set(groups) == {"smb", "enterprise"}
    assert groups["enterprise"].median > groups["smb"].median
    assert groups["smb"].q1 <= groups["smb"].median <= groups["smb"].q3


def test_groups_smaller_than_the_minimum_are_dropped():
    frame = pd.DataFrame(
        {
            "segment": ["smb"] * 30 + ["enterprise"] * 30 + ["tiny"] * 2,
            "revenue": np.linspace(10, 100, 62),
        }
    )
    box = next(chart for chart in charts_for(frame) if chart.chart_type == "box")

    assert {group.name for group in box.data.groups} == {"smb", "enterprise"}


def test_three_numeric_columns_get_a_correlation_heatmap():
    rng = np.random.default_rng(1)
    frame = pd.DataFrame({name: rng.normal(size=60) for name in ("a", "b", "c")})
    heatmap = next(chart for chart in charts_for(frame) if chart.chart_type == "heatmap")

    assert heatmap.data.columns == ["a", "b", "c"]
    assert [row[index] for index, row in enumerate(heatmap.data.matrix)] == [1.0, 1.0, 1.0]
    assert heatmap.data.matrix[0][1] == heatmap.data.matrix[1][0]


def test_high_cardinality_categorical_gets_no_bar_chart():
    frame = pd.DataFrame({"code": [f"code-{i}" for i in range(200)]})
    assert chart_types(frame) == []


def test_bar_chart_folds_the_tail_into_other():
    frame = pd.DataFrame({"city": [f"city-{i % 20}" for i in range(400)]})
    bar = next(chart for chart in charts_for(frame) if chart.chart_type == "bar")

    assert len(bar.data.categories) == TOP_CATEGORY_COUNT
    assert bar.data.other_count == 400 - sum(bar.data.counts)


def test_scatter_samples_large_datasets():
    spend = np.arange(5000, dtype=float)
    frame = pd.DataFrame({"spend": spend, "revenue": spend * 1.5})
    scatter = next(chart for chart in charts_for(frame) if chart.chart_type == "scatter")

    assert len(scatter.data.x) == 2000
    assert scatter.data.sampled_from == 5000


def test_chart_ids_are_unique():
    frame = pd.DataFrame(
        {
            "day": pd.date_range("2024-01-01", periods=60).astype(str),
            "segment": ["smb", "enterprise"] * 30,
            "spend": np.linspace(1, 60, 60),
            "revenue": np.linspace(2, 120, 60),
        }
    )
    ids = [chart.id for chart in charts_for(frame)]

    assert len(ids) == len(set(ids))
