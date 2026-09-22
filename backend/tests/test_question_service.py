import json
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.profiling import profile_dataset
from app.questions.service import ask_question, plan_question, planning_prompt
from app.store import DatasetStore


class FakeClient:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system, user):
        self.calls.append((system, user))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def sales():
    frame = pd.DataFrame(
        {
            "product": ["Atlas"] * 20 + ["Beacon"] * 20 + ["Comet"] * 20,
            "segment": ["enterprise", "smb"] * 30,
            "revenue": [100 + index * 4 for index in range(60)],
            "cost": [50 + index * 2 for index in range(60)],
            "ordered_at": pd.date_range("2024-01-01", periods=60, freq="7D"),
            "private_note": [f"SECRET-ROW-{index}" for index in range(60)],
        }
    )
    store = DatasetStore()
    dataset_id = store.new_id()
    stored = store.add(
        dataset_id, "sales.csv", frame,
        profile_dataset(dataset_id, "sales.csv", frame),
    )
    return store, stored, frame


def envelope(plan):
    return json.dumps({"plan": plan, "refusal": None})


@pytest.mark.parametrize(
    "question,plan,operation",
    [
        ("Which products generate the most revenue?", {"operation": "rank", "measure": "revenue", "function": "sum", "group_by": ["product"], "limit": 3}, "rank"),
        ("Average revenue by segment", {"operation": "aggregate", "measure": "revenue", "function": "mean", "group_by": ["segment"]}, "aggregate"),
        ("Compare revenue by segment", {"operation": "compare", "measure": "revenue", "group_by": "segment"}, "compare"),
        ("Does cost track revenue?", {"operation": "relate", "measure": "cost", "secondary_measure": "revenue"}, "relate"),
        ("How has revenue changed?", {"operation": "trend", "measure": "revenue", "time": "ordered_at"}, "trend"),
        ("Show the revenue distribution", {"operation": "distribution", "column": "revenue"}, "distribution"),
        ("How many enterprise rows?", {"operation": "count", "filters": [{"column": "segment", "operator": "eq", "value": "enterprise"}]}, "count"),
    ],
)
def test_golden_question_plan_pairs_use_fake_clients(question, plan, operation):
    _, stored, _ = sales()
    fake = FakeClient(envelope(plan))
    planned = plan_question(question, stored.profile, [], fake)
    assert planned.plan.operation == operation
    assert len(fake.calls) == 1


def test_question_runs_two_model_calls_and_verifies_the_answer():
    store, stored, frame = sales()
    fake = FakeClient(
        envelope({
            "operation": "count",
            "filters": [{"column": "segment", "operator": "eq", "value": "enterprise"}],
        }),
        json.dumps({"answer": "30 rows match the enterprise filter."}),
    )
    response = ask_question(store, stored, frame, "How many enterprise rows?", True, fake)
    assert response.status == "answered"
    assert response.answer == "30 rows match the enterprise filter."
    assert response.explained is True
    assert response.rows == [{"count": 30}]
    assert len(fake.calls) == 2


def test_unverified_model_prose_falls_back_to_python_result():
    store, stored, frame = sales()
    fake = FakeClient(
        envelope({"operation": "count"}),
        json.dumps({"answer": "999 rows match because revenue caused growth."}),
    )
    response = ask_question(store, stored, frame, "How many rows?", True, fake)
    assert response.status == "answered"
    assert response.answer == "60 rows match the question."
    assert response.explained is False
    assert "rejected" in response.explanation_reason


def test_disabled_feature_and_causal_questions_make_no_model_calls():
    store, stored, frame = sales()
    fake = FakeClient()
    disabled = ask_question(store, stored, frame, "How many rows?", False, fake)
    causal = ask_question(store, stored, frame, "Why did revenue rise?", True, fake)
    assert disabled.status == causal.status == "refused"
    assert "No model was called" in disabled.refusal
    assert "cannot establish why" in causal.refusal
    assert fake.calls == []


