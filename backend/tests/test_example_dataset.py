"""Pin the figures the README walkthrough promises about the example file.

A first-time user follows that walkthrough with no dataset and no API key of their
own, so the numbers it quotes are part of the interface. They come out of the same
thresholds every other test exercises in isolation — the missing-value bands, the
Tukey fences, the effect-size floor — and moving any of those silently turns the
walkthrough into a lie. These tests read the committed file exactly as an upload
would and fail here instead, naming what the README then has to say.
"""

from pathlib import Path

import pytest

from app.analysis import analyze_dataset
from app.ingestion import load_dataset
from app.insights import build_insights
from app.profiling import profile_dataset
from app.provenance import Provenance
from app.quality import check_dataset_quality
from app.recipes import (
    Aggregate,
    Aggregation,
    DropDuplicates,
    Recipe,
    planned_columns,
    run_recipe,
)
from app.visualization import build_charts

EXAMPLE = Path(__file__).resolve().parents[2] / "example-data" / "orders-sample.csv"


@pytest.fixture(scope="module")
def frame():
    return load_dataset(EXAMPLE.name, EXAMPLE.read_bytes(), 10 * 1024 * 1024)


@pytest.fixture(scope="module")
def profile(frame):
    return profile_dataset("example", EXAMPLE.name, frame)


@pytest.fixture(scope="module")
def report(frame, profile):
    return check_dataset_quality(frame, profile, Provenance())


@pytest.fixture(scope="module")
def insights(frame, profile, report):
    analysis = analyze_dataset(frame, profile)
    charts = build_charts(frame, profile, analysis)
    return build_insights(profile, analysis, report, charts.charts, Provenance()).insights


def issue(report, issue_type: str, column: str | None = None):
    return next(
        found
        for found in report.issues
        if found.issue_type == issue_type and (column is None or column in found.columns)
    )


def test_example_file_is_small_enough_to_read_in_a_diff():
    assert EXAMPLE.stat().st_size < 8 * 1024


def test_profile_matches_the_walkthrough(profile):
    assert profile.rows == 60
    assert profile.columns == 9
    assert profile.duplicate_rows == 3

    types = {schema.name: schema.inferred_type for schema in profile.column_schemas}
    assert types == {
        "order_id": "text",
        "order_date": "datetime",
        "channel": "categorical",
        "region": "categorical",
        "units": "numeric",
        "unit_price": "numeric",
        "order_total": "numeric",
        "delivery_days": "numeric",
        # The planted defect: percentages a reader would expect to be numeric.
        "discount_pct": "categorical",
    }


def test_quality_score_is_the_one_the_walkthrough_quotes(report):
    assert report.score.score == 80


def test_every_planted_issue_is_reported_as_a_warning(report):
    warnings = {
        (found.issue_type, tuple(found.columns))
        for found in report.issues
        if found.severity == "warning"
    }
    assert warnings == {
        ("missing_values", ("delivery_days",)),
        ("duplicate_rows", ()),
        ("outliers", ("delivery_days",)),
        ("suspicious_categories", ("channel",)),
        ("inconsistent_formatting", ("channel",)),
        ("mistyped_column", ("discount_pct",)),
    }


def test_missing_delivery_days_are_counted(report):
    found = issue(report, "missing_values", "delivery_days")

    assert found.metrics["missing_count"] == 7
    assert found.metrics["missing_ratio"] == pytest.approx(7 / 60)


def test_the_three_repeated_orders_are_reported(report):
    found = issue(report, "duplicate_rows")

    assert found.metrics["duplicate_rows"] == 3
    assert found.metrics["duplicate_ratio"] == pytest.approx(0.05)


def test_the_late_deliveries_sit_outside_the_fences(report):
    found = issue(report, "outliers", "delivery_days")

    assert found.metrics["outlier_count"] == 3
    assert found.metrics["maximum"] == 29.0


def test_channel_spellings_collapse_into_two_groups(report):
    found = issue(report, "suspicious_categories", "channel")
    groups = {frozenset(group) for group in found.metrics["groups"]}

    assert found.metrics["group_count"] == 2
    assert groups == {
        frozenset({"Online", "online", " Online"}),
        frozenset({"Retail", "Retail "}),
    }


