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
    Recipe,
    RenameColumn,
    SelectColumns,
    SortRows,
    planned_columns,
    run_recipe,
)


def orders() -> pd.DataFrame:
    """A file with one of everything: gaps, dates as text, labels and free text."""
    return pd.DataFrame(
        {
            "customer_id": [f"c{index:03d}" for index in range(40)],
            "city": ["Ankara", "Izmir", "Bursa", "Izmir"] * 10,
            "revenue": [100.0 + index * 37 for index in range(39)] + [None],
            "cost": [50.0 + index * 11 for index in range(40)],
            "order_date": pd.date_range("2024-01-01", periods=40, freq="9D").strftime("%Y-%m-%d"),
            "returned": ["yes", "no", "no", "no"] * 10,
            "note": [
                f"A reasonably long free-text remark about order {index}" for index in range(40)
            ],
        }
    )


def starting_columns(frame: pd.DataFrame) -> list[PlannedColumn]:
    return planned_columns(profile_dataset("start", "orders.csv", frame).column_schemas)


def run(frame: pd.DataFrame, *steps):
    return run_recipe(frame, starting_columns(frame), Recipe(steps=list(steps)))


def every_step() -> dict[str, object]:
    """One of each step, chosen to leave rows behind so the result is profilable."""
    return {
        "select_columns": SelectColumns(columns=["revenue", "city"]),
        "drop_columns": DropColumns(columns=["note"]),
        "filter_rows": FilterRows(
            clauses=[FilterClause(column="revenue", operator="gt", value=200)]
        ),
        "sort_rows": SortRows(columns=["revenue"], order="desc"),
        "limit_rows": LimitRows(count=20),
        "limit_rows_sample": LimitRows(count=20, method="sample", seed=7),
        "drop_missing": DropMissing(columns=["revenue"]),
        "fill_missing_median": FillMissing(column="revenue", method="median"),
        "fill_missing_mode": FillMissing(column="city", method="mode"),
        "fill_missing_constant": FillMissing(column="revenue", method="constant", value=0),
        "fill_missing_forward": FillMissing(column="revenue", method="forward"),
        "drop_duplicates": DropDuplicates(columns=["city"]),
        "rename_column": RenameColumn(column="revenue", to="turnover"),
        "cast_numeric": CastColumn(column="revenue", to="numeric"),
        "cast_datetime": CastColumn(column="order_date", to="datetime"),
        "cast_categorical": CastColumn(column="revenue", to="categorical"),
        "cast_categorical_from_text": CastColumn(column="note", to="categorical"),
        "cast_text": CastColumn(column="city", to="text"),
        "derive_arithmetic": DeriveColumn(
            name="margin",
            expression=ArithmeticExpression(
                left=ColumnOperand(name="revenue"),
                operator="subtract",
                right=ColumnOperand(name="cost"),
            ),
        ),
        "derive_divide": DeriveColumn(
            name="ratio",
            expression=ArithmeticExpression(
                left=ColumnOperand(name="revenue"),
                operator="divide",
                right=ConstantOperand(value=1000),
            ),
        ),
        "derive_bin_quantiles": DeriveColumn(
            name="band", expression=BinExpression(column="revenue", quantiles=4)
        ),
        "derive_bin_edges": DeriveColumn(
            name="band",
            expression=BinExpression(
                column="revenue", edges=[0, 500, 5000], labels=["low", "high"]
            ),
        ),
        "derive_year": DeriveColumn(
            name="year",
            expression=DatetimePartExpression(column="order_date", part="year"),
        ),
        "derive_quarter": DeriveColumn(
            name="quarter",
            expression=DatetimePartExpression(column="order_date", part="quarter"),
        ),
        "derive_month": DeriveColumn(
            name="month",
            expression=DatetimePartExpression(column="order_date", part="month"),
        ),
        "derive_week": DeriveColumn(
            name="week", expression=DatetimePartExpression(column="order_date", part="week")
        ),
        "derive_weekday": DeriveColumn(
            name="weekday",
            expression=DatetimePartExpression(column="order_date", part="weekday"),
        ),
        "derive_hour": DeriveColumn(
            name="hour", expression=DatetimePartExpression(column="order_date", part="hour")
        ),
        "derive_date": DeriveColumn(
            name="day", expression=DatetimePartExpression(column="order_date", part="date")
        ),
        "derive_map": DeriveColumn(
            name="region",
            expression=MapValuesExpression(
                column="city", mapping={"Ankara": "Central", "Izmir": "Aegean"}, default="Other"
            ),
        ),
        "aggregate": Aggregate(
            group_by=["city"],
            aggregations=[
                Aggregation(function="sum", column="revenue"),
                Aggregation(function="count"),
            ],
        ),
        "aggregate_two_groups": Aggregate(
            group_by=["city", "returned"],
            aggregations=[Aggregation(function="mean", column="cost")],
        ),
        "aggregate_whole_table": Aggregate(
            aggregations=[Aggregation(function="sum", column="revenue")]
        ),
    }


