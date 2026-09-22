import math
from typing import Any

import pandas as pd

from app.analysis import analyze_categorical, analyze_correlations, analyze_groups, analyze_numeric
from app.analysis.datetime_analysis import analyze_timeline
from app.insights.models import Insight
from app.profiling.models import DatasetProfile
from app.recipes import (
    Aggregate,
    Aggregation,
    DatetimePartExpression,
    DeriveColumn,
    FilterRows,
    LimitRows,
    Recipe,
    SortRows,
    planned_columns,
    run_recipe,
)
from app.visualization.chart_generator import (
    bar_chart,
    box_chart,
    histogram_chart,
    line_chart,
    scatter_chart,
)
from app.visualization.models import BarData, ChartSpec

from .models import (
    AggregatePlan,
    AnalysisPlan,
    ComparePlan,
    ComputedQuery,
    CountPlan,
    DescribePlan,
    DistributionPlan,
    RankPlan,
    RelatePlan,
    TrendPlan,
)
from .validator import PlanRefused, validate_plan

MAX_RESULT_ROWS = 20
MIN_TYPICAL_GROUP_SIZE = 3
DATETIME_PART = {
    "day": "date",
    "week": "year_week",
    "month": "year_month",
    "quarter": "year_quarter",
    "year": "year",
}


