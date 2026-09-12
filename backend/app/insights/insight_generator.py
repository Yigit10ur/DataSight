from app.analysis.categorical_analysis import RARE_CATEGORY_RATIO
from app.analysis.models import (
    CategoricalSummary,
    CorrelationPair,
    DatasetAnalysis,
    GroupComparison,
    NumericSummary,
    Timeline,
)
from app.insights.formatting import multiple, number, percent
from app.insights.models import Insight
from app.quality.models import QualityReport
from app.visualization.models import ChartSpec

STRONG_CORRELATION = 0.5
# Conventional reading of epsilon-squared: 0.01 small, 0.06 moderate, 0.14 large.
MODERATE_EFFECT = 0.06
LARGE_EFFECT = 0.14
SIGNIFICANT_P = 0.05
NOTABLE_TREND_RATIO = 0.10
DOUBLED = 1.0
NOTABLE_SEASONAL_STRENGTH = 0.30
NOTABLE_JUMP_RATIO = 0.50
# A normal distribution already puts about 0.7% of its values outside the Tukey
# fences, and sampling alone pushes that past 2% often enough. Only a share several
# times the natural rate says the column really has a heavy tail.
NOTABLE_OUTLIER_RATIO = 0.05
SEVERE_OUTLIER_RATIO = 0.20
NOTABLE_SKEW = 1.0
EXTREME_SKEW = 3.0
DOMINANT_CATEGORY_RATIO = 0.70
MIN_RARE_CATEGORIES = 3
NOTABLE_MISSING_RATIO = 0.10
UNUSABLE_MISSING_RATIO = 0.50

CAUSATION_CAVEAT = (
    "A relationship between two columns is not evidence that one causes the other."
)
SPLIT_CATEGORY_CAVEAT = (
    "This column has spelling or spacing variants, so one real group may be split "
    "across several of the groups compared here."
)

CONSISTENCY_ISSUES = {"suspicious_categories", "inconsistent_formatting"}


def _capped(value: float, ceiling: float) -> float:
    return min(abs(value) / ceiling, 1.0) if ceiling else 0.0


def _correlation_insight(pair: CorrelationPair, charts: dict) -> Insight | None:
    coefficient = max(abs(pair.pearson), abs(pair.spearman or 0.0))
    if coefficient < STRONG_CORRELATION:
        return None

    # The sign of the coefficient that actually carried the pair.
    leading = pair.pearson if abs(pair.pearson) >= abs(pair.spearman or 0.0) else pair.spearman
    direction = "move together" if leading > 0 else "move in opposite directions"

    coefficients = f"r = {pair.pearson:.2f}"
    if pair.spearman is not None:
        coefficients += f", rho = {pair.spearman:.2f}"

    return Insight(
        id=f"correlation__{pair.column_a}__{pair.column_b}",
        insight_type="correlation",
        columns=[pair.column_a, pair.column_b],
        message=(
            f"{pair.column_a} and {pair.column_b} {direction} "
            f"({coefficients}, {pair.sample_size} rows)."
        ),
        metrics={
            "pearson": pair.pearson,
            "spearman": pair.spearman,
            "sample_size": pair.sample_size,
        },
        strength=coefficient,
        sample_size=pair.sample_size,
        caveats=[CAUSATION_CAVEAT],
        chart_id=charts.get(("scatter", (pair.column_a, pair.column_b))),
    )


def _group_insight(
    comparison: GroupComparison, split_columns: set[str], charts: dict
) -> Insight | None:
    effect = comparison.effect_size
    if effect is None or effect < MODERATE_EFFECT:
        return None
    if comparison.p_value is not None and comparison.p_value > SIGNIFICANT_P:
        return None

    highest = next(group for group in comparison.groups if group.name == comparison.highest_group)
    lowest = next(group for group in comparison.groups if group.name == comparison.lowest_group)

    if comparison.mean_ratio is not None:
        gap = f"{multiple(comparison.mean_ratio)} the average {comparison.value_column} of"
    else:
        gap = f"a median {comparison.value_column} {number(comparison.median_difference)} above"

    return Insight(
        id=f"group_difference__{comparison.group_column}__{comparison.value_column}",
        insight_type="group_difference",
        columns=[comparison.group_column, comparison.value_column],
        message=(
            f"{comparison.group_column} = {highest.name} has {gap} "
            f"{lowest.name} ({number(highest.mean)} against {number(lowest.mean)} "
            f"across {comparison.sample_size} rows)."
        ),
        metrics={
            "highest_group": highest.name,
            "lowest_group": lowest.name,
            "highest_mean": highest.mean,
            "lowest_mean": lowest.mean,
            "mean_ratio": comparison.mean_ratio,
            "median_difference": comparison.median_difference,
            "effect_size": effect,
            "p_value": comparison.p_value,
            "sample_size": comparison.sample_size,
        },
        strength=_capped(effect, LARGE_EFFECT),
        sample_size=comparison.sample_size,
        caveats=[SPLIT_CATEGORY_CAVEAT] if comparison.group_column in split_columns else [],
        chart_id=charts.get(("box", (comparison.group_column, comparison.value_column))),
    )


