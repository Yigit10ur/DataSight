from dataclasses import dataclass

import numpy as np
import pandas as pd
from pydantic import BaseModel

from app.analysis.numbers import numeric_values
from app.recipes.models import (
    Aggregate,
    Aggregation,
    ArithmeticExpression,
    BinExpression,
    CastColumn,
    ColumnOperand,
    DatetimePartExpression,
    DeriveColumn,
    DropColumns,
    DropDuplicates,
    DropMissing,
    FillMissing,
    FilterClause,
    FilterRows,
    LimitRows,
    MapValuesExpression,
    Operand,
    PlannedColumn,
    Recipe,
    RenameColumn,
    SelectColumns,
    SortRows,
    StepRefusal,
    TransformStep,
)
from app.recipes.schema import aggregation_name, find_column, plan_schema
from app.recipes.validator import StepRefused, validate_step

# How much of a column may fail to convert before a cast is refused instead of
# quietly turning values into gaps.
MAX_CAST_LOSS_RATIO = 0.1

TRUE_TOKENS = {"true", "yes", "y", "1", "evet"}

# Written as strings, in the order a reader would sort them, because a derived part
# of a date is a label to group by rather than a number to average.
DATETIME_PART_FORMATS = {
    "year": "%Y",
    "month": "%m",
    "week": "%V",
    "weekday": "%A",
    "hour": "%H",
}

WHOLE_TABLE_FUNCTIONS = {
    "sum": lambda series: series.sum(),
    "mean": lambda series: series.mean(),
    "median": lambda series: series.median(),
    "min": lambda series: series.min(),
    "max": lambda series: series.max(),
    "count": lambda series: series.count(),
}


class StepReport(BaseModel):
    """What one step did, for a reader watching the row count move."""

    step_index: int
    op: str
    rows_in: int
    rows_out: int
    # Anything the step had to do that the reader did not ask for and should know
    # about: rows left out of a grouping, values that would not divide.
    note: str | None = None


@dataclass(frozen=True)
class RecipeRun:
    """The result of running a recipe as far as it would go.

    On a refusal the frame is the one the last accepted step left behind, so the
    reader keeps what they had while they fix the step that failed.
    """

    frame: pd.DataFrame
    columns: list[PlannedColumn]
    reports: list[StepReport]
    refusal: StepRefusal | None


def _as_number(value: object) -> float:
    return float(value) if isinstance(value, bool) else float(str(value))


def _as_moment(value: object) -> pd.Timestamp:
    return pd.to_datetime(str(value), format="mixed", dayfirst=False)


