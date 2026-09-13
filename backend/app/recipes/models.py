from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.analysis.models import (
    CategoricalSummary,
    CorrelationPair,
    GroupComparison,
    NumericSummary,
    Timeline,
)
from app.profiling.models import ColumnType
from app.profiling.preview import DatasetPreview
from app.visualization.models import ChartSpec

MAX_RECIPE_STEPS = 20
MAX_GROUP_COLUMNS = 2
MAX_ROW_LIMIT = 100_000
MAX_BIN_COUNT = 20
MAX_MAPPING_SIZE = 200


class PlannedColumn(BaseModel):
    """A column as it will exist at one point in a recipe, before anything has run.

    It carries only what a later step is validated against: the semantic type, and
    the two flags that decide whether a column may be grouped on. The counts and
    ratios of `ColumnSchema` describe data, and no projection can know them without
    executing, so no step is ever validated against them.

    The two flags are the uploaded file's judgement carried forward rather than a
    prediction. Filtering rows can only lower a column's cardinality, so a flag that
    has gone stale refuses a step that would in fact have worked — it never permits
    one that would not. That is the safe direction, and the reader is told why.
    """

    name: str
    inferred_type: ColumnType
    is_probable_id: bool = False
    is_high_cardinality: bool = False


FilterOperator = Literal[
    "eq",
    "ne",
    "lt",
    "lte",
    "gt",
    "gte",
    "contains",
    "in",
    "not_in",
    "is_missing",
    "not_missing",
]

# A literal written by the reader, before it is coerced to its column's type. Bool
# leads the union so that `true` stays a boolean instead of becoming 1.0.
Scalar = bool | float | str


class FilterClause(BaseModel):
    column: str
    operator: FilterOperator
    # Absent for the two missingness operators, a list for `in` and `not_in`, and a
    # single literal otherwise. Which of the three is required is the validator's
    # business, not the parser's.
    value: Scalar | list[Scalar] | None = None


class SelectColumns(BaseModel):
    op: Literal["select_columns"] = "select_columns"
    columns: list[str] = Field(min_length=1)


class DropColumns(BaseModel):
    op: Literal["drop_columns"] = "drop_columns"
    columns: list[str] = Field(min_length=1)


class FilterRows(BaseModel):
    op: Literal["filter_rows"] = "filter_rows"
    clauses: list[FilterClause] = Field(min_length=1)
    combine: Literal["and", "or"] = "and"


class SortRows(BaseModel):
    op: Literal["sort_rows"] = "sort_rows"
    columns: list[str] = Field(min_length=1)
    order: Literal["asc", "desc"] = "asc"


class LimitRows(BaseModel):
    op: Literal["limit_rows"] = "limit_rows"
    count: int = Field(ge=1, le=MAX_ROW_LIMIT)
    method: Literal["head", "sample"] = "head"
    # A sample that cannot be reproduced is not a recipe, so the seed is part of the
    # step rather than left to the executor.
    seed: int = 0


class DropMissing(BaseModel):
    op: Literal["drop_missing"] = "drop_missing"
    # Empty means every column.
    columns: list[str] = Field(default_factory=list)
    how: Literal["any", "all"] = "any"


class FillMissing(BaseModel):
    op: Literal["fill_missing"] = "fill_missing"
    column: str
    method: Literal["median", "mean", "mode", "constant", "forward"]
    value: Scalar | None = None


class DropDuplicates(BaseModel):
    op: Literal["drop_duplicates"] = "drop_duplicates"
    # Empty means every column.
    columns: list[str] = Field(default_factory=list)


class RenameColumn(BaseModel):
    op: Literal["rename_column"] = "rename_column"
    column: str
    to: str


class CastColumn(BaseModel):
    op: Literal["cast_column"] = "cast_column"
    column: str
    to: Literal["numeric", "datetime", "categorical", "text"]


class ColumnOperand(BaseModel):
    kind: Literal["column"] = "column"
    name: str


class ConstantOperand(BaseModel):
    kind: Literal["constant"] = "constant"
    value: float


# Whether an operand is a column or a number is declared, never inferred from how it
# looks. A file is allowed to have a column named "1000".
Operand = Annotated[ColumnOperand | ConstantOperand, Field(discriminator="kind")]


class ArithmeticExpression(BaseModel):
    kind: Literal["arithmetic"] = "arithmetic"
    left: Operand
    operator: Literal["add", "subtract", "multiply", "divide"]
    right: Operand


class BinExpression(BaseModel):
    kind: Literal["bin"] = "bin"
    column: str
    # Exactly one of the two: explicit cut points, or that many equal-sized buckets.
    edges: list[float] = Field(default_factory=list)
    quantiles: int | None = None
    labels: list[str] = Field(default_factory=list)


