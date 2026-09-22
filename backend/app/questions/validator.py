from app.profiling.models import ColumnSchema, DatasetProfile
from app.recipes import FilterRows, planned_columns
from app.recipes.validator import validate_step

from .models import (
    AggregatePlan,
    AnalysisPlan,
    ComparePlan,
    CountPlan,
    DescribePlan,
    DistributionPlan,
    RankPlan,
    RelatePlan,
    TrendPlan,
)


class PlanRefused(ValueError):
    pass


def _column(profile: DatasetProfile, name: str) -> ColumnSchema:
    found = next((column for column in profile.column_schemas if column.name == name), None)
    if found is None:
        raise PlanRefused(f'There is no column named "{name}" in this dataset.')
    return found


def _numeric(profile: DatasetProfile, name: str, action: str) -> ColumnSchema:
    column = _column(profile, name)
    if column.inferred_type != "numeric":
        raise PlanRefused(
            f'"{name}" is a {column.inferred_type} column, so it cannot be used to {action}.'
        )
    return column


def _groupable(profile: DatasetProfile, name: str) -> ColumnSchema:
    column = _column(profile, name)
    if column.is_probable_id:
        raise PlanRefused(
            f'"{name}" looks like a row identifier, so grouping by it could expose individual rows.'
        )
    if column.is_high_cardinality:
        raise PlanRefused(
            f'"{name}" has too many distinct values to group safely. Choose a broader category.'
        )
    if column.inferred_type not in {"categorical", "boolean", "datetime"}:
        raise PlanRefused(
            f'"{name}" is a {column.inferred_type} column and cannot define groups.'
        )
    return column


def validate_plan(plan: AnalysisPlan, profile: DatasetProfile) -> None:
    if plan.filters:
        refusal = validate_step(
            planned_columns(profile.column_schemas), FilterRows(clauses=plan.filters)
        )
        if refusal is not None:
            raise PlanRefused(refusal.reason)

    match plan:
        case AggregatePlan() | RankPlan():
            groups = [_groupable(profile, name) for name in plan.group_by]
            dates = [column for column in groups if column.inferred_type == "datetime"]
            if dates and plan.time_grain is None:
                raise PlanRefused(
                    f'Grouping by date column "{dates[0].name}" needs an explicit time_grain.'
                )
            if not dates and plan.time_grain is not None:
                raise PlanRefused("time_grain can only be used with a date group.")
            if plan.measure is not None:
                if plan.function == "count":
                    _column(profile, plan.measure)
                else:
                    _numeric(profile, plan.measure, plan.function)
        case ComparePlan():
            _groupable(profile, plan.group_by)
            _numeric(profile, plan.measure, "compare groups")
        case RelatePlan():
            _numeric(profile, plan.measure, "measure a relationship")
            _numeric(profile, plan.secondary_measure, "measure a relationship")
            if plan.measure == plan.secondary_measure:
                raise PlanRefused("A column cannot be related to itself.")
        case TrendPlan():
            time = _column(profile, plan.time)
            if time.inferred_type != "datetime":
                raise PlanRefused(f'"{plan.time}" is not a date column, so it cannot define a trend.')
            _numeric(profile, plan.measure, "measure a trend")
        case DistributionPlan():
            column = _column(profile, plan.column)
            if column.is_probable_id or column.is_high_cardinality:
                raise PlanRefused(
                    f'"{plan.column}" is too close to individual rows to describe safely.'
                )
            if column.inferred_type in {"text", "empty", "datetime"}:
                raise PlanRefused(
                    f'"{plan.column}" is a {column.inferred_type} column and has no supported distribution.'
                )
            if column.inferred_type == "categorical" and (
                column.unique_count / max(profile.rows, 1) > 0.2
            ):
                raise PlanRefused(
                    f'"{plan.column}" is too close to individual rows to describe safely.'
                )
        case DescribePlan():
            _column(profile, plan.column)
        case CountPlan():
            pass