def test_unsupported_question_returns_the_planners_useful_refusal():
    store, stored, frame = sales()
    fake = FakeClient(json.dumps({
        "plan": None,
        "refusal": "Forecasting future revenue is outside the supported analysis vocabulary.",
    }))
    response = ask_question(store, stored, frame, "Forecast next year's revenue", True, fake)
    assert response.status == "refused"
    assert "outside" in response.refusal
    assert len(fake.calls) == 1


def test_raw_rows_and_profile_samples_never_reach_either_prompt():
    store, stored, frame = sales()
    fake = FakeClient(
        envelope({"operation": "count"}),
        json.dumps({"answer": "There are 60 matching rows."}),
    )
    ask_question(store, stored, frame, "How many rows?", True, fake)
    combined = "\n".join(system + user for system, user in fake.calls)
    assert "SECRET-ROW-" not in combined
    assert "sample_values" not in combined
    assert '"rows": 60' in fake.calls[0][1]


def test_identical_question_reuses_the_stored_answer_without_model_calls():
    store, stored, frame = sales()
    first = FakeClient(
        envelope({"operation": "count"}),
        json.dumps({"answer": "There are 60 rows."}),
    )
    expected = ask_question(store, stored, frame, "How many rows?", True, first)
    second = FakeClient()
    actual = ask_question(store, stored, frame, "How many rows?", True, second)
    assert actual == expected
    assert second.calls == []


def test_concurrent_identical_questions_share_the_same_two_model_calls():
    store, stored, frame = sales()
    fake = FakeClient(
        envelope({"operation": "count"}),
        json.dumps({"answer": "There are 60 rows."}),
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: ask_question(store, stored, frame, "How many rows?", True, fake),
                range(2),
            )
        )
    assert responses[0] == responses[1]
    assert len(fake.calls) == 2


def test_follow_up_references_become_a_complete_explicit_plan():
    store, stored, frame = sales()
    first = FakeClient(
        envelope({
            "operation": "rank", "measure": "revenue", "function": "sum",
            "group_by": ["product"], "limit": 3,
        }),
        json.dumps({"answer": "Comet, Beacon, and Atlas are the ranked products."}),
    )
    ranked = ask_question(
        store, stored, frame, "Which three products generate the most revenue?", True, first
    )
    assert ranked.status == "answered"

    values = [row["product"] for row in ranked.rows]
    second_plan = {
        "operation": "aggregate",
        "measure": "revenue",
        "function": "sum",
        "group_by": ["ordered_at", "product"],
        "time_grain": "month",
        "filters": [{"column": "product", "operator": "in", "value": values}],
    }
    second = FakeClient(
        envelope(second_plan),
        json.dumps({"answer": "The monthly totals were computed for the selected products."}),
    )
    response = ask_question(
        store, stored, frame, "Compare the top three by month", True, second
    )
    assert response.status == "answered"
    assert response.plan.model_dump(mode="json")["filters"][0]["value"] == values
    planning_user = second.calls[0][1]
    assert "Resolved previous values" in planning_user
    assert all(value in planning_user for value in values)


def test_planning_prompt_contains_schema_and_prior_plans_but_no_results():
    _, stored, _ = sales()
    turns = [{
        "question": "Top products?",
        "plan": {"operation": "rank", "group_by": ["product"]},
        "response": {"rows": [{"product": "SECRET"}]},
    }]
    _, user = planning_prompt("And by month?", stored.profile, turns)
    assert "Top products?" in user
    assert '"operation": "rank"' in user
    assert "SECRET" not in user


def test_api_refuses_without_a_key_instead_of_making_a_live_call():
    client = TestClient(app)
    uploaded = client.post(
        "/api/upload", files={"file": ("small.csv", b"category,value\na,1\nb,2\n")}
    )
    dataset_id = uploaded.json()["dataset_id"]
    response = client.post(
        f"/api/datasets/{dataset_id}/questions",
        json={"question": "How many rows?", "use_ai": True},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "refused"
    assert "API key" in response.json()["refusal"]