def test_projection_matches_what_profiling_finds():
    """The invariant the whole layer rests on.

    `plan_schema` decides what a reader may do next, and it decides it without
    running anything. If what it predicts is not what executing the step and then
    profiling the result produces, a recipe validated against one schema runs against
    another — the reader is offered columns that will not be there, or refused ones
    that will.

    Names, order and type are predicted exactly. The two flags are not: whether a
    column is near-unique or high-cardinality is a fact about data, and carrying the
    uploaded file's judgement forward is a stated choice rather than a prediction.
    """
    frame = orders()
    columns = starting_columns(frame)

    for label, step in every_step().items():
        result = run_recipe(frame, columns, Recipe(steps=[step]))
        assert result.refusal is None, f"{label}: {result.refusal}"
        assert not result.frame.empty, f"{label} left nothing to profile"

        profiled = planned_columns(
            profile_dataset("after", "derived.csv", result.frame).column_schemas
        )
        predicted = result.columns

        assert [column.name for column in predicted] == [column.name for column in profiled], label
        assert [column.inferred_type for column in predicted] == [
            column.inferred_type for column in profiled
        ], label


def test_a_recipe_leaves_the_uploaded_frame_alone():
    frame = orders()
    before = frame.copy()

    result = run(
        frame,
        FillMissing(column="revenue", method="median"),
        DeriveColumn(
            name="margin",
            expression=ArithmeticExpression(
                left=ColumnOperand(name="revenue"),
                operator="subtract",
                right=ColumnOperand(name="cost"),
            ),
        ),
        CastColumn(column="city", to="categorical"),
    )

    assert result.refusal is None
    pd.testing.assert_frame_equal(frame, before)


def test_the_same_recipe_twice_gives_the_same_frame():
    """Derived data is stored as its recipe, so re-running has to be re-deriving."""
    frame = orders()
    steps = [
        FilterRows(clauses=[FilterClause(column="revenue", operator="gt", value=300)]),
        LimitRows(count=10, method="sample", seed=3),
        SortRows(columns=["revenue"], order="desc"),
    ]

    first = run(frame, *steps)
    second = run(frame, *steps)

    assert first.refusal is None
    pd.testing.assert_frame_equal(first.frame, second.frame)


def test_a_row_with_no_value_answers_no_question_about_it():
    frame = orders()
    # Row 39 has no revenue. Pandas alone would call it "not 100" and keep it.
    clause = FilterClause(column="revenue", operator="ne", value=100)
    kept = run(frame, FilterRows(clauses=[clause]))
    assert kept.frame["revenue"].isna().sum() == 0

    for operator in ("eq", "gt", "lte"):
        compared = FilterClause(column="revenue", operator=operator, value=100)
        result = run(frame, FilterRows(clauses=[compared]))
        assert result.frame["revenue"].isna().sum() == 0, operator

    absent = FilterClause(column="revenue", operator="is_missing")
    missing = run(frame, FilterRows(clauses=[absent]))
    assert len(missing.frame) == 1


