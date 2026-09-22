import pandas as pd
import pytest
from pydantic import ValidationError

from app.profiling import profile_dataset
from app.questions import PlanRefused, execute_plan, validate_plan
from app.questions.models import (
    AggregatePlan,
    ComparePlan,
    CountPlan,
    DescribePlan,
    DistributionPlan,
    RankPlan,
    RelatePlan,
    TrendPlan,
)
from app.recipes import FilterClause


def sales():
    rows = 60
    frame = pd.DataFrame(
        {
            "order_id": [f"O-{index:03}" for index in range(rows)],
            "product": (["Atlas"] * 20 + ["Beacon"] * 20 + ["Comet"] * 20),
            "segment": ["enterprise", "smb"] * 30,
            "revenue": [100 + index * 4 for index in range(rows)],
            "cost": [50 + index * 2 for index in range(rows)],
            "ordered_at": pd.date_range("2024-01-01", periods=rows, freq="7D"),
            "notes": [f"note {index}" for index in range(rows)],
        }
    )
    return frame, profile_dataset("sales", "sales.csv", frame)


@pytest.mark.parametrize(
    "plan,operation,chart",
    [
        (RankPlan(measure="revenue", function="sum", group_by=["product"], limit=3), "rank", "bar"),
        (AggregatePlan(measure="revenue", function="mean", group_by=["segment"]), "aggregate", "bar"),
        (ComparePlan(measure="revenue", group_by="segment"), "compare", "box"),
        (RelatePlan(measure="revenue", secondary_measure="cost"), "relate", "scatter"),
        (TrendPlan(measure="revenue", time="ordered_at"), "trend", "line"),
        (DistributionPlan(column="revenue"), "distribution", "histogram"),
        (CountPlan(filters=[FilterClause(column="segment", operator="eq", value="smb")]), "count", None),
        (DescribePlan(column="notes"), "describe", None),
    ],
)
def test_hand_written_plans_execute_deterministically(plan, operation, chart):
    frame, profile = sales()
    result = execute_plan(frame, profile, plan)
    assert result.insight.id == f"question-{operation}"
    assert (result.chart.chart_type if result.chart else None) == chart
    assert result.insight.sample_size > 0


def test_grouping_and_ranking_return_expected_python_results():
    frame, profile = sales()
    grouped = execute_plan(
        frame, profile,
        AggregatePlan(measure="revenue", function="sum", group_by=["product"]),
    )
    ranked = execute_plan(
        frame, profile,
        RankPlan(measure="revenue", function="sum", group_by=["product"], limit=2),
    )
    expected = frame.groupby("product")["revenue"].sum().sort_values(ascending=False)
    assert {row["product"]: row["value"] for row in grouped.rows} == expected.to_dict()
    assert [row["product"] for row in ranked.rows] == expected.index[:2].tolist()
    assert [row["value"] for row in ranked.rows] == expected.iloc[:2].tolist()


@pytest.mark.parametrize(
    "plan,reason",
    [
        (CountPlan(filters=[FilterClause(column="missing", operator="eq", value="x")]), "no column"),
        (AggregatePlan(measure="product", function="sum"), "cannot be used"),
        (CountPlan(filters=[FilterClause(column="revenue", operator="gt", value="many")]), "cannot be read"),
        (AggregatePlan(measure="revenue", function="mean", group_by=["order_id"]), "identifier"),
        (AggregatePlan(measure="revenue", function="mean", group_by=["notes"]), "too many"),
        (TrendPlan(measure="revenue", time="product"), "not a date"),
        (RelatePlan(measure="revenue", secondary_measure="revenue"), "itself"),
        (DistributionPlan(column="order_id"), "individual rows"),
    ],
)
def test_invalid_or_private_plans_are_refused_with_a_reason(plan, reason):
    _, profile = sales()
    with pytest.raises(PlanRefused, match=reason):
        validate_plan(plan, profile)


def test_closed_plan_schema_rejects_code_and_unknown_operations():
    with pytest.raises(ValidationError):
        CountPlan.model_validate({"operation": "count", "python": "frame.head()"})
    with pytest.raises(ValidationError):
        CountPlan.model_validate({
            "operation": "count",
            "filters": [{
                "column": "revenue", "operator": "gt", "value": 10,
                "python": "frame.query('revenue > 10')",
            }],
        })
    from pydantic import TypeAdapter
    from app.questions.models import AnalysisPlan
    with pytest.raises(ValidationError):
        TypeAdapter(AnalysisPlan).validate_python({"operation": "run_python", "code": "1+1"})


def test_result_rows_sent_for_explanation_are_capped():
    frame = pd.DataFrame({
        "group": [f"group-{index}" for index in range(25) for _ in range(3)],
        "revenue": list(range(75)),
    })
    profile = profile_dataset("many-groups", "groups.csv", frame)
    result = execute_plan(
        frame,
        profile,
        AggregatePlan(measure="revenue", function="sum", group_by=["group"]),
    )
    assert len(result.rows) == 20
    assert result.result_truncated is True
    assert "first 20" in result.insight.caveats[0]


def test_near_unique_time_groups_are_refused_before_explanation():
    frame, profile = sales()
    with pytest.raises(PlanRefused, match="too close to individual rows"):
        execute_plan(
            frame,
            profile,
            AggregatePlan(
                measure="revenue", function="sum", group_by=["ordered_at"], time_grain="day"
            ),
        )


def test_time_groups_keep_the_year_in_month_labels():
    frame, _ = sales()
    later = frame.copy()
    later["ordered_at"] = later["ordered_at"] + pd.DateOffset(years=1)
    combined = pd.concat([frame, later], ignore_index=True)
    profile = profile_dataset("two-years", "sales.csv", combined)
    result = execute_plan(
        combined,
        profile,
        AggregatePlan(
            measure="revenue", function="sum", group_by=["ordered_at"], time_grain="month"
        ),
    )
    labels = {row["ordered_at (month)"] for row in result.rows}
    assert any(label.startswith("2024-") for label in labels)
    assert any(label.startswith("2025-") for label in labels)


def test_no_executor_source_uses_dynamic_code_or_dataframe_query():
    import inspect
    import app.questions.executor as executor
    source = inspect.getsource(executor)
    forbidden = ["eval" + "(", "exec" + "(", ".query" + "(", "getattr" + "("]
    assert all(token not in source for token in forbidden)
