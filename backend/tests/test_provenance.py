import pandas as pd

from app.analysis import analyze_dataset
from app.insights import build_insights
from app.insights.insight_generator import GROUPED_ROWS_CONFIDENCE
from app.profiling import profile_dataset
from app.provenance import GROUPED_ROWS_CAVEAT, Provenance
from app.quality import check_dataset_quality
from app.quality.score import (
    GAPS_SHAPED_CAVEAT,
    GROUPED_ROWS_SCORE_CAVEAT,
    ROWS_REMOVED_CAVEAT,
)
from app.recipes import (
    Aggregate,
    Aggregation,
    DropDuplicates,
    DropMissing,
    FillMissing,
    FilterClause,
    FilterRows,
    LimitRows,
    Recipe,
    RenameColumn,
    SelectColumns,
    SortRows,
    provenance_of,
)
from app.visualization import build_charts


def recipe(*steps) -> Recipe:
    return Recipe(steps=list(steps))


def test_a_file_nobody_shaped_has_nothing_to_say_about_itself():
    assert provenance_of([]) == Provenance()
    assert provenance_of([recipe()]) == Provenance()


def test_steps_that_leave_a_row_meaning_what_it_meant_say_so():
    shaped = provenance_of(
        recipe(step)
        for step in [
            SelectColumns(columns=["city"]),
            SortRows(columns=["city"]),
            RenameColumn(column="city", to="town"),
        ]
    )

    assert shaped.steps == 3
    assert not shaped.rows_are_groups
    assert not shaped.rows_were_removed
    assert not shaped.gaps_were_shaped


def test_grouping_is_the_step_that_changes_what_a_row_is():
    grouped = provenance_of(
        [recipe(Aggregate(group_by=["city"], aggregations=[Aggregation(function="count")]))]
    )
    assert grouped.rows_are_groups

    for step in (FilterRows(clauses=[FilterClause(column="a", operator="gt", value=1)]),
                 LimitRows(count=5), DropDuplicates(), DropMissing()):
        assert not provenance_of([recipe(step)]).rows_are_groups, step.op
        assert provenance_of([recipe(step)]).rows_were_removed, step.op


def test_acting_on_gaps_is_told_apart_from_removing_rows():
    filled = provenance_of([recipe(FillMissing(column="a", method="mode"))])
    assert filled.gaps_were_shaped
    assert not filled.rows_were_removed

    filtered = provenance_of(
        [recipe(FilterRows(clauses=[FilterClause(column="a", operator="gt", value=1)]))]
    )
    assert filtered.rows_were_removed
    assert not filtered.gaps_were_shaped


def test_provenance_reads_the_whole_chain_and_not_only_the_last_recipe():
    shaped = provenance_of(
        [
            recipe(Aggregate(group_by=["city"], aggregations=[Aggregation(function="count")])),
            recipe(SortRows(columns=["city"])),
        ]
    )

    assert shaped.steps == 2
    assert shaped.rows_are_groups


def orders() -> pd.DataFrame:
    cities = ["Ankara", "Izmir", "Bursa", "Antalya"]
    return pd.DataFrame(
        {
            "city": [cities[index % 4] for index in range(200)],
            "revenue": [100.0 + (index % 37) * 41 + (index % 4) * 900 for index in range(200)],
            "cost": [50.0 + (index % 29) * 17 + (index % 4) * 300 for index in range(200)],
        }
    )


def findings(frame: pd.DataFrame, shaped: Provenance | None = None):
    profile = profile_dataset("x", "orders.csv", frame)
    analysis = analyze_dataset(frame, profile)
    charts = build_charts(frame, profile, analysis)
    quality = check_dataset_quality(frame, profile, shaped)
    return build_insights(profile, analysis, quality, charts.charts, shaped).insights


def one(insights, insight_type):
    return next(insight for insight in insights if insight.insight_type == insight_type)


def test_a_finding_over_grouped_rows_says_what_a_row_is():
    """The case the reliability curve cannot catch.

    A correlation over two hundred daily totals has two hundred rows behind it, so
    nothing about the sample size marks it out — and it answers a different question
    from the same correlation over two hundred orders.
    """
    frame = orders()
    plain = one(findings(frame), "correlation")
    grouped = one(findings(frame, Provenance(steps=1, rows_are_groups=True)), "correlation")

    assert GROUPED_ROWS_CAVEAT not in plain.caveats
    assert GROUPED_ROWS_CAVEAT in grouped.caveats
    assert grouped.confidence == GROUPED_ROWS_CONFIDENCE
    assert grouped.importance < plain.importance
    # The numbers themselves are untouched: only what is said about them changed.
    assert grouped.metrics == plain.metrics


def test_a_group_difference_over_grouped_rows_says_it_too():
    grouped = one(
        findings(orders(), Provenance(steps=1, rows_are_groups=True)), "group_difference"
    )
    assert GROUPED_ROWS_CAVEAT in grouped.caveats


def test_a_finding_about_a_column_s_own_shape_is_left_alone():
    """A long tail in a column of totals is a fact about those totals, said correctly."""
    frame = pd.DataFrame({"total": [1.0] * 40 + [900.0, 1500.0, 3000.0]})
    shaped = findings(frame, Provenance(steps=1, rows_are_groups=True))

    assert any(insight.insight_type == "skewed_distribution" for insight in shaped)
    assert all(
        GROUPED_ROWS_CAVEAT not in insight.caveats
        for insight in shaped
        if insight.insight_type == "skewed_distribution"
    )


def score_of(frame: pd.DataFrame, shaped: Provenance | None = None):
    profile = profile_dataset("x", "orders.csv", frame)
    return check_dataset_quality(frame, profile, shaped).score


def test_an_uploaded_file_has_nothing_written_next_to_its_score():
    assert score_of(orders()).caveats == []


def test_a_score_the_recipe_produced_says_which_step_produced_it():
    shaped = Provenance(steps=1, gaps_were_shaped=True, rows_were_removed=True)
    gapless = score_of(orders(), shaped)

    assert gapless.score == 100
    # The number stands; changing it would claim the data is worse than it is.
    assert GAPS_SHAPED_CAVEAT in gapless.caveats
    assert ROWS_REMOVED_CAVEAT in gapless.caveats


def test_grouping_says_the_stronger_thing_instead_of_the_weaker_one():
    grouped = score_of(
        orders(), Provenance(steps=1, rows_are_groups=True, rows_were_removed=True)
    )

    assert GROUPED_ROWS_SCORE_CAVEAT in grouped.caveats
    assert ROWS_REMOVED_CAVEAT not in grouped.caveats


def test_nothing_breaks_on_a_frame_too_small_to_mean_anything():
    """Whatever a recipe leaves behind still has to go through the whole pipeline."""
    for frame in (
        pd.DataFrame({"city": ["Ankara"], "revenue": [100.0]}),
        pd.DataFrame({"city": ["Ankara", "Izmir"], "revenue": [100.0, 200.0]}),
        pd.DataFrame({"city": [None, None], "revenue": [None, None]}),
        pd.DataFrame({"city": ["Ankara"] * 5, "revenue": [1.0, 2.0, 3.0, 4.0, 5.0]}),
    ):
        profile = profile_dataset("x", "small.csv", frame)
        analysis = analyze_dataset(frame, profile)
        charts = build_charts(frame, profile, analysis)
        quality = check_dataset_quality(frame, profile)
        insights = build_insights(profile, analysis, quality, charts.charts)
        # Too little to say anything about, and saying nothing is the right answer.
        assert insights.insights == []