def test_padded_channel_values_are_reported_on_their_own(report):
    assert issue(report, "inconsistent_formatting", "channel").metrics["affected_rows"] == 7


def test_discount_percentages_are_numbers_held_as_text(report):
    # Four "pending" rows out of sixty: enough to keep the column out of numeric
    # analysis, and few enough that reading it as a number is not refused.
    found = issue(report, "mistyped_column", "discount_pct")
    assert found.metrics["numeric_ratio"] == pytest.approx(56 / 60)


def test_the_leading_finding_is_the_gap_between_regions(insights):
    leading = insights[0]

    assert leading.insight_type == "group_difference"
    assert leading.columns == ["region", "order_total"]
    assert leading.metrics["highest_group"] == "West"
    assert leading.metrics["lowest_group"] == "North"
    assert leading.metrics["mean_ratio"] == pytest.approx(1.84, abs=0.005)


def test_units_and_order_total_are_reported_as_related(insights):
    found = next(
        found
        for found in insights
        if found.insight_type == "correlation" and found.columns == ["units", "order_total"]
    )

    assert found.metrics["pearson"] == pytest.approx(0.94, abs=0.005)
    assert found.sample_size == 60


def test_the_walkthrough_recipe_produces_the_quoted_totals(frame, profile):
    recipe = Recipe(
        steps=[
            DropDuplicates(),
            Aggregate(
                group_by=["region"],
                aggregations=[Aggregation(function="sum", column="order_total")],
            ),
        ]
    )
    run = run_recipe(frame, planned_columns(profile.column_schemas), recipe)

    assert run.refusal is None
    assert [(report.rows_in, report.rows_out) for report in run.reports] == [(60, 57), (57, 4)]

    totals = dict(zip(run.frame["region"], run.frame["sum_order_total"].round(2)))
    assert totals == {
        "East": 4698.53,
        "North": 3523.10,
        "South": 3914.06,
        "West": 6083.31,
    }


def test_removing_the_duplicates_is_what_makes_those_totals_right(frame, profile):
    """The step the walkthrough justifies: without it three regions are overstated."""
    recipe = Recipe(
        steps=[
            Aggregate(
                group_by=["region"],
                aggregations=[Aggregation(function="sum", column="order_total")],
            )
        ]
    )
    run = run_recipe(frame, planned_columns(profile.column_schemas), recipe)
    totals = dict(zip(run.frame["region"], run.frame["sum_order_total"].round(2)))

    assert totals == {
        "East": 4991.21,
        "North": 3831.54,
        # The one region with no repeated order, and the one total that does not move.
        "South": 3914.06,
        "West": 6606.83,
    }


def test_the_walkthrough_download_arrives_as_the_file_it_names():
    """The last step of the walkthrough, through the API the browser actually calls."""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    upload = client.post(
        "/api/upload", files={"file": (EXAMPLE.name, EXAMPLE.read_bytes(), "text/csv")}
    )
    assert upload.status_code == 200
    dataset_id = upload.json()["dataset_id"]

    response = client.post(
        f"/api/datasets/{dataset_id}/recipe/export",
        json={
            "steps": [
                {"op": "drop_duplicates"},
                {
                    "op": "aggregate",
                    "group_by": ["region"],
                    "aggregations": [{"function": "sum", "column": "order_total"}],
                },
            ]
        },
    )

    assert response.status_code == 200
    assert 'filename="orders-sample (2 steps).csv"' in response.headers["content-disposition"]

    header, *lines = response.text.splitlines()
    assert header == "region,sum_order_total"
    # Rounded, because the export writes a float at full precision and the exact
    # digits after the second decimal are a property of the summation, not of the
    # figure the walkthrough quotes.
    written = [(region, round(float(total), 2)) for region, total in
               (line.split(",") for line in lines)]
    assert written == [
        ("East", 4698.53),
        ("North", 3523.10),
        ("South", 3914.06),
        ("West", 6083.31),
    ]
