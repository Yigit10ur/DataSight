from pathlib import Path

import app.recipes as recipes_package
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
    FillMissing,
    FilterClause,
    FilterRows,
    LimitRows,
    MapValuesExpression,
    PlannedColumn,
    Recipe,
    RenameColumn,
    SelectColumns,
    SortRows,
    validate_recipe,
    validate_step,
)


def columns() -> list[PlannedColumn]:
    return [
        PlannedColumn(name="customer_id", inferred_type="categorical", is_probable_id=True),
        PlannedColumn(name="city", inferred_type="categorical"),
        PlannedColumn(name="revenue", inferred_type="numeric"),
        PlannedColumn(name="cost", inferred_type="numeric"),
        PlannedColumn(name="order_date", inferred_type="datetime"),
        PlannedColumn(name="returned", inferred_type="boolean"),
        PlannedColumn(name="sku", inferred_type="categorical", is_high_cardinality=True),
        PlannedColumn(name="note", inferred_type="text", is_high_cardinality=True),
        PlannedColumn(name="blank", inferred_type="empty"),
    ]


def refuse(step) -> str:
    """Run one step against the standing schema and return why it was refused."""
    refusal = validate_step(columns(), step)
    assert refusal is not None, f"{step.op} was accepted when it should not have been"
    return refusal.reason


def accept(step) -> None:
    assert validate_step(columns(), step) is None


def test_a_column_the_file_does_not_have_is_refused_by_name():
    assert '"profit"' in refuse(SortRows(columns=["profit"]))


def test_a_column_an_earlier_step_removed_says_so():
    recipe = Recipe(steps=[DropColumns(columns=["revenue"]), SortRows(columns=["revenue"])])
    result = validate_recipe(columns(), recipe)

    assert result.accepted == 1
    assert result.refusal is not None
    assert result.refusal.step_index == 1
    assert "An earlier step removed it." in result.refusal.reason


def test_a_column_an_earlier_step_created_is_accepted():
    recipe = Recipe(
        steps=[
            DeriveColumn(
                name="margin",
                expression=ArithmeticExpression(
                    left=ColumnOperand(name="revenue"),
                    operator="subtract",
                    right=ColumnOperand(name="cost"),
                ),
            ),
            SortRows(columns=["margin"], order="desc"),
            LimitRows(count=5),
        ]
    )
    result = validate_recipe(columns(), recipe)

    assert result.refusal is None
    assert result.accepted == 3


def test_checking_stops_at_the_first_refusal():
    recipe = Recipe(
        steps=[
            SelectColumns(columns=["city", "revenue"]),
            SortRows(columns=["nowhere"]),
            SortRows(columns=["also_nowhere"]),
        ]
    )
    result = validate_recipe(columns(), recipe)

    assert result.accepted == 1
    assert result.refusal is not None
    assert result.refusal.step_index == 1
    # The schema handed back is the one the accepted steps left behind.
    assert [column.name for column in result.columns] == ["city", "revenue"]


def test_naming_the_same_column_twice_is_refused():
    assert "twice" in refuse(SelectColumns(columns=["city", "city"]))


def test_removing_every_column_is_refused():
    every = [column.name for column in columns()]
    assert "nothing to work with" in refuse(DropColumns(columns=every))


def test_ordering_a_category_is_refused():
    reason = refuse(FilterRows(clauses=[FilterClause(column="city", operator="gt", value="A")]))
    assert "cannot be ordered" in reason


def test_searching_a_number_for_text_is_refused():
    reason = refuse(
        FilterRows(clauses=[FilterClause(column="revenue", operator="contains", value="9")])
    )
    assert "no text to search" in reason


def test_a_filter_value_that_will_not_coerce_is_refused_not_compared_loosely():
    reason = refuse(
        FilterRows(clauses=[FilterClause(column="revenue", operator="gt", value="a thousand")])
    )
    assert "cannot be read as a value" in reason


def test_a_number_is_not_accepted_as_a_date():
    # pandas would read 1000 as a moment in 1970. That is never what the reader meant.
    reason = refuse(
        FilterRows(clauses=[FilterClause(column="order_date", operator="gte", value=1000)])
    )
    assert "cannot be read as a value" in reason
    accept(
        FilterRows(clauses=[FilterClause(column="order_date", operator="gte", value="2024-01-01")])
    )