class DatetimePartExpression(BaseModel):
    kind: Literal["datetime_part"] = "datetime_part"
    column: str
    part: Literal["year", "quarter", "month", "week", "weekday", "date", "hour"]


class MapValuesExpression(BaseModel):
    kind: Literal["map_values"] = "map_values"
    column: str
    mapping: dict[str, str] = Field(default_factory=dict, max_length=MAX_MAPPING_SIZE)
    # None leaves anything unmapped as it was.
    default: str | None = None


Expression = Annotated[
    ArithmeticExpression | BinExpression | DatetimePartExpression | MapValuesExpression,
    Field(discriminator="kind"),
]


class DeriveColumn(BaseModel):
    op: Literal["derive_column"] = "derive_column"
    name: str
    expression: Expression


AggregateFunction = Literal["sum", "mean", "median", "count", "min", "max"]


class Aggregation(BaseModel):
    function: AggregateFunction
    # Only `count` may leave this out, in which case it counts rows.
    column: str | None = None
    name: str | None = None


class Aggregate(BaseModel):
    """Group rows and summarise them.

    This is a transform and not an analysis because what it returns is a table. That
    is what lets `sort_rows` and `limit_rows` follow it to answer "the top three",
    and `filter_rows` follow it as a HAVING clause, without any of the three needing
    a second meaning.
    """

    op: Literal["aggregate"] = "aggregate"
    # Empty means summarise the whole table into one row.
    group_by: list[str] = Field(default_factory=list)
    aggregations: list[Aggregation] = Field(min_length=1)


TransformStep = Annotated[
    SelectColumns
    | DropColumns
    | FilterRows
    | SortRows
    | LimitRows
    | DropMissing
    | FillMissing
    | DropDuplicates
    | RenameColumn
    | CastColumn
    | DeriveColumn
    | Aggregate,
    Field(discriminator="op"),
]


class Compare(BaseModel):
    """Does this number differ across these groups?"""

    op: Literal["compare"] = "compare"
    group_by: str
    measure: str


class Relate(BaseModel):
    """Do these two numbers move together?"""

    op: Literal["relate"] = "relate"
    left: str
    right: str


class Trend(BaseModel):
    """How has this number moved over time?"""

    op: Literal["trend"] = "trend"
    time: str
    measure: str


class Distribution(BaseModel):
    """What does this column's spread look like?"""

    op: Literal["distribution"] = "distribution"
    column: str


AnalyzeStep = Annotated[
    Compare | Relate | Trend | Distribution,
    Field(discriminator="op"),
]


class Recipe(BaseModel):
    """What the reader built, in the order they built it.

    At most one analysis, and it comes after every step above it. It answers with a
    statistical result rather than a table, which is the whole reason nothing can
    follow it: there are no columns left for a later step to name.
    """

    steps: list[TransformStep] = Field(default_factory=list, max_length=MAX_RECIPE_STEPS)
    analyze: AnalyzeStep | None = None


class StepRefusal(BaseModel):
    """Why one step cannot be applied.

    A refusal is a normal response and not an error: the recipe survives it, the
    reader is told which step and which column, and everything before it still ran.
    """

    step_index: int
    op: str
    column: str | None
    reason: str


class StepReport(BaseModel):
    """What one step did, for a reader watching the row count move."""

    step_index: int
    op: str
    rows_in: int
    rows_out: int
    # Anything the step had to do that the reader did not ask for and should know
    # about: rows left out of a grouping, values that would not divide.
    note: str | None = None


class RecipeValidation(BaseModel):
    # The schema as it stands after the last accepted step. Steps after a refusal
    # would be checked against a schema nobody can know, so checking stops there.
    columns: list[PlannedColumn]
    accepted: int
    refusal: StepRefusal | None = None


class RecipeAnalysis(BaseModel):
    """What a recipe's terminal step found, and the chart that shows it.

    Exactly one of the five results is filled, decided by `op`. They are the models
    the analysis layer already produces, unchanged — which is what lets the chart
    layer draw them without knowing a recipe was involved.
    """

    op: str
    columns: list[str]
    chart: ChartSpec | None = None
    comparison: GroupComparison | None = None
    correlation: CorrelationPair | None = None
    timeline: Timeline | None = None
    numeric: NumericSummary | None = None
    categorical: CategoricalSummary | None = None


class RecipePreview(BaseModel):
    """What a recipe would produce, without producing it.

    `columns` is the projected schema rather than the preview's column names: it is
    what the interface builds its menus from, and it describes columns that exist
    only because a step in this recipe invents them.
    """

    dataset_id: str
    source_rows: int
    columns: list[PlannedColumn]
    preview: DatasetPreview
    reports: list[StepReport]
    analysis: RecipeAnalysis | None
    refusal: StepRefusal | None

