import pandas as pd

from app.profiling import profile_dataset
from app.recipes import (
    Aggregate,
    Aggregation,
    ArithmeticExpression,
    BinExpression,
    CastColumn,
    ColumnOperand,
    ConstantOperand,
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
    PlannedColumn,
    RenameColumn,
    SelectColumns,
    SortRows,
    aggregation_name,
    plan_recipe_schema,
    plan_schema,
    planned_columns,
)


def columns() -> list[PlannedColumn]:
    return [
        PlannedColumn(name="customer_id", inferred_type="categorical", is_probable_id=True),
        PlannedColumn(name="city", inferred_type="categorical"),
        PlannedColumn(name="revenue", inferred_type="numeric"),
        PlannedColumn(name="cost", inferred_type="numeric"),
        PlannedColumn(name="order_date", inferred_type="datetime"),
        PlannedColumn(name="note", inferred_type="text", is_high_cardinality=True),
    ]


def names(planned: list[PlannedColumn]) -> list[str]:
    return [column.name for column in planned]


def typed(planned: list[PlannedColumn]) -> dict[str, str]:
    return {column.name: column.inferred_type for column in planned}


def test_planned_columns_reads_a_profile_down_to_what_validation_needs():
    frame = pd.DataFrame(
        {
            "customer_id": ["a", "b", "c", "d"],
            "city": ["Ankara", "Izmir", "Ankara", "Izmir"],
            "revenue": [10.0, 20.0, 30.0, 40.0],
        }
    )
    planned = planned_columns(profile_dataset("abc", "sales.csv", frame).column_schemas)

    assert names(planned) == ["customer_id", "city", "revenue"]
    assert typed(planned)["revenue"] == "numeric"
    assert next(column for column in planned if column.name == "customer_id").is_probable_id


def test_select_keeps_the_order_the_reader_asked_for():
    after = plan_schema(columns(), SelectColumns(columns=["revenue", "city"]))
    assert names(after) == ["revenue", "city"]


def test_drop_removes_the_named_columns():
    after = plan_schema(columns(), DropColumns(columns=["note", "customer_id"]))
    assert names(after) == ["city", "revenue", "cost", "order_date"]


def test_rename_keeps_position_and_type():
    after = plan_schema(columns(), RenameColumn(column="revenue", to="turnover"))
    assert names(after) == ["customer_id", "city", "turnover", "cost", "order_date", "note"]
    assert typed(after)["turnover"] == "numeric"


def test_cast_changes_the_type():
    after = plan_schema(columns(), CastColumn(column="revenue", to="categorical"))
    assert typed(after)["revenue"] == "categorical"


def test_cast_drops_flags_that_stop_applying():
    after = plan_schema(columns(), CastColumn(column="customer_id", to="datetime"))
    identifier = next(column for column in after if column.name == "customer_id")
    # The profiler never calls a datetime an identifier, so neither may the projection.
    assert not identifier.is_probable_id

    after = plan_schema(columns(), CastColumn(column="note", to="numeric"))
    note = next(column for column in after if column.name == "note")
    assert not note.is_high_cardinality


def test_arithmetic_derives_a_numeric_column():
    step = DeriveColumn(
        name="margin",
        expression=ArithmeticExpression(
            left=ColumnOperand(name="revenue"),
            operator="subtract",
            right=ColumnOperand(name="cost"),
        ),
    )
    after = plan_schema(columns(), step)

    assert names(after)[-1] == "margin"
    assert typed(after)["margin"] == "numeric"


def test_bins_datetime_parts_and_mappings_all_derive_categories():
    steps = [
        DeriveColumn(
            name="band", expression=BinExpression(column="revenue", quantiles=4)
        ),
        DeriveColumn(
            name="year", expression=DatetimePartExpression(column="order_date", part="year")
        ),
        DeriveColumn(
            name="region", expression=MapValuesExpression(column="city", mapping={"Ankara": "TR"})
        ),
    ]
    after = plan_recipe_schema(columns(), steps)

    assert typed(after)["band"] == "categorical"
    # A year is a label to group by, not a measurement to average, so it is written
    # as a category rather than as a number.
    assert typed(after)["year"] == "categorical"
    assert typed(after)["region"] == "categorical"


def test_aggregate_replaces_the_schema_with_its_groups_and_measures():
    step = Aggregate(
        group_by=["city"],
        aggregations=[
            Aggregation(function="sum", column="revenue"),
            Aggregation(function="count"),
        ],
    )
    after = plan_schema(columns(), step)

    assert names(after) == ["city", "sum_revenue", "row_count"]
    assert typed(after)["sum_revenue"] == "numeric"
    assert typed(after)["row_count"] == "numeric"
    assert typed(after)["city"] == "categorical"


def test_aggregate_without_groups_keeps_only_its_measures():
    step = Aggregate(aggregations=[Aggregation(function="mean", column="revenue", name="average")])
    assert names(plan_schema(columns(), step)) == ["average"]


def test_aggregation_names_itself_after_what_it_did():
    assert aggregation_name(Aggregation(function="sum", column="revenue")) == "sum_revenue"
    assert aggregation_name(Aggregation(function="count")) == "row_count"
    named = Aggregation(function="count", column="city", name="orders")
    assert aggregation_name(named) == "orders"


def test_row_steps_leave_the_columns_alone():
    unchanged = [
        FilterRows(clauses=[FilterClause(column="revenue", operator="gt", value=1000)]),
        SortRows(columns=["revenue"], order="desc"),
        LimitRows(count=10),
        DropMissing(columns=["revenue"]),
        DropDuplicates(),
        FillMissing(column="cost", method="median"),
    ]
    for step in unchanged:
        assert plan_schema(columns(), step) == columns()


def test_a_chain_projects_through_columns_the_file_never_had():
    steps = [
        SelectColumns(columns=["city", "revenue", "cost"]),
        DeriveColumn(
            name="margin",
            expression=ArithmeticExpression(
                left=ColumnOperand(name="revenue"),
                operator="subtract",
                right=ColumnOperand(name="cost"),
            ),
        ),
        DeriveColumn(
            name="margin_per_mille",
            expression=ArithmeticExpression(
                left=ColumnOperand(name="margin"),
                operator="divide",
                right=ConstantOperand(value=1000),
            ),
        ),
        Aggregate(
            group_by=["city"],
            aggregations=[Aggregation(function="sum", column="margin_per_mille")],
        ),
        SortRows(columns=["sum_margin_per_mille"], order="desc"),
        LimitRows(count=3),
    ]
    after = plan_recipe_schema(columns(), steps)

    assert names(after) == ["city", "sum_margin_per_mille"]