def test_membership_needs_a_list_and_ordinary_comparison_needs_one_value():
    assert "list of values" in refuse(
        FilterRows(clauses=[FilterClause(column="city", operator="in", value="Ankara")])
    )
    assert "single value" in refuse(
        FilterRows(clauses=[FilterClause(column="city", operator="eq", value=["Ankara"])])
    )
    accept(
        FilterRows(
            clauses=[FilterClause(column="city", operator="in", value=["Ankara", "Izmir"])]
        )
    )


def test_every_value_in_a_list_has_to_coerce():
    reason = refuse(
        FilterRows(clauses=[FilterClause(column="revenue", operator="in", value=[10, "high"])])
    )
    assert '"high"' in reason


def test_an_empty_column_can_only_be_filtered_on_whether_it_is_missing():
    assert "nothing to compare" in refuse(
        FilterRows(clauses=[FilterClause(column="blank", operator="eq", value="x")])
    )
    accept(FilterRows(clauses=[FilterClause(column="blank", operator="is_missing")]))


def test_a_true_false_column_accepts_the_words_it_was_read_from():
    accept(FilterRows(clauses=[FilterClause(column="returned", operator="eq", value=True)]))
    accept(FilterRows(clauses=[FilterClause(column="returned", operator="eq", value="yes")]))
    assert "cannot be read" in refuse(
        FilterRows(clauses=[FilterClause(column="returned", operator="eq", value="maybe")])
    )


def test_filling_text_with_a_median_is_refused_and_names_what_would_work():
    reason = refuse(FillMissing(column="note", method="median"))
    assert "has no median" in reason
    assert "most frequent value" in reason


def test_filling_with_a_constant_needs_a_value_of_the_right_type():
    assert "needs a value" in refuse(FillMissing(column="revenue", method="constant"))
    assert "cannot be read as a value" in refuse(
        FillMissing(column="revenue", method="constant", value="none at all")
    )
    accept(FillMissing(column="revenue", method="constant", value=0))


def test_an_empty_column_can_only_be_filled_with_a_constant():
    assert "no value to carry" in refuse(FillMissing(column="blank", method="mode"))
    accept(FillMissing(column="blank", method="constant", value="unknown"))


def test_renaming_onto_an_existing_name_is_refused():
    assert "already a column" in refuse(RenameColumn(column="revenue", to="cost"))
    assert "already called that" in refuse(RenameColumn(column="revenue", to="revenue"))
    accept(RenameColumn(column="revenue", to="turnover"))


def test_converting_an_empty_column_is_refused():
    assert "no values to convert" in refuse(CastColumn(column="blank", to="numeric"))


def test_a_derived_name_cannot_collide():
    step = DeriveColumn(
        name="cost",
        expression=ArithmeticExpression(
            left=ColumnOperand(name="revenue"), operator="add", right=ConstantOperand(value=1)
        ),
    )
    assert "already a column" in refuse(step)


def test_arithmetic_on_a_category_is_refused():
    step = DeriveColumn(
        name="odd",
        expression=ArithmeticExpression(
            left=ColumnOperand(name="city"), operator="add", right=ConstantOperand(value=1)
        ),
    )
    assert "cannot be used in arithmetic" in refuse(step)


def test_dividing_by_a_constant_zero_is_refused():
    step = DeriveColumn(
        name="ratio",
        expression=ArithmeticExpression(
            left=ColumnOperand(name="revenue"), operator="divide", right=ConstantOperand(value=0)
        ),
    )
    assert "Dividing by zero" in refuse(step)


def test_binning_needs_a_number_column_and_one_way_of_cutting_it():
    assert "only numbers can be binned" in refuse(
        DeriveColumn(name="band", expression=BinExpression(column="city", quantiles=4))
    )
    assert "not both" in refuse(
        DeriveColumn(
            name="band", expression=BinExpression(column="revenue", edges=[0, 10], quantiles=4)
        )
    )
    assert "not both" in refuse(
        DeriveColumn(name="band", expression=BinExpression(column="revenue"))
    )


def test_cut_points_have_to_increase_and_labels_have_to_match():
    assert "have to increase" in refuse(
        DeriveColumn(name="band", expression=BinExpression(column="revenue", edges=[0, 100, 50]))
    )
    assert "2 bins but 3 labels" in refuse(
        DeriveColumn(
            name="band",
            expression=BinExpression(
                column="revenue", edges=[0, 50, 100], labels=["low", "mid", "high"]
            ),
        )
    )
    accept(
        DeriveColumn(
            name="band",
            expression=BinExpression(column="revenue", edges=[0, 50, 100], labels=["low", "high"]),
        )
    )