def _trend_insight(timeline: Timeline, charts: dict) -> Insight | None:
    change = timeline.change_ratio
    if change is None or abs(change) < NOTABLE_TREND_RATIO:
        return None

    direction = "rose" if change > 0 else "fell"
    chart_id = charts.get(("line", (timeline.time_column, timeline.value_column)))

    return Insight(
        id=f"trend__{timeline.time_column}__{timeline.value_column}",
        insight_type="trend",
        columns=[timeline.time_column, timeline.value_column],
        message=(
            f"{timeline.value_column} {direction} {percent(abs(change))} between the start and "
            f"the end of the period covered by {timeline.time_column} "
            f"({number(timeline.first_window_mean)} to {number(timeline.last_window_mean)}, "
            f"{timeline.aggregation})."
        ),
        metrics={
            "trend": timeline.trend,
            "change_ratio": change,
            "first_window_mean": timeline.first_window_mean,
            "last_window_mean": timeline.last_window_mean,
            "window_periods": timeline.window_periods,
            "monotonicity": timeline.monotonicity,
            "start": timeline.start,
            "end": timeline.end,
            "aggregation": timeline.aggregation,
        },
        strength=_capped(change, DOUBLED),
        sample_size=timeline.sample_size,
        caveats=[],
        chart_id=chart_id,
    )


def _seasonality_insight(timeline: Timeline, charts: dict) -> Insight | None:
    season = timeline.seasonality
    if season is None or season.strength < NOTABLE_SEASONAL_STRENGTH:
        return None

    return Insight(
        id=f"seasonality__{timeline.time_column}__{timeline.value_column}",
        insight_type="seasonality",
        columns=[timeline.time_column, timeline.value_column],
        message=(
            f"{timeline.value_column} peaks at {season.strongest} and bottoms out at "
            f"{season.weakest}; the {season.cycle} accounts for {percent(season.strength)} "
            f"of its variation."
        ),
        metrics={
            "cycle": season.cycle,
            "strongest": season.strongest,
            "weakest": season.weakest,
            "seasonal_strength": season.strength,
        },
        strength=season.strength,
        sample_size=timeline.sample_size,
        caveats=[],
        chart_id=charts.get(("line", (timeline.time_column, timeline.value_column))),
    )


def _sudden_change_insight(timeline: Timeline, charts: dict) -> Insight | None:
    change = timeline.largest_change
    if change is None or change.ratio is None or abs(change.ratio) < NOTABLE_JUMP_RATIO:
        return None

    direction = "jumped" if change.delta > 0 else "dropped"

    return Insight(
        id=f"sudden_change__{timeline.time_column}__{timeline.value_column}",
        insight_type="sudden_change",
        columns=[timeline.time_column, timeline.value_column],
        message=(
            f"{timeline.value_column} {direction} {percent(abs(change.ratio))} at "
            f"{change.period} compared with {change.previous_period} "
            f"(a change of {number(change.delta)}, {timeline.aggregation})."
        ),
        metrics={
            "period": change.period,
            "previous_period": change.previous_period,
            "delta": change.delta,
            "change_ratio": change.ratio,
            "aggregation": timeline.aggregation,
        },
        strength=_capped(change.ratio, DOUBLED),
        sample_size=timeline.sample_size,
        caveats=[],
        chart_id=charts.get(("line", (timeline.time_column, timeline.value_column))),
    )


def _outlier_insight(summary: NumericSummary, charts: dict) -> Insight | None:
    if summary.outlier_ratio < NOTABLE_OUTLIER_RATIO or summary.outlier_count == 0:
        return None

    return Insight(
        id=f"outliers__{summary.column}",
        insight_type="outliers",
        columns=[summary.column],
        message=(
            f"{summary.outlier_count} of {summary.count} values in {summary.column} "
            f"({percent(summary.outlier_ratio)}) sit far outside the middle half of the "
            f"column, which stretches from {number(summary.q1)} to {number(summary.q3)}."
        ),
        metrics={
            "outlier_count": summary.outlier_count,
            "outlier_ratio": summary.outlier_ratio,
            "count": summary.count,
            "q1": summary.q1,
            "q3": summary.q3,
            "minimum": summary.minimum,
            "maximum": summary.maximum,
        },
        strength=_capped(summary.outlier_ratio, SEVERE_OUTLIER_RATIO),
        sample_size=summary.count,
        caveats=[],
        chart_id=charts.get(("histogram", (summary.column,))),
    )


