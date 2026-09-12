import math

import pandas as pd

from app.analysis.models import CategoricalSummary, CorrelationPair, NumericSummary
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
MAX_LINE_POINTS = 400
MIN_BOX_GROUP_SIZE = 5


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


def line_chart(frame: pd.DataFrame, time_column: str, value_column: str) -> ChartSpec:
    timestamps = pd.to_datetime(frame[time_column], errors="coerce", format="mixed")
    values = pd.to_numeric(frame[value_column], errors="coerce")
    series = pd.DataFrame({"t": timestamps, "v": values}).dropna(subset=["t"])

    span_days = (series["t"].max() - series["t"].min()).days if len(series) > 1 else 0
    rule = "D" if span_days <= MAX_LINE_POINTS else ("W" if span_days <= MAX_LINE_POINTS * 7 else "MS")
    grouped = series.set_index("t").resample(rule)["v"].mean()

    return ChartSpec(
        id=_slug("line", time_column, value_column),
        chart_type="line",
        title=f"{value_column} over time",
        columns=[time_column, value_column],
        x_label=time_column,
        y_label=f"mean {value_column}",
        data=LineData(
            x=[timestamp.date().isoformat() for timestamp in grouped.index],
            y=[None if math.isnan(value) else float(value) for value in grouped],
            aggregation={"D": "daily mean", "W": "weekly mean", "MS": "monthly mean"}[rule],
        ),
    )


def box_chart(frame: pd.DataFrame, group_column: str, value_column: str) -> ChartSpec | None:
    values = pd.to_numeric(frame[value_column], errors="coerce")
    groups: list[BoxGroup] = []

    for name, group in values.groupby(frame[group_column].astype(str)):
        group = group.dropna()
        if len(group) < MIN_BOX_GROUP_SIZE:
            continue
        q1, median, q3 = group.quantile([0.25, 0.5, 0.75])
        iqr = q3 - q1
        within = group[(group >= q1 - 1.5 * iqr) & (group <= q3 + 1.5 * iqr)]
        groups.append(
            BoxGroup(
                name=str(name),
                count=len(group),
                lower=float(within.min() if not within.empty else group.min()),
                q1=float(q1),
                median=float(median),
                q3=float(q3),
                upper=float(within.max() if not within.empty else group.max()),
            )
        )

    if len(groups) < 2:
        return None

    return ChartSpec(
        id=_slug("box", group_column, value_column),
        chart_type="box",
        title=f"{value_column} by {group_column}",
        columns=[group_column, value_column],
        x_label=group_column,
        y_label=value_column,
        data=BoxData(groups=groups),
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