def test_reading_a_date_part_off_something_that_is_not_a_date_is_refused():
    step = DeriveColumn(
        name="year", expression=DatetimePartExpression(column="revenue", part="year")
    )
    assert "no year to read" in refuse(step)


def test_remapping_a_number_is_refused():
    step = DeriveColumn(
        name="region", expression=MapValuesExpression(column="revenue", mapping={"1": "one"})
    )
    assert "only categories can be remapped" in refuse(step)


def test_grouping_by_an_identifier_is_refused():
    step = Aggregate(
        group_by=["customer_id"], aggregations=[Aggregation(function="sum", column="revenue")]
    )
    assert "row identifier" in refuse(step)


def test_grouping_by_too_many_distinct_values_is_refused():
    step = Aggregate(group_by=["sku"], aggregations=[Aggregation(function="count")])
    assert "too many distinct values" in refuse(step)


def test_grouping_by_a_number_is_refused_and_names_the_way_round_it():
    step = Aggregate(group_by=["revenue"], aggregations=[Aggregation(function="count")])
    reason = refuse(step)
    assert "cannot be grouped on" in reason
    assert "Bin it into ranges" in reason


def test_grouping_by_more_than_two_columns_is_refused():
    step = Aggregate(
        group_by=["city", "returned", "order_date"],
        aggregations=[Aggregation(function="count")],
    )
    assert "more than 2 columns" in refuse(step)


def test_summing_text_is_refused_and_counting_it_is_not():
    step = Aggregate(group_by=["city"], aggregations=[Aggregation(function="sum", column="note")])
    assert "there is no sum of it" in refuse(step)
    accept(
        Aggregate(
            group_by=["city"], aggregations=[Aggregation(function="count", column="note")]
        )
    )


def test_two_results_cannot_share_a_name():
    step = Aggregate(
        group_by=["city"],
        aggregations=[
            Aggregation(function="sum", column="revenue"),
            Aggregation(function="mean", column="cost", name="sum_revenue"),
        ],
    )
    assert "would both be called" in refuse(step)

    assert "would both be called" in refuse(
        Aggregate(
            group_by=["city"],
            aggregations=[Aggregation(function="count", name="city")],
        )
    )


def test_a_whole_recipe_that_makes_sense_is_accepted():
    recipe = Recipe(
        steps=[
            SelectColumns(columns=["city", "revenue", "cost", "order_date"]),
            FilterRows(clauses=[FilterClause(column="revenue", operator="gt", value=1000)]),
            FillMissing(column="cost", method="median"),
            DeriveColumn(
                name="margin",
                expression=ArithmeticExpression(
                    left=ColumnOperand(name="revenue"),
                    operator="subtract",
                    right=ColumnOperand(name="cost"),
                ),
            ),
            Aggregate(
                group_by=["city"], aggregations=[Aggregation(function="sum", column="margin")]
            ),
            FilterRows(clauses=[FilterClause(column="sum_margin", operator="gt", value=0)]),
            SortRows(columns=["sum_margin"], order="desc"),
            LimitRows(count=10),
        ]
    )
    result = validate_recipe(columns(), recipe)

    assert result.refusal is None
    assert result.accepted == 8
    assert [column.name for column in result.columns] == ["city", "sum_margin"]


def test_no_step_can_reach_an_interpreter():
    """Nothing a reader writes is ever executed as code.

    The whole argument for a closed vocabulary is that a column name is looked up and
    an operation is dispatched, never evaluated. This reads the source rather than
    trusting that it stayed that way, and it covers every file a recipe passes
    through on its way in from a request — not only the package that defines it.
    """
    forbidden = ("eval(", "exec(", ".query(", "getattr(", "__import__", "compile(")
    package = Path(recipes_package.__file__).parent
    backend = package.parent.parent
    reached = [
        *sorted(package.glob("*.py")),
        backend / "app" / "store.py",
        backend / "app" / "api" / "routes.py",
    ]

    for path in reached:
        source = path.read_text()
        for construct in forbidden:
            assert construct not in source, f"{path.name} reaches for {construct}"