def test_contains_searches_for_characters_and_not_for_a_pattern():
    frame = pd.DataFrame({"label": ["order (TR)", "order TR", "order [x]", None]})
    result = run(
        frame,
        FilterRows(clauses=[FilterClause(column="label", operator="contains", value="(TR)")]),
    )

    assert list(result.frame["label"]) == ["order (TR)"]


def test_clauses_combine_the_way_the_step_says():
    frame = orders()
    clauses = [
        FilterClause(column="city", operator="eq", value="Ankara"),
        FilterClause(column="city", operator="eq", value="Bursa"),
    ]

    both = run(frame, FilterRows(clauses=clauses, combine="and"))
    either = run(frame, FilterRows(clauses=clauses, combine="or"))

    assert len(both.frame) == 0
    assert len(either.frame) == 20


def test_sorting_leaves_the_gaps_at_the_end():
    frame = orders()
    result = run(frame, SortRows(columns=["revenue"], order="desc"))

    assert pd.isna(result.frame["revenue"].iloc[-1])


def test_a_conversion_that_would_destroy_a_column_is_refused():
    frame = pd.DataFrame({"amount": ["10", "20", "thirty", "forty", "fifty"]})
    result = run(frame, CastColumn(column="amount", to="numeric"))

    assert result.refusal is not None
    assert "3 of 5 values" in result.refusal.reason
    # The frame is the one the accepted steps left behind: untouched, here.
    assert list(result.frame["amount"]) == ["10", "20", "thirty", "forty", "fifty"]


def test_a_conversion_that_loses_a_little_says_how_much():
    frame = pd.DataFrame({"amount": [str(value) for value in range(20)] + ["nope"]})
    result = run(frame, CastColumn(column="amount", to="numeric"))

    assert result.refusal is None
    assert result.reports[0].note == "1 values could not be read as numeric."


def test_dividing_by_a_zero_cell_leaves_a_gap_and_says_how_many():
    frame = pd.DataFrame({"revenue": [100.0, 200.0, 300.0], "units": [4.0, 0.0, 2.0]})
    result = run(
        frame,
        DeriveColumn(
            name="each",
            expression=ArithmeticExpression(
                left=ColumnOperand(name="revenue"),
                operator="divide",
                right=ColumnOperand(name="units"),
            ),
        ),
    )

    assert result.refusal is None
    assert list(result.frame["each"].isna()) == [False, True, False]
    assert result.reports[0].note == "1 rows had nothing to divide by."


def test_grouping_leaves_out_rows_with_no_group_and_says_so():
    frame = pd.DataFrame(
        {"city": ["Ankara", "Izmir", None, "Ankara"], "revenue": [10.0, 20.0, 30.0, 40.0]}
    )
    result = run(
        frame,
        Aggregate(group_by=["city"], aggregations=[Aggregation(function="sum", column="revenue")]),
    )

    assert len(result.frame) == 2
    assert result.reports[0].note == '1 rows had no "city" and were left out.'


def test_aggregating_the_whole_table_gives_one_row():
    frame = orders()
    result = run(
        frame,
        Aggregate(
            aggregations=[
                Aggregation(function="sum", column="revenue", name="total"),
                Aggregation(function="count", name="orders"),
            ]
        ),
    )

    assert list(result.frame.columns) == ["total", "orders"]
    assert len(result.frame) == 1
    assert result.frame["orders"].iloc[0] == 40


def test_buckets_a_column_cannot_be_split_into_are_refused():
    frame = pd.DataFrame({"score": [5.0] * 10})
    result = run(
        frame,
        DeriveColumn(
            name="band",
            expression=BinExpression(column="score", quantiles=4, labels=["a", "b", "c", "d"]),
        ),
    )

    assert result.refusal is not None
    assert "not have enough distinct values" in result.refusal.reason


