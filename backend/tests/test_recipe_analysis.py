import pandas as pd

from app.profiling import profile_dataset
from app.recipes import (
    Aggregate,
    Aggregation,
    CastColumn,
    Compare,
    DatetimePartExpression,
    DeriveColumn,
    Distribution,
    FilterClause,
    FilterRows,
    PlannedColumn,
    Recipe,
    Relate,
    SelectColumns,
    Trend,
    planned_columns,
    run_recipe,
    validate_analyze,
)


def orders() -> pd.DataFrame:
    """Enough rows per city that a comparison has groups to work with."""
    return pd.DataFrame(
        {
            "city": ["Ankara", "Izmir", "Bursa"] * 20,
            "revenue": [100.0 + index * 13 for index in range(60)],
            "cost": [40.0 + index * 5 for index in range(60)],
            "order_date": pd.date_range("2024-01-01", periods=60, freq="5D").strftime("%Y-%m-%d"),
            "note": [
                f"A long free-text remark written about order {index}" for index in range(60)
            ],
        }
    )


def columns() -> list[PlannedColumn]:
    return [
        PlannedColumn(name="customer_id", inferred_type="categorical", is_probable_id=True),
        PlannedColumn(name="city", inferred_type="categorical"),
        PlannedColumn(name="sku", inferred_type="categorical", is_high_cardinality=True),
        PlannedColumn(name="revenue", inferred_type="numeric"),
        PlannedColumn(name="order_date", inferred_type="datetime"),
        PlannedColumn(name="note", inferred_type="text"),
        PlannedColumn(name="blank", inferred_type="empty"),
    ]


def refuse(step) -> str:
    refusal = validate_analyze(columns(), step)
    assert refusal is not None, f"{step.op} was accepted when it should not have been"
    return refusal.reason


def run(frame: pd.DataFrame, *steps, analyze=None):
    start = planned_columns(profile_dataset("x", "orders.csv", frame).column_schemas)
    return run_recipe(frame, start, Recipe(steps=list(steps), analyze=analyze))


def test_comparing_across_something_that_has_no_groups_is_refused():
    assert "no groups to compare" in refuse(Compare(group_by="note", measure="revenue"))
    assert "row identifier" in refuse(Compare(group_by="customer_id", measure="revenue"))
    assert "too many distinct values" in refuse(Compare(group_by="sku", measure="revenue"))
    assert "nothing to compare" in refuse(Compare(group_by="city", measure="note"))


def test_relating_a_column_to_itself_is_refused():
    assert "relates to itself" in refuse(Relate(left="revenue", right="revenue"))
    assert "nothing to relate" in refuse(Relate(left="revenue", right="city"))


def test_a_trend_needs_something_that_orders_in_time():
    reason = refuse(Trend(time="city", measure="revenue"))
    assert "cannot put anything in order of time" in reason
    assert "Convert it to a date first" in reason


def test_a_column_with_no_spread_has_no_distribution():
    assert "no spread to describe" in refuse(Distribution(column="note"))
    assert "no spread to describe" in refuse(Distribution(column="blank"))


def test_an_analysis_is_checked_against_what_the_steps_leave_behind():
    frame = orders()

    gone = run(
        frame,
        SelectColumns(columns=["city", "cost"]),
        analyze=Relate(left="revenue", right="cost"),
    )
    assert gone.refusal is not None
    assert gone.refusal.step_index == 1
    assert "An earlier step removed it." in gone.refusal.reason

    # And a column a step invents is a column the analysis may name.
    made = run(
        frame,
        DeriveColumn(
            name="day", expression=DatetimePartExpression(column="order_date", part="date")
        ),
        analyze=Trend(time="day", measure="revenue"),
    )
    assert made.refusal is None
    assert made.analysis is not None