def _finite(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return _finite(value.item())
    return value


def _filters(plan: AnalysisPlan):
    return [FilterRows(clauses=plan.filters)] if plan.filters else []


def _filtered(frame: pd.DataFrame, profile: DatasetProfile, plan: AnalysisPlan) -> pd.DataFrame:
    if not plan.filters:
        return frame
    run = run_recipe(
        frame,
        planned_columns(profile.column_schemas),
        Recipe(steps=_filters(plan)),
    )
    if run.refusal is not None:
        raise PlanRefused(run.refusal.reason)
    return run.frame


def _metric_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for index, row in enumerate(rows):
        for key, value in row.items():
            metrics[f"row_{index}_{key}"] = value
    return metrics


def _insight(
    operation: str,
    columns: list[str],
    message: str,
    metrics: dict[str, Any],
    sample_size: int,
    chart: ChartSpec | None = None,
    caveats: list[str] | None = None,
) -> Insight:
    kinds = {
        "aggregate": "aggregate",
        "rank": "ranking",
        "count": "count",
        "describe": "description",
        "compare": "group_difference",
        "relate": "correlation",
        "trend": "trend",
        "distribution": "skewed_distribution",
    }
    return Insight(
        id=f"question-{operation}",
        insight_type=kinds[operation],
        columns=columns,
        message=message,
        metrics=metrics,
        strength=1.0,
        confidence=min(sample_size / 30, 1.0) if sample_size else 0.0,
        sample_size=sample_size,
        caveats=caveats or [],
        chart_id=chart.id if chart else None,
        importance=1.0,
    )


def _unique_name(profile: DatasetProfile, base: str) -> str:
    names = {column.name for column in profile.column_schemas}
    name = base
    while name in names:
        name = f"_{name}"
    return name


def _aggregate(
    frame: pd.DataFrame, profile: DatasetProfile, plan: AggregatePlan | RankPlan
) -> ComputedQuery:
    value_name = _unique_name(profile, "__query_value")
    group_count_name = _unique_name(profile, "__query_group_rows")
    steps = list(_filters(plan))
    groups = list(plan.group_by)
    output_groups = list(groups)

    if plan.time_grain is not None:
        date_group = next(
            name for name in groups
            if next(c for c in profile.column_schemas if c.name == name).inferred_type == "datetime"
        )
        part_name = _unique_name(profile, f"__query_{date_group}_{plan.time_grain}")
        steps.append(
            DeriveColumn(
                name=part_name,
                expression=DatetimePartExpression(
                    column=date_group, part=DATETIME_PART[plan.time_grain]
                ),
            )
        )
        groups[groups.index(date_group)] = part_name
        output_groups[output_groups.index(date_group)] = f"{date_group} ({plan.time_grain})"

    steps.append(
        Aggregate(
            group_by=groups,
            aggregations=[
                Aggregation(function=plan.function, column=plan.measure, name=value_name),
                Aggregation(function="count", column=None, name=group_count_name),
            ],
        )
    )
    if isinstance(plan, RankPlan):
        steps.extend(
            [
                SortRows(columns=[value_name], order=plan.order),
                LimitRows(count=plan.limit),
            ]
        )

    run = run_recipe(frame, planned_columns(profile.column_schemas), Recipe(steps=steps))
    if run.refusal is not None:
        raise PlanRefused(run.refusal.reason)
    if groups and float(run.frame[group_count_name].median()) < MIN_TYPICAL_GROUP_SIZE:
        raise PlanRefused(
            "This grouping is too close to individual rows to send for explanation. "
            "Choose a broader category or time grain."
        )

    all_rows = []
    for values in run.frame.to_dict(orient="records"):
        row = {
            output_groups[index]: str(values[group])
            for index, group in enumerate(groups)
        }
        row["value"] = _finite(values[value_name])
        all_rows.append(row)
    rows = all_rows[:MAX_RESULT_ROWS]
    truncated = len(all_rows) > len(rows)
    value_label = f"{plan.function} {plan.measure}" if plan.measure else "row count"
    if rows and groups and isinstance(plan, RankPlan):
        leader = rows[0]
        labels = ", ".join(str(leader[name]) for name in output_groups)
        direction = "highest" if plan.order == "desc" else "lowest"
        message = f"{labels} has the {direction} {value_label}: {leader['value']}."
    elif rows and groups:
        message = f"Computed {len(all_rows)} grouped results for {value_label}."
    elif rows:
        message = f"The {value_label} is {rows[0]['value']}."
    else:
        message = "No rows matched the question."

    chart = None
    if rows and groups:
        chart = ChartSpec(
            id=f"question-{plan.operation}-bar",
            chart_type="bar",
            title=f"{value_label} by {', '.join(output_groups)}",
            columns=[*plan.group_by, *( [plan.measure] if plan.measure else [])],
            x_label=" / ".join(output_groups),
            y_label=value_label,
            data=BarData(
                categories=[" / ".join(str(row[name]) for name in output_groups) for row in rows],
                counts=[float(row["value"] or 0) for row in rows],
                other_count=0,
            ),
        )
    caveats = [f"Only the first {MAX_RESULT_ROWS} result rows are shown."] if truncated else []
    metrics = {**_metric_rows(rows), "matched_rows": len(_filtered(frame, profile, plan))}
    insight = _insight(
        plan.operation,
        [*plan.group_by, *( [plan.measure] if plan.measure else [])],
        message,
        metrics,
        metrics["matched_rows"],
        chart,
        caveats,
    )
    references = [str(row[output_groups[0]]) for row in rows] if output_groups else []
    return ComputedQuery(
        insight=insight,
        chart=chart,
        rows=rows,
        result_truncated=truncated,
        reference_values=references,
    )


def execute_plan(
    frame: pd.DataFrame, profile: DatasetProfile, plan: AnalysisPlan
) -> ComputedQuery:
    validate_plan(plan, profile)
    filtered = _filtered(frame, profile, plan)

    if isinstance(plan, (AggregatePlan, RankPlan)):
        return _aggregate(frame, profile, plan)

    if isinstance(plan, CountPlan):
        count = len(filtered)
        message = f"{count} rows match the question."
        insight = _insight("count", [], message, {"count": count}, count)
        return ComputedQuery(insight=insight, rows=[{"count": count}])

    if isinstance(plan, ComparePlan):
        comparison = analyze_groups(filtered, plan.group_by, plan.measure)
        if comparison is None:
            raise PlanRefused("Fewer than two sufficiently large groups remain to compare.")
        chart = box_chart(comparison)
        message = (
            f"{comparison.highest_group} has the highest average {plan.measure}; "
            f"{comparison.lowest_group} has the lowest."
        )
        rows = [
            {"group": group.name, "count": group.count, "mean": group.mean, "median": group.median}
            for group in comparison.groups[:MAX_RESULT_ROWS]
        ]
        metrics = {
            key: value
            for key, value in comparison.model_dump().items()
            if key != "groups"
        } | _metric_rows(rows)
        insight = _insight(
            "compare", [plan.group_by, plan.measure], message, metrics,
            comparison.sample_size, chart,
        )
        return ComputedQuery(insight=insight, chart=chart, rows=rows)

    if isinstance(plan, RelatePlan):
        pairs = analyze_correlations(filtered, [plan.measure, plan.secondary_measure])
        if not pairs:
            raise PlanRefused("The two columns have too few paired values or one never varies.")
        pair = pairs[0]
        chart = scatter_chart(filtered, pair)
        message = f"{pair.column_a} and {pair.column_b} have correlation {pair.pearson:.2f}."
        insight = _insight(
            "relate", [pair.column_a, pair.column_b], message, pair.model_dump(),
            pair.sample_size, chart, ["Association does not establish causation."],
        )
        return ComputedQuery(insight=insight, chart=chart)

    if isinstance(plan, TrendPlan):
        timeline = analyze_timeline(filtered, plan.time, plan.measure)
        if timeline is None:
            raise PlanRefused("At least three observed periods are needed for a trend.")
        chart = line_chart(timeline)
        message = f"{plan.measure} is {timeline.trend} from {timeline.start} to {timeline.end}."
        metrics = {
            key: value
            for key, value in timeline.model_dump().items()
            if key not in {"points", "largest_change", "seasonality"}
        }
        if timeline.largest_change is not None:
            metrics.update(
                {f"largest_change_{key}": value for key, value in timeline.largest_change.model_dump().items()}
            )
        if timeline.seasonality is not None:
            metrics.update(
                {f"seasonality_{key}": value for key, value in timeline.seasonality.model_dump().items()}
            )
        insight = _insight(
            "trend", [plan.time, plan.measure], message, metrics,
            timeline.sample_size, chart,
        )
        return ComputedQuery(insight=insight, chart=chart)

    if isinstance(plan, DistributionPlan):
        schema = next(column for column in profile.column_schemas if column.name == plan.column)
        if schema.inferred_type == "numeric":
            summary = analyze_numeric(filtered[plan.column])
            chart = histogram_chart(summary)
            message = f"{plan.column} has median {summary.median} across {summary.count} values."
            metrics = {
                key: value for key, value in summary.model_dump().items() if key != "histogram"
            }
            rows = []
        else:
            summary = analyze_categorical(filtered[plan.column])
            chart = bar_chart(summary)
            top = summary.top_categories[0] if summary.top_categories else None
            message = (
                f"{top.value} is the most common {plan.column}, with {top.count} rows."
                if top else f"{plan.column} has no non-missing values."
            )
            rows = [item.model_dump() for item in summary.top_categories]
            metrics = {
                key: value for key, value in summary.model_dump().items() if key != "top_categories"
            } | _metric_rows(rows)
        insight = _insight(
            "distribution", [plan.column], message, metrics,
            summary.count, chart,
        )
        return ComputedQuery(insight=insight, chart=chart, rows=rows)

    if isinstance(plan, DescribePlan):
        column = next(column for column in profile.column_schemas if column.name == plan.column)
        metrics = {
            "missing_count": column.missing_count,
            "missing_ratio": column.missing_ratio,
            "unique_count": column.unique_count,
        }
        message = (
            f"{column.name} is a {column.inferred_type} column with "
            f"{column.unique_count} distinct values and {column.missing_count} missing values."
        )
        insight = _insight("describe", [column.name], message, metrics, profile.rows)
        return ComputedQuery(insight=insight, rows=[{
            "column": column.name,
            "type": column.inferred_type,
            **metrics,
        }])

    raise PlanRefused("That analysis operation is not supported.")