def test_mapping_replaces_what_it_knows_and_keeps_the_rest():
    frame = pd.DataFrame({"city": ["Ankara", "Izmir", "Bursa", None]})

    kept = run(
        frame,
        DeriveColumn(
            name="region",
            expression=MapValuesExpression(column="city", mapping={"Ankara": "Central"}),
        ),
    )
    assert list(kept.frame["region"][:3]) == ["Central", "Izmir", "Bursa"]
    assert kept.frame["region"].isna().iloc[3]

    defaulted = run(
        frame,
        DeriveColumn(
            name="region",
            expression=MapValuesExpression(
                column="city", mapping={"Ankara": "Central"}, default="Other"
            ),
        ),
    )
    assert list(defaulted.frame["region"][:3]) == ["Central", "Other", "Other"]
    # A row with no city has no region either: a default replaces a value that was
    # there and is not in the mapping, never a value that was never written.
    assert defaulted.frame["region"].isna().iloc[3]


def test_every_part_of_a_date_is_a_label_except_the_date():
    frame = orders()
    result = run(
        frame,
        DeriveColumn(
            name="year", expression=DatetimePartExpression(column="order_date", part="year")
        ),
        DeriveColumn(
            name="quarter",
            expression=DatetimePartExpression(column="order_date", part="quarter"),
        ),
        DeriveColumn(
            name="day", expression=DatetimePartExpression(column="order_date", part="date")
        ),
    )

    assert result.frame["year"].iloc[0] == "2024"
    assert result.frame["quarter"].iloc[0] == "Q1"
    assert pd.api.types.is_datetime64_any_dtype(result.frame["day"])


def test_a_derived_date_can_be_filtered_as_one():
    frame = orders()
    result = run(
        frame,
        DeriveColumn(
            name="day", expression=DatetimePartExpression(column="order_date", part="date")
        ),
        FilterRows(clauses=[FilterClause(column="day", operator="gte", value="2024-06-01")]),
    )

    assert result.refusal is None
    assert result.frame["day"].min() >= pd.Timestamp("2024-06-01")


def test_each_step_reports_what_it_did_to_the_row_count():
    frame = orders()
    result = run(
        frame,
        FilterRows(clauses=[FilterClause(column="revenue", operator="gt", value=500)]),
        Aggregate(group_by=["city"], aggregations=[Aggregation(function="count")]),
    )

    counts = [(report.rows_in, report.rows_out) for report in result.reports]
    assert counts == [(40, 28), (28, 3)]


def test_a_refusal_keeps_what_the_accepted_steps_left():
    frame = orders()
    result = run(
        frame,
        SelectColumns(columns=["city", "revenue"]),
        SortRows(columns=["margin"]),
    )

    assert result.refusal is not None
    assert result.refusal.step_index == 1
    assert list(result.frame.columns) == ["city", "revenue"]
    assert len(result.reports) == 1


def test_the_top_three_is_three_steps_and_not_an_operation_of_its_own():
    """The composition the plan claims: rank is aggregate, then sort, then limit."""
    frame = orders()
    result = run(
        frame,
        Aggregate(
            group_by=["city"],
            aggregations=[Aggregation(function="sum", column="revenue")],
        ),
        SortRows(columns=["sum_revenue"], order="desc"),
        LimitRows(count=2),
    )

    assert result.refusal is None
    assert len(result.frame) == 2
    assert result.frame["sum_revenue"].is_monotonic_decreasing


def test_a_filter_after_an_aggregate_is_a_having_clause():
    frame = orders()
    result = run(
        frame,
        Aggregate(group_by=["city"], aggregations=[Aggregation(function="count")]),
        FilterRows(clauses=[FilterClause(column="row_count", operator="gt", value=15)]),
    )

    assert result.refusal is None
    assert list(result.frame["city"]) == ["Izmir"]
