import pandas as pd

from app.profiling.schema_detector import BOOLEAN_TOKENS
from app.recipes.models import (
    MAX_BIN_COUNT,
    AnalyzeStep,
    MAX_GROUP_COLUMNS,
    Aggregate,
    ArithmeticExpression,
    BinExpression,
    CastColumn,
    ColumnOperand,
    Compare,
    ConstantOperand,
    DatetimePartExpression,
    DeriveColumn,
    Distribution,
    DropColumns,
    DropDuplicates,
    DropMissing,
    FillMissing,
    FilterClause,
    FilterRows,
    MapValuesExpression,
    Operand,
    PlannedColumn,
    Recipe,
    Relate,
    RecipeValidation,
    RenameColumn,
    SelectColumns,
    SortRows,
    StepRefusal,
    TransformStep,
    Trend,
)
from app.recipes.schema import aggregation_name, find_column, plan_schema

ORDERED_TYPES = {"numeric", "datetime"}
TEXTUAL_TYPES = {"categorical", "boolean", "text"}
GROUPABLE_TYPES = {"categorical", "boolean", "datetime"}

ORDERING_OPERATORS = {"lt", "lte", "gt", "gte"}
MISSINGNESS_OPERATORS = {"is_missing", "not_missing"}
MEMBERSHIP_OPERATORS = {"in", "not_in"}

TYPE_LABELS = {
    "numeric": "a number column",
    "categorical": "a category column",
    "boolean": "a true/false column",
    "datetime": "a date column",
    "text": "a text column",
    "empty": "an empty column",
}


