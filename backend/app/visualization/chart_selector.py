import pandas as pd

from app.analysis.models import DatasetAnalysis
from app.visualization.chart_generator import (
    bar_chart,
    box_chart,
    heatmap_chart,
    histogram_chart,
    line_chart,
    scatter_chart,
)
from app.visualization.models import ChartSpec

MIN_SCATTER_CORRELATION = 0.3
MIN_HEATMAP_COLUMNS = 3
MAX_BAR_CHART_UNIQUE = 30

MAX_SCATTERS = 3
MAX_LINES = 2
MAX_BOXES = 2
MAX_HISTOGRAMS = 6
MAX_BARS = 6


def select_charts(frame: pd.DataFrame, analysis: DatasetAnalysis) -> list[ChartSpec]:
    """Choose the charts worth showing, strongest signal first.

    Ordering is the product decision here: a relationship or a trend says more
    about a dataset than yet another single-column distribution, so those lead.
    Which trend and which group comparison is worth the space was already decided
    in the analysis layer, which ranked them by how much they actually move.
    """
    numeric_columns = [summary.column for summary in analysis.numeric]
    charts: list[ChartSpec] = []

    # A few extreme values can flatten Pearson on a pair whose ranks move together,
    # so a strong result from either coefficient is reason enough to plot the pair.
    strong_pairs = [
        pair
        for pair in analysis.correlations
        if max(abs(pair.pearson), abs(pair.spearman or 0)) >= MIN_SCATTER_CORRELATION
    ]
    charts.extend(scatter_chart(frame, pair) for pair in strong_pairs[:MAX_SCATTERS])
    charts.extend(line_chart(timeline) for timeline in analysis.timelines[:MAX_LINES])
    charts.extend(box_chart(comparison) for comparison in analysis.groups[:MAX_BOXES])

    if len(numeric_columns) >= MIN_HEATMAP_COLUMNS:
        charts.append(heatmap_chart(numeric_columns, analysis.correlations))

    charts.extend(histogram_chart(summary) for summary in analysis.numeric[:MAX_HISTOGRAMS])
    charts.extend(
        bar_chart(summary)
        for summary in analysis.categorical[:MAX_BARS]
        if 2 <= summary.unique_count <= MAX_BAR_CHART_UNIQUE
    )

    return charts