def _skew_insight(summary: NumericSummary, charts: dict) -> Insight | None:
    skew = summary.skewness
    if skew is None or abs(skew) < NOTABLE_SKEW:
        return None
    if summary.mean is None or summary.median is None:
        return None

    side = "a long tail of high values" if skew > 0 else "a long tail of low values"
    relation = "above" if summary.mean > summary.median else "below"

    return Insight(
        id=f"skewed_distribution__{summary.column}",
        insight_type="skewed_distribution",
        columns=[summary.column],
        message=(
            f"{summary.column} has {side} (skewness {skew:.2f}), so its average of "
            f"{number(summary.mean)} sits {relation} the typical value of "
            f"{number(summary.median)}."
        ),
        metrics={
            "skewness": skew,
            "mean": summary.mean,
            "median": summary.median,
            "count": summary.count,
        },
        strength=_capped(skew, EXTREME_SKEW),
        sample_size=summary.count,
        caveats=[],
        chart_id=charts.get(("histogram", (summary.column,))),
    )


def _dominant_category_insight(summary: CategoricalSummary, charts: dict) -> Insight | None:
    if not summary.top_categories or summary.unique_count < 2:
        return None
    top = summary.top_categories[0]
    if top.ratio < DOMINANT_CATEGORY_RATIO:
        return None

    return Insight(
        id=f"dominant_category__{summary.column}",
        insight_type="dominant_category",
        columns=[summary.column],
        message=(
            f"{percent(top.ratio)} of rows share one value of {summary.column}: "
            f"{top.value} ({top.count} of {summary.count} rows, "
            f"{summary.unique_count} distinct values in total)."
        ),
        metrics={
            "value": top.value,
            "count": top.count,
            "ratio": top.ratio,
            "total": summary.count,
            "unique_count": summary.unique_count,
        },
        strength=top.ratio,
        sample_size=summary.count,
        caveats=[],
        chart_id=charts.get(("bar", (summary.column,))),
    )


def _rare_categories_insight(summary: CategoricalSummary, charts: dict) -> Insight | None:
    if summary.rare_category_count < MIN_RARE_CATEGORIES:
        return None

    return Insight(
        id=f"rare_categories__{summary.column}",
        insight_type="rare_categories",
        columns=[summary.column],
        message=(
            f"{summary.rare_category_count} of the {summary.unique_count} values in "
            f"{summary.column} each appear in under {percent(RARE_CATEGORY_RATIO)} of rows, "
            f"too rarely to compare against the rest."
        ),
        metrics={
            "rare_category_count": summary.rare_category_count,
            "unique_count": summary.unique_count,
            "count": summary.count,
            "rare_threshold": RARE_CATEGORY_RATIO,
        },
        strength=_capped(summary.rare_category_count / summary.unique_count, 1.0),
        sample_size=summary.count,
        caveats=[],
        chart_id=charts.get(("bar", (summary.column,))),
    )


def _missing_insights(quality: QualityReport) -> list[Insight]:
    insights: list[Insight] = []

    for issue in quality.issues:
        if issue.issue_type != "missing_values":
            continue
        ratio = issue.metrics["missing_ratio"]
        if ratio < NOTABLE_MISSING_RATIO:
            continue

        column = issue.columns[0]
        insights.append(
            Insight(
                id=f"missing_data__{column}",
                insight_type="missing_data",
                columns=[column],
                message=(
                    f"{column} has no value in {percent(ratio)} of rows "
                    f"({issue.metrics['missing_count']} rows), so any result that uses it "
                    f"rests on the remainder."
                ),
                metrics=issue.metrics,
                strength=_capped(ratio, UNUSABLE_MISSING_RATIO),
                sample_size=issue.metrics["missing_count"],
                caveats=[],
                chart_id=None,
            )
        )

    return insights


def _chart_lookup(charts: list[ChartSpec]) -> dict[tuple[str, tuple[str, ...]], str]:
    """Index the selected charts so a finding can point at the one that shows it."""
    return {(chart.chart_type, tuple(chart.columns)): chart.id for chart in charts}


def generate_insights(
    analysis: DatasetAnalysis, quality: QualityReport, charts: list[ChartSpec]
) -> list[Insight]:
    """Turn computed results into structured findings.

    Nothing is measured here. Every number already exists in the analysis or the
    quality report; this layer only decides which of them are worth saying out
    loud and writes the sentence that says it.
    """
    lookup = _chart_lookup(charts)
    split_columns = {
        column
        for issue in quality.issues
        if issue.issue_type in CONSISTENCY_ISSUES
        for column in issue.columns
    }

    candidates: list[Insight | None] = []
    for pair in analysis.correlations:
        candidates.append(_correlation_insight(pair, lookup))
    for comparison in analysis.groups:
        candidates.append(_group_insight(comparison, split_columns, lookup))
    for timeline in analysis.timelines:
        candidates.append(_trend_insight(timeline, lookup))
        candidates.append(_seasonality_insight(timeline, lookup))
        candidates.append(_sudden_change_insight(timeline, lookup))
    for summary in analysis.numeric:
        candidates.append(_outlier_insight(summary, lookup))
        candidates.append(_skew_insight(summary, lookup))
    for summary in analysis.categorical:
        candidates.append(_dominant_category_insight(summary, lookup))
        candidates.append(_rare_categories_insight(summary, lookup))

    found = [insight for insight in candidates if insight is not None]
    return [*found, *_missing_insights(quality)]