class StepRefused(Exception):
    """One step cannot be applied, and this is why.

    Carried as an exception only so that a check buried three levels inside an
    expression can stop the walk. It leaves the validator as a `StepRefusal`, which
    is a normal response and never an error.
    """

    def __init__(self, reason: str, column: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.column = column


def _label(column: PlannedColumn) -> str:
    return TYPE_LABELS[column.inferred_type]


def _require(columns: list[PlannedColumn], name: str) -> PlannedColumn:
    column = find_column(columns, name)
    if column is None:
        raise StepRefused(f'There is no column named "{name}" at this point in the recipe.', name)
    return column


def _require_all(columns: list[PlannedColumn], names: list[str], what: str) -> None:
    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise StepRefused(f'"{name}" is named twice in the same {what}.', name)
        seen.add(name)
        _require(columns, name)


def _require_free(columns: list[PlannedColumn], name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise StepRefused("A new column needs a name.")
    if find_column(columns, cleaned) is not None:
        raise StepRefused(f'There is already a column named "{cleaned}".', cleaned)
    return cleaned


def _coercible(value: object, inferred_type: str) -> bool:
    """Can this literal be read as a value of that column's type?"""
    if inferred_type == "numeric":
        if isinstance(value, bool):
            return True
        try:
            float(str(value))
        except (TypeError, ValueError):
            return False
        return True
    if inferred_type == "datetime":
        # A bare number parses as a date — 1000 becomes a moment in 1970 — so only a
        # written date is accepted. A number here is a mistake, not a timestamp.
        if not isinstance(value, str):
            return False
        return pd.to_datetime(value, errors="coerce", format="mixed", dayfirst=False) is not pd.NaT
    if inferred_type == "boolean":
        return isinstance(value, bool) or str(value).strip().lower() in BOOLEAN_TOKENS
    if inferred_type == "empty":
        return False
    return True


def _check_value_coerces(column: PlannedColumn, value: object) -> None:
    if _coercible(value, column.inferred_type):
        return
    raise StepRefused(
        f'"{value}" cannot be read as a value of "{column.name}", which is {_label(column)}.',
        column.name,
    )


def _check_filter_clause(columns: list[PlannedColumn], clause: FilterClause) -> None:
    column = _require(columns, clause.column)

    if clause.operator in MISSINGNESS_OPERATORS:
        return

    if column.inferred_type == "empty":
        raise StepRefused(
            f'"{column.name}" is empty, so there is nothing to compare. '
            "Filter it on whether it is missing instead.",
            column.name,
        )

    if clause.operator in ORDERING_OPERATORS and column.inferred_type not in ORDERED_TYPES:
        raise StepRefused(
            f'"{column.name}" is {_label(column)} and cannot be ordered. '
            "Try: is, is not, or one of a list.",
            column.name,
        )

    if clause.operator == "contains" and column.inferred_type not in TEXTUAL_TYPES:
        raise StepRefused(
            f'"{column.name}" is {_label(column)}, so it has no text to search.',
            column.name,
        )

    if clause.operator in MEMBERSHIP_OPERATORS:
        if not isinstance(clause.value, list) or not clause.value:
            raise StepRefused(
                f'"{clause.operator}" needs a list of values to match against.', column.name
            )
        for value in clause.value:
            _check_value_coerces(column, value)
        return

    if clause.value is None or isinstance(clause.value, list):
        raise StepRefused(
            f'"{clause.operator}" needs a single value to compare against.', column.name
        )
    _check_value_coerces(column, clause.value)


def _check_operand(columns: list[PlannedColumn], operand: Operand, operator: str) -> None:
    if isinstance(operand, ConstantOperand):
        if operator == "divide" and operand.value == 0:
            raise StepRefused("Dividing by zero leaves nothing to analyse.")
        return
    if isinstance(operand, ColumnOperand):
        column = _require(columns, operand.name)
        if column.inferred_type != "numeric":
            raise StepRefused(
                f'"{column.name}" is {_label(column)} and cannot be used in arithmetic.',
                column.name,
            )


def _check_bin(columns: list[PlannedColumn], expression: BinExpression) -> None:
    column = _require(columns, expression.column)
    if column.inferred_type != "numeric":
        raise StepRefused(
            f'"{column.name}" is {_label(column)}, and only numbers can be binned.', column.name
        )

    if bool(expression.edges) == (expression.quantiles is not None):
        raise StepRefused(
            "Bins need either cut points or a number of equal-sized buckets, not both."
        )

    if expression.edges:
        if len(expression.edges) < 2:
            raise StepRefused(
                "Cut points have to describe at least one bin, so there must be two."
            )
        if any(a >= b for a, b in zip(expression.edges, expression.edges[1:])):
            raise StepRefused("Cut points have to increase.")
        bin_count = len(expression.edges) - 1
    else:
        quantiles = expression.quantiles or 0
        if not 2 <= quantiles <= MAX_BIN_COUNT:
            raise StepRefused(f"Between 2 and {MAX_BIN_COUNT} buckets, not {quantiles}.")
        bin_count = quantiles

    if expression.labels and len(expression.labels) != bin_count:
        raise StepRefused(f"There are {bin_count} bins but {len(expression.labels)} labels.")


def _check_derive(columns: list[PlannedColumn], step: DeriveColumn) -> None:
    _require_free(columns, step.name)
    expression = step.expression

    match expression:
        case ArithmeticExpression():
            _check_operand(columns, expression.left, expression.operator)
            _check_operand(columns, expression.right, expression.operator)
        case BinExpression():
            _check_bin(columns, expression)
        case DatetimePartExpression():
            column = _require(columns, expression.column)
            if column.inferred_type != "datetime":
                raise StepRefused(
                    f'"{column.name}" is {_label(column)}, so it has no '
                    f"{expression.part} to read.",
                    column.name,
                )
        case MapValuesExpression():
            column = _require(columns, expression.column)
            if column.inferred_type not in TEXTUAL_TYPES:
                raise StepRefused(
                    f'"{column.name}" is {_label(column)}, and only categories can be remapped.',
                    column.name,
                )


def _check_aggregate(columns: list[PlannedColumn], step: Aggregate) -> None:
    if len(step.group_by) > MAX_GROUP_COLUMNS:
        raise StepRefused(
            f"Grouping by more than {MAX_GROUP_COLUMNS} columns leaves a table nobody can read."
        )
    _require_all(columns, step.group_by, "grouping")

    for name in step.group_by:
        column = _require(columns, name)
        if column.inferred_type not in GROUPABLE_TYPES:
            # Numbers can be made groupable; free text and empty columns cannot, so
            # sending the reader to the bin dialog would waste the trip.
            hint = (
                "Bin it into ranges first."
                if column.inferred_type == "numeric"
                else "Map its values into categories first."
            )
            raise StepRefused(
                f'"{name}" is {_label(column)} and cannot be grouped on. {hint}', name
            )
        if column.is_probable_id:
            raise StepRefused(
                f'"{name}" looks like a row identifier, so each group would hold one row.', name
            )
        if column.is_high_cardinality:
            raise StepRefused(
                f'"{name}" has too many distinct values to group by. '
                "Filter it down, or map its values into fewer categories first.",
                name,
            )

    produced: set[str] = set(step.group_by)
    for aggregation in step.aggregations:
        if aggregation.function == "count":
            if aggregation.column is not None:
                _require(columns, aggregation.column)
        elif aggregation.column is None:
            raise StepRefused(f'"{aggregation.function}" needs a column to summarise.')
        else:
            column = _require(columns, aggregation.column)
            if column.inferred_type != "numeric":
                raise StepRefused(
                    f'"{column.name}" is {_label(column)}, so there is no '
                    f"{aggregation.function} of it. Try: count.",
                    column.name,
                )

        name = aggregation_name(aggregation)
        if name in produced:
            raise StepRefused(f'Two results would both be called "{name}".', name)
        produced.add(name)


def _check_step(columns: list[PlannedColumn], step: TransformStep) -> None:
    match step:
        case SelectColumns():
            _require_all(columns, step.columns, "selection")

        case DropColumns():
            _require_all(columns, step.columns, "removal")
            if len(set(step.columns)) == len(columns):
                raise StepRefused("Removing every column would leave nothing to work with.")

        case FilterRows():
            for clause in step.clauses:
                _check_filter_clause(columns, clause)

        case SortRows():
            _require_all(columns, step.columns, "sort")

        case DropMissing():
            _require_all(columns, step.columns, "step")

        case DropDuplicates():
            _require_all(columns, step.columns, "step")

        case FillMissing():
            _check_fill(columns, step)

        case RenameColumn():
            column = _require(columns, step.column)
            cleaned = step.to.strip()
            if cleaned == column.name:
                raise StepRefused(f'"{column.name}" is already called that.', column.name)
            _require_free(columns, step.to)

        case CastColumn():
            column = _require(columns, step.column)
            if column.inferred_type == "empty":
                raise StepRefused(
                    f'"{column.name}" has no values to convert.', column.name
                )

        case DeriveColumn():
            _check_derive(columns, step)

        case Aggregate():
            _check_aggregate(columns, step)


def _check_fill(columns: list[PlannedColumn], step: FillMissing) -> None:
    column = _require(columns, step.column)

    if step.method in {"median", "mean"} and column.inferred_type != "numeric":
        raise StepRefused(
            f'"{column.name}" is {_label(column)} and has no {step.method}. '
            "Try: most frequent value, or a constant.",
            column.name,
        )
    if step.method in {"mode", "forward"} and column.inferred_type == "empty":
        raise StepRefused(
            f'"{column.name}" is empty, so there is no value to carry into the gaps. '
            "Fill it with a constant instead.",
            column.name,
        )
    if step.method == "constant":
        if step.value is None:
            raise StepRefused("Filling with a constant needs a value.", column.name)
        if column.inferred_type != "empty":
            _check_value_coerces(column, step.value)


def _require_measure(columns: list[PlannedColumn], name: str, what: str) -> PlannedColumn:
    column = _require(columns, name)
    if column.inferred_type != "numeric":
        raise StepRefused(f'"{name}" is {_label(column)}, so there is nothing to {what}.', name)
    return column


def _check_analyze(columns: list[PlannedColumn], step: AnalyzeStep) -> None:
    match step:
        case Compare():
            group = _require(columns, step.group_by)
            if group.inferred_type not in GROUPABLE_TYPES:
                raise StepRefused(
                    f'"{group.name}" is {_label(group)}, so it has no groups to compare across.',
                    group.name,
                )
            if group.is_probable_id:
                raise StepRefused(
                    f'"{group.name}" looks like a row identifier, so every group '
                    "would hold one row.",
                    group.name,
                )
            if group.is_high_cardinality:
                raise StepRefused(
                    f'"{group.name}" has too many distinct values to compare across.',
                    group.name,
                )
            _require_measure(columns, step.measure, "compare")

        case Relate():
            if step.left == step.right:
                raise StepRefused(
                    f'"{step.left}" relates to itself perfectly, which says nothing.', step.left
                )
            _require_measure(columns, step.left, "relate")
            _require_measure(columns, step.right, "relate")

        case Trend():
            time = _require(columns, step.time)
            if time.inferred_type != "datetime":
                raise StepRefused(
                    f'"{time.name}" is {_label(time)}, so it cannot put anything in order '
                    "of time. Convert it to a date first.",
                    time.name,
                )
            _require_measure(columns, step.measure, "follow over time")

        case Distribution():
            column = _require(columns, step.column)
            if column.inferred_type in {"text", "empty"}:
                raise StepRefused(
                    f'"{column.name}" is {_label(column)}, and it has no spread to describe.',
                    column.name,
                )
            if column.inferred_type == "datetime":
                raise StepRefused(
                    f'"{column.name}" is a date column. Ask for a trend over it, or take a '
                    "part of it first.",
                    column.name,
                )


def validate_analyze(
    columns: list[PlannedColumn], step: AnalyzeStep, step_index: int = 0
) -> StepRefusal | None:
    """Check the terminal analysis against the schema the steps above it leave."""
    try:
        _check_analyze(columns, step)
    except StepRefused as refused:
        return StepRefusal(
            step_index=step_index, op=step.op, column=refused.column, reason=refused.reason
        )
    return None


def validate_step(
    columns: list[PlannedColumn], step: TransformStep, step_index: int = 0
) -> StepRefusal | None:
    """Check one step against the schema as it stands, and say why not if it fails."""
    try:
        _check_step(columns, step)
    except StepRefused as refused:
        return StepRefusal(
            step_index=step_index, op=step.op, column=refused.column, reason=refused.reason
        )
    return None


def validate_recipe(columns: list[PlannedColumn], recipe: Recipe) -> RecipeValidation:
    """Walk a recipe, projecting the schema forward and checking each step against it.

    Checking stops at the first refusal. A later step would be checked against a
    schema nobody can know — the refused step never ran, so what it would have left
    behind is a guess — and a cascade of refusals caused by one mistake tells the
    reader less than the one that caused them.
    """
    started_with = {column.name for column in columns}

    for index, step in enumerate(recipe.steps):
        refusal = validate_step(columns, step, index)
        if refusal is not None:
            return RecipeValidation(
                columns=columns,
                accepted=index,
                refusal=note_removal(refusal, columns, started_with),
            )
        columns = plan_schema(columns, step)

    if recipe.analyze is not None:
        # The analysis is checked against what the steps leave behind, which is the
        # only schema it could ever mean anything against.
        refusal = validate_analyze(columns, recipe.analyze, len(recipe.steps))
        if refusal is not None:
            return RecipeValidation(
                columns=columns,
                accepted=len(recipe.steps),
                refusal=note_removal(refusal, columns, started_with),
            )

    return RecipeValidation(columns=columns, accepted=len(recipe.steps), refusal=None)


def note_removal(
    refusal: StepRefusal, columns: list[PlannedColumn], started_with: set[str]
) -> StepRefusal:
    """Say so when the missing column is one an earlier step took away.

    "There is no column named revenue" is confusing in a file that plainly has one.
    Naming the earlier step as the cause is the difference between a refusal the
    reader can act on and one that reads like a bug.
    """
    if refusal.column is None or refusal.column not in started_with:
        return refusal
    if find_column(columns, refusal.column) is not None:
        return refusal
    return refusal.model_copy(
        update={"reason": f"{refusal.reason} An earlier step removed it."}
    )