def test_comparing_groups_answers_with_the_comparison_and_its_box_plot():
    result = run(orders(), analyze=Compare(group_by="city", measure="revenue"))

    assert result.refusal is None
    comparison = result.analysis.comparison
    assert comparison.group_column == "city"
    assert {group.name for group in comparison.groups} == {"Ankara", "Izmir", "Bursa"}
    assert result.analysis.chart.chart_type == "box"
    assert result.analysis.columns == ["city", "revenue"]


def test_relating_two_numbers_answers_with_the_pair_and_its_scatter():
    result = run(orders(), analyze=Relate(left="revenue", right="cost"))

    assert result.analysis.correlation.pearson > 0.99
    assert result.analysis.chart.chart_type == "scatter"


def test_a_trend_answers_with_the_timeline_and_its_line():
    result = run(
        orders(),
        CastColumn(column="order_date", to="datetime"),
        analyze=Trend(time="order_date", measure="revenue"),
    )

    assert result.refusal is None
    assert result.analysis.timeline.trend == "rising"
    assert result.analysis.chart.chart_type == "line"


def test_a_distribution_reads_numbers_and_categories_differently():
    numbers = run(orders(), analyze=Distribution(column="revenue"))
    assert numbers.analysis.numeric.median is not None
    assert numbers.analysis.chart.chart_type == "histogram"

    labels = run(orders(), analyze=Distribution(column="city"))
    assert labels.analysis.categorical.unique_count == 3
    assert labels.analysis.chart.chart_type == "bar"


def test_data_that_cannot_carry_the_analysis_is_refused_with_the_data_s_reason():
    """A schema can be right and the rows still not add up to a finding."""
    # Two real groups, but neither has the rows a comparison is willing to describe.
    thin = pd.DataFrame(
        {"city": ["Ankara", "Izmir"] * 4, "revenue": [float(index) for index in range(8)]}
    )
    result = run(thin, analyze=Compare(group_by="city", measure="revenue"))

    assert result.refusal is not None
    assert result.refusal.op == "compare"
    assert "rows a comparison needs" in result.refusal.reason
    # The rows are still there to look at, even though the analysis found nothing.
    assert len(result.frame) == 8


def test_a_trend_over_too_few_periods_is_refused():
    frame = pd.DataFrame(
        {"day": pd.to_datetime(["2024-01-01", "2024-01-02"]), "revenue": [10.0, 20.0]}
    )
    result = run(frame, analyze=Trend(time="day", measure="revenue"))

    assert result.refusal is not None
    assert "not enough to be a trend" in result.refusal.reason


def test_two_columns_that_never_vary_together_are_refused():
    frame = pd.DataFrame({"a": [1.0] * 10, "b": [float(index) for index in range(10)]})
    result = run(frame, analyze=Relate(left="a", right="b"))

    assert result.refusal is not None
    assert "never varies" in result.refusal.reason


def test_an_analysis_runs_on_what_the_steps_shaped_and_not_on_the_file():
    frame = orders()
    whole = run(frame, analyze=Distribution(column="revenue"))
    filtered = run(
        frame,
        FilterRows(clauses=[FilterClause(column="city", operator="eq", value="Ankara")]),
        analyze=Distribution(column="revenue"),
    )

    assert whole.analysis.numeric.count == 60
    assert filtered.analysis.numeric.count == 20


def test_an_analysis_can_follow_an_aggregate():
    frame = orders()
    result = run(
        frame,
        Aggregate(
            group_by=["city"],
            aggregations=[
                Aggregation(function="sum", column="revenue"),
                Aggregation(function="sum", column="cost"),
            ],
        ),
        analyze=Relate(left="sum_revenue", right="sum_cost"),
    )

    assert result.refusal is None
    # Three city totals, which is exactly the kind of result a caveat belongs on.
    assert result.analysis.correlation.sample_size == 3


def test_a_date_has_no_distribution_but_it_has_somewhere_to_go():
    reason = refuse(Distribution(column="order_date"))
    assert "Ask for a trend over it" in reason