def _as_truth(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in TRUE_TOKENS


def _truth_values(series: pd.Series) -> pd.Series:
    """Read a column as true/false, keeping its gaps as gaps."""
    if pd.api.types.is_bool_dtype(series):
        return series
    lowered = series.astype(str).str.strip().str.lower()
    return lowered.isin(TRUE_TOKENS).where(series.notna())


def _moment_values(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    return pd.to_datetime(series, errors="coerce", format="mixed", dayfirst=False)


def _comparable(series: pd.Series, inferred_type: str) -> pd.Series:
    if inferred_type == "numeric":
        return numeric_values(series)
    if inferred_type == "datetime":
        return _moment_values(series)
    if inferred_type == "boolean":
        return _truth_values(series)
    return series.astype(str).where(series.notna())


def _comparable_value(value: object, inferred_type: str) -> object:
    if inferred_type == "numeric":
        return _as_number(value)
    if inferred_type == "datetime":
        return _as_moment(value)
    if inferred_type == "boolean":
        return _as_truth(value)
    return str(value)


def _clause_mask(frame: pd.DataFrame, clause: FilterClause, inferred_type: str) -> pd.Series:
    series = frame[clause.column]

    if clause.operator == "is_missing":
        return series.isna()
    if clause.operator == "not_missing":
        return series.notna()

    left = _comparable(series, inferred_type)

    if clause.operator in {"in", "not_in"}:
        wanted = [_comparable_value(value, inferred_type) for value in clause.value or []]
        matched = left.isin(wanted)
        mask = ~matched if clause.operator == "not_in" else matched
    elif clause.operator == "contains":
        # Never a regular expression: a reader searching for "(TR)" is searching for
        # those characters, and a pattern from outside is not something to run.
        mask = left.str.contains(str(clause.value), case=False, regex=False, na=False)
    else:
        right = _comparable_value(clause.value, inferred_type)
        comparisons = {
            "eq": lambda: left == right,
            "ne": lambda: left != right,
            "lt": lambda: left < right,
            "lte": lambda: left <= right,
            "gt": lambda: left > right,
            "gte": lambda: left >= right,
        }
        mask = comparisons[clause.operator]()

    # A row with no value in the column answers no question about it. Pandas would
    # call a missing revenue "not 5" and keep the row; a reader who wants those rows
    # has an operator that says so.
    return mask.fillna(False) & series.notna()


def _apply_filter(
    frame: pd.DataFrame, columns: list[PlannedColumn], step: FilterRows
) -> pd.DataFrame:
    masks = []
    for clause in step.clauses:
        column = find_column(columns, clause.column)
        inferred_type = column.inferred_type if column else "text"
        masks.append(_clause_mask(frame, clause, inferred_type))

    combined = masks[0]
    for mask in masks[1:]:
        combined = (combined & mask) if step.combine == "and" else (combined | mask)
    return frame[combined]


def _fill_value(series: pd.Series, step: FillMissing, inferred_type: str) -> object | None:
    if step.method == "median":
        return numeric_values(series).median()
    if step.method == "mean":
        return numeric_values(series).mean()
    if step.method == "mode":
        modes = series.mode(dropna=True)
        return modes.iloc[0] if not modes.empty else None
    if inferred_type == "empty":
        return step.value
    return _comparable_value(step.value, inferred_type)


def _apply_fill(frame: pd.DataFrame, step: FillMissing, inferred_type: str) -> pd.DataFrame:
    frame = frame.copy()
    if step.method == "forward":
        frame[step.column] = frame[step.column].ffill()
        return frame

    value = _fill_value(frame[step.column], step, inferred_type)
    if value is None or (isinstance(value, float) and np.isnan(value)):
        # Nothing to fill with: every value in the column is already missing. The
        # step is a no-op rather than a refusal, because the recipe still means what
        # it meant and a later file may have values.
        return frame
    frame[step.column] = frame[step.column].fillna(value)
    return frame


def _as_labels(series: pd.Series) -> pd.Series:
    """Turn a column into its labels, leaving gaps alone.

    `astype(str)` would write the string "nan" into every gap, which then reads as a
    category of its own for the rest of the recipe.
    """
    return series.astype(str).where(series.notna())


def _cast(frame: pd.DataFrame, step: CastColumn) -> tuple[pd.DataFrame, str | None]:
    series = frame[step.column]
    had = int(series.notna().sum())

    if step.to == "numeric":
        converted = numeric_values(series)
    elif step.to == "datetime":
        converted = pd.to_datetime(series, errors="coerce", format="mixed", dayfirst=False)
    else:
        # Written as a declared dtype rather than as bare strings, so that profiling
        # the result reads back what the reader asked for instead of re-deciding it
        # from how many distinct values happen to be left.
        converted = _as_labels(series).astype("category" if step.to == "categorical" else "string")

    lost = had - int(converted.notna().sum())
    if had and lost / had > MAX_CAST_LOSS_RATIO:
        share = lost / had
        raise StepRefused(
            f'Reading "{step.column}" as {step.to} would turn {lost} of {had} values '
            f"into gaps ({share:.0%}). Clean them first, or filter them out.",
            step.column,
        )

    frame = frame.copy()
    frame[step.column] = converted
    return frame, f"{lost} values could not be read as {step.to}." if lost else None


def _operand_values(frame: pd.DataFrame, operand: Operand) -> pd.Series | float:
    if isinstance(operand, ColumnOperand):
        return numeric_values(frame[operand.name])
    return operand.value


def _arithmetic(
    frame: pd.DataFrame, expression: ArithmeticExpression
) -> tuple[pd.Series, str | None]:
    left = _operand_values(frame, expression.left)
    right = _operand_values(frame, expression.right)

    if expression.operator == "add":
        return left + right, None
    if expression.operator == "subtract":
        return left - right, None
    if expression.operator == "multiply":
        return left * right, None

    # A zero denominator is a gap, not an error and not infinity: the row has no
    # answer, and saying so leaves the rest of the column usable.
    divided = (left / right).replace([np.inf, -np.inf], np.nan)
    zeros = int((right == 0).sum()) if isinstance(right, pd.Series) else 0
    note = f"{zeros} rows had nothing to divide by." if zeros else None
    return divided, note


def _binned(frame: pd.DataFrame, expression: BinExpression) -> pd.Series:
    values = numeric_values(frame[expression.column])
    labels = expression.labels or None
    try:
        if expression.edges:
            cut = pd.cut(values, bins=expression.edges, labels=labels)
        else:
            cut = pd.qcut(values, q=expression.quantiles, labels=labels, duplicates="drop")
    except ValueError as error:
        raise StepRefused(
            f'"{expression.column}" does not have enough distinct values to split into '
            f"{expression.quantiles} buckets of equal size.",
            expression.column,
        ) from error
    return _as_labels(cut)


def _datetime_part(frame: pd.DataFrame, expression: DatetimePartExpression) -> pd.Series:
    moments = _moment_values(frame[expression.column])
    if expression.part == "date":
        # The one part that is still a date: kept as one, so it can be filtered on a
        # range and read as a timeline later.
        return moments.dt.normalize()
    if expression.part == "quarter":
        parts = moments.dt.quarter.map(lambda quarter: f"Q{quarter}", na_action="ignore")
        return parts.where(moments.notna())
    return moments.dt.strftime(DATETIME_PART_FORMATS[expression.part]).where(moments.notna())


def _mapped(frame: pd.DataFrame, expression: MapValuesExpression) -> pd.Series:
    labels = _as_labels(frame[expression.column])
    mapped = labels.map(expression.mapping)
    fallback = expression.default if expression.default is not None else labels
    return mapped.where(mapped.notna(), fallback).where(labels.notna())


def _apply_derive(frame: pd.DataFrame, step: DeriveColumn) -> tuple[pd.DataFrame, str | None]:
    expression = step.expression
    note = None

    match expression:
        case ArithmeticExpression():
            values, note = _arithmetic(frame, expression)
        case BinExpression():
            values = _binned(frame, expression)
        case DatetimePartExpression():
            values = _datetime_part(frame, expression)
        case MapValuesExpression():
            values = _mapped(frame, expression)

    frame = frame.copy()
    frame[step.name.strip()] = values
    return frame, note


def _whole_table_aggregate(frame: pd.DataFrame, step: Aggregate) -> pd.DataFrame:
    row: dict[str, object] = {}
    for aggregation in step.aggregations:
        name = aggregation_name(aggregation)
        if aggregation.column is None:
            row[name] = len(frame)
        else:
            values = frame[aggregation.column]
            if aggregation.function != "count":
                values = numeric_values(values)
            row[name] = WHOLE_TABLE_FUNCTIONS[aggregation.function](values)
    return pd.DataFrame([row])


def _apply_aggregate(frame: pd.DataFrame, step: Aggregate) -> tuple[pd.DataFrame, str | None]:
    if not step.group_by:
        return _whole_table_aggregate(frame, step), None

    incomplete = int(frame[step.group_by].isna().any(axis=1).sum())
    grouped = frame.groupby(step.group_by, dropna=True, observed=True)

    spec: dict[str, pd.NamedAgg] = {}
    for aggregation in step.aggregations:
        name = aggregation_name(aggregation)
        if aggregation.column is None:
            spec[name] = pd.NamedAgg(column=step.group_by[0], aggfunc="size")
        else:
            spec[name] = pd.NamedAgg(column=aggregation.column, aggfunc=aggregation.function)

    result = grouped.agg(**spec).reset_index()
    note = None
    if incomplete:
        columns = " and ".join(f'"{name}"' for name in step.group_by)
        note = f"{incomplete} rows had no {columns} and were left out."
    return result, note


def apply_step(
    frame: pd.DataFrame, columns: list[PlannedColumn], step: TransformStep
) -> tuple[pd.DataFrame, str | None]:
    """Run one already-validated step, and say anything the reader should know.

    Raises `StepRefused` for the refusals that cannot be made without the data —
    a conversion that would destroy most of a column, a quantile split a column has
    too few distinct values for.
    """
    match step:
        case SelectColumns():
            return frame.loc[:, step.columns], None

        case DropColumns():
            return frame.drop(columns=step.columns), None

        case FilterRows():
            return _apply_filter(frame, columns, step), None

        case SortRows():
            # Stable, so that two runs of the same recipe order ties the same way,
            # and gaps last, so an empty column never leads the table.
            return (
                frame.sort_values(
                    by=step.columns,
                    ascending=step.order == "asc",
                    kind="stable",
                    na_position="last",
                ),
                None,
            )

        case LimitRows():
            if step.method == "sample":
                return frame.sample(n=min(step.count, len(frame)), random_state=step.seed), None
            return frame.head(step.count), None

        case DropMissing():
            return frame.dropna(subset=step.columns or None, how=step.how), None

        case DropDuplicates():
            return frame.drop_duplicates(subset=step.columns or None), None

        case FillMissing():
            column = find_column(columns, step.column)
            inferred_type = column.inferred_type if column else "text"
            return _apply_fill(frame, step, inferred_type), None

        case RenameColumn():
            return frame.rename(columns={step.column: step.to.strip()}), None

        case CastColumn():
            return _cast(frame, step)

        case DeriveColumn():
            return _apply_derive(frame, step)

        case Aggregate():
            return _apply_aggregate(frame, step)

    raise ValueError(f"Unknown step: {step}")  # pragma: no cover


def run_recipe(frame: pd.DataFrame, columns: list[PlannedColumn], recipe: Recipe) -> RecipeRun:
    """Validate and run each step in turn, stopping at the first one that refuses.

    Validation and execution are interleaved rather than done in two passes because
    some refusals need the data — how much of a column a conversion would destroy is
    not a question the schema can answer — and because stopping mid-recipe has to
    leave a frame behind either way.
    """
    reports: list[StepReport] = []

    for index, step in enumerate(recipe.steps):
        refusal = validate_step(columns, step, index)
        if refusal is not None:
            return RecipeRun(frame=frame, columns=columns, reports=reports, refusal=refusal)

        rows_in = len(frame)
        try:
            frame, note = apply_step(frame, columns, step)
        except StepRefused as refused:
            return RecipeRun(
                frame=frame,
                columns=columns,
                reports=reports,
                refusal=StepRefusal(
                    step_index=index, op=step.op, column=refused.column, reason=refused.reason
                ),
            )

        columns = plan_schema(columns, step)
        reports.append(
            StepReport(
                step_index=index, op=step.op, rows_in=rows_in, rows_out=len(frame), note=note
            )
        )

    return RecipeRun(frame=frame, columns=columns, reports=reports, refusal=None)
