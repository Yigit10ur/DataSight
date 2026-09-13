from app.profiling.models import ColumnSchema, ColumnType
from app.recipes.models import (
    Aggregate,
    Aggregation,
    ArithmeticExpression,
    BinExpression,
    CastColumn,
    DatetimePartExpression,
    DeriveColumn,
    DropColumns,
    MapValuesExpression,
    PlannedColumn,
    RenameColumn,
    SelectColumns,
    TransformStep,
)

# What `derive_column` produces, by construction rather than by inference. The
# executor is held to these: datetime parts are written as strings because a year is
# a label to group by and not a measurement to average, and a bin is its label.
DERIVED_TYPES: dict[str, ColumnType] = {
    "arithmetic": "numeric",
    "bin": "categorical",
    "datetime_part": "categorical",
    "map_values": "categorical",
}


def planned_columns(schemas: list[ColumnSchema]) -> list[PlannedColumn]:
    """Read the uploaded profile down to what a recipe is validated against."""
    return [
        PlannedColumn(
            name=schema.name,
            inferred_type=schema.inferred_type,
            is_probable_id=schema.is_probable_id,
            is_high_cardinality=schema.is_high_cardinality,
        )
        for schema in schemas
    ]


def aggregation_name(aggregation: Aggregation) -> str:
    """The column an aggregation writes into."""
    if aggregation.name:
        return aggregation.name
    if aggregation.column is None:
        return "row_count"
    return f"{aggregation.function}_{aggregation.column}"


def find_column(columns: list[PlannedColumn], name: str) -> PlannedColumn | None:
    """Look a column up by exact name.

    Exact, never fuzzy: a name that is nearly right is a question about a column the
    file does not have, and answering it with a neighbour is the kind of guess this
    layer exists to avoid.
    """
    for column in columns:
        if column.name == name:
            return column
    return None


def _settled_flags(column: PlannedColumn, inferred_type: ColumnType) -> PlannedColumn:
    """Carry a column's flags through a type change, dropping the ones that stop applying.

    The profiler never calls a datetime or a boolean an identifier, and only ever
    calls a categorical or text column high-cardinality. A cast that leaves a flag
    behind would be claiming something the profiler itself would not claim.
    """
    return PlannedColumn(
        name=column.name,
        inferred_type=inferred_type,
        is_probable_id=(
            column.is_probable_id and inferred_type not in {"boolean", "empty", "datetime"}
        ),
        is_high_cardinality=(
            column.is_high_cardinality and inferred_type in {"categorical", "text"}
        ),
    )


def _renamed(column: PlannedColumn, name: str) -> PlannedColumn:
    return column.model_copy(update={"name": name})


def _after_aggregate(columns: list[PlannedColumn], step: Aggregate) -> list[PlannedColumn]:
    grouped = []
    for name in step.group_by:
        column = find_column(columns, name)
        if column is None:  # pragma: no cover - validation runs first
            continue
        # The group keys survive with their type but without their flags. Grouping by
        # one column makes it unique, which is what re-profiling would read as an
        # identifier; refusing the reader's next step over a column they chose to
        # group by would be the flag working against them.
        grouped.append(
            PlannedColumn(name=column.name, inferred_type=column.inferred_type)
        )

    measured = [
        PlannedColumn(name=aggregation_name(aggregation), inferred_type="numeric")
        for aggregation in step.aggregations
    ]
    return grouped + measured


def plan_schema(columns: list[PlannedColumn], step: TransformStep) -> list[PlannedColumn]:
    """Say what the columns look like after a step, without running it.

    This is what makes a recipe checkable at all. Step six may sort by a column that
    step four invented and step one never had, so no step can be validated against
    the uploaded profile — only against the schema as it stands at that point. The
    same projection drives the interface: a column menu built from it cannot offer an
    operation on a column that will not be there.

    Only the names, their order and their types are predicted. The step is assumed to
    have been validated already.
    """
    match step:
        case SelectColumns():
            # In the order the reader asked for, which is the order they will see.
            kept = [find_column(columns, name) for name in step.columns]
            return [column for column in kept if column is not None]

        case DropColumns():
            dropped = set(step.columns)
            return [column for column in columns if column.name not in dropped]

        case RenameColumn():
            return [
                _renamed(column, step.to) if column.name == step.column else column
                for column in columns
            ]

        case CastColumn():
            return [
                _settled_flags(column, step.to) if column.name == step.column else column
                for column in columns
            ]

        case DeriveColumn():
            return [*columns, PlannedColumn(name=step.name, inferred_type=_derived_type(step))]

        case Aggregate():
            return _after_aggregate(columns, step)

    # Filtering, sorting, limiting, filling and de-duplicating change which rows are
    # there and what is in them, never which columns exist or what they hold.
    return list(columns)


def _derived_type(step: DeriveColumn) -> ColumnType:
    expression = step.expression
    if isinstance(expression, DatetimePartExpression) and expression.part == "date":
        # Every other part is a label. A date is still a date.
        return "datetime"
    match expression:
        case (
            ArithmeticExpression()
            | BinExpression()
            | DatetimePartExpression()
            | MapValuesExpression()
        ):
            return DERIVED_TYPES[expression.kind]
    raise ValueError(f"Unknown expression kind: {expression}")  # pragma: no cover


def plan_recipe_schema(
    columns: list[PlannedColumn], steps: list[TransformStep]
) -> list[PlannedColumn]:
    """Walk a whole recipe's projection, assuming every step has been validated."""
    for step in steps:
        columns = plan_schema(columns, step)
    return columns
