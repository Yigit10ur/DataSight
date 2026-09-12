import pandas as pd

from app.analysis.models import (
    CategoricalSummary,
    CorrelationPair,
    GroupComparison,
    NumericSummary,
    Timeline,
)
from app.visualization.models import (
    BarData,
    BoxData,
    BoxGroup,
    ChartSpec,
    HeatmapData,
    HistogramData,
    LineData,
    ScatterData,
)

MAX_SCATTER_POINTS = 2000


def _slug(*parts: str) -> str:
    return "_".join(str(part).strip().lower().replace(" ", "-") for part in parts)


def histogram_chart(summary: NumericSummary) -> ChartSpec:
    return ChartSpec(
        id=_slug("histogram", summary.column),
        chart_type="histogram",
        title=f"Distribution of {summary.column}",
        columns=[summary.column],
        x_label=summary.column,
        y_label="rows",
        data=HistogramData(bin_edges=summary.histogram.bin_edges, counts=summary.histogram.counts),
    )


def bar_chart(summary: CategoricalSummary) -> ChartSpec:
    # How many categories are worth showing is decided once, when they are counted.
    shown = summary.top_categories
    other_count = summary.count - sum(category.count for category in shown)

    return ChartSpec(
        id=_slug("bar", summary.column),
        chart_type="bar",
        title=f"Most common values in {summary.column}",
        columns=[summary.column],
        x_label=summary.column,
        y_label="rows",
        data=BarData(
            categories=[category.value for category in shown],
            counts=[category.count for category in shown],
            other_count=max(other_count, 0),
        ),
    )


def scatter_chart(frame: pd.DataFrame, pair: CorrelationPair) -> ChartSpec:
    both = frame[[pair.column_a, pair.column_b]].apply(pd.to_numeric, errors="coerce").dropna()
    sampled_from = len(both)
    if sampled_from > MAX_SCATTER_POINTS:
        both = both.sample(MAX_SCATTER_POINTS, random_state=0).sort_index()

    title = f"{pair.column_b} vs {pair.column_a} (r = {pair.pearson:.2f}"
    title += f", ρ = {pair.spearman:.2f})" if pair.spearman is not None else ")"

    return ChartSpec(
        id=_slug("scatter", pair.column_a, pair.column_b),
        chart_type="scatter",
        title=title,
        columns=[pair.column_a, pair.column_b],
        x_label=pair.column_a,
        y_label=pair.column_b,
        data=ScatterData(
            x=[float(value) for value in both[pair.column_a]],
            y=[float(value) for value in both[pair.column_b]],
            sampled_from=sampled_from,
        ),
    )


def line_chart(timeline: Timeline) -> ChartSpec:
    return ChartSpec(
        id=_slug("line", timeline.time_column, timeline.value_column),
        chart_type="line",
        title=f"{timeline.value_column} over time",
        columns=[timeline.time_column, timeline.value_column],
        x_label=timeline.time_column,
        y_label=f"mean {timeline.value_column}",
        data=LineData(
            x=[point.period for point in timeline.points],
            y=[point.value for point in timeline.points],
            aggregation=timeline.aggregation,
        ),
    )


def box_chart(comparison: GroupComparison) -> ChartSpec:
    return ChartSpec(
        id=_slug("box", comparison.group_column, comparison.value_column),
        chart_type="box",
        title=f"{comparison.value_column} by {comparison.group_column}",
        columns=[comparison.group_column, comparison.value_column],
        x_label=comparison.group_column,
        y_label=comparison.value_column,
        data=BoxData(
            groups=[
                BoxGroup(
                    name=group.name,
                    count=group.count,
                    lower=group.lower_whisker,
                    q1=group.q1,
                    median=group.median,
                    q3=group.q3,
                    upper=group.upper_whisker,
                )
                for group in comparison.groups
            ]
        ),
    )


def heatmap_chart(columns: list[str], pairs: list[CorrelationPair]) -> ChartSpec:
    lookup = {(pair.column_a, pair.column_b): pair.pearson for pair in pairs}
    matrix: list[list[float | None]] = []

    for row in columns:
        line: list[float | None] = []
        for column in columns:
            if row == column:
                line.append(1.0)
            else:
                line.append(lookup.get((row, column), lookup.get((column, row))))
        matrix.append(line)

    return ChartSpec(
        id="heatmap_correlation",
        chart_type="heatmap",
        title="Correlation between numeric columns",
        columns=columns,
        x_label="",
        y_label="",
        data=HeatmapData(columns=columns, matrix=matrix),
    )
