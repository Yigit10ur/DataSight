import json

import numpy as np
import pandas as pd
import pytest

from app.ai import (
    build_payload,
    build_prompt,
    causal_claims,
    clear_cache,
    explain_insights,
    untraceable_numbers,
    verify,
)
from app.ai.llm_client import LLMError, default_client
from app.analysis import analyze_dataset
from app.config import settings
from app.insights import build_insights
from app.insights.models import Insight
from app.profiling import profile_dataset
from app.quality import check_dataset_quality
from app.visualization import build_charts


@pytest.fixture(autouse=True)
def empty_cache():
    clear_cache()
    yield
    clear_cache()


class FakeClient:
    """Answers with whatever the test decided, and remembers what it was asked."""

    def __init__(self, answer):
        self.answer = answer
        self.system = None
        self.user = None
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        self.system, self.user = system, user
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def dataset():
    rng = np.random.default_rng(0)
    frame = pd.DataFrame(
        {
            "segment": ["enterprise"] * 150 + ["smb"] * 150,
            "revenue": [*rng.normal(240, 10, 150), *rng.normal(100, 10, 150)],
        }
    )
    profile = profile_dataset("x", "f.csv", frame)
    analysis = analyze_dataset(frame, profile)
    charts = build_charts(frame, profile, analysis)
    quality = check_dataset_quality(frame, profile)
    return profile, build_insights(profile, analysis, quality, charts.charts).insights


def answer_for(insights, text: str) -> str:
    return json.dumps({insight.id: text for insight in insights})


def insight(metrics=None, columns=None) -> Insight:
    return Insight(
        id="i1",
        insight_type="correlation",
        columns=columns if columns is not None else ["spend", "revenue"],
        message="m",
        metrics=metrics if metrics is not None else {"pearson": 0.98, "sample_size": 400},
        strength=0.9,
        confidence=1.0,
        sample_size=400,
        caveats=[],
        chart_id=None,
    )


def test_no_row_of_the_dataset_reaches_the_prompt():
    # Every row carries a value that appears nowhere else, so any of them showing up
    # in the prompt would mean raw data had been sent.
    rng = np.random.default_rng(0)
    frame = pd.DataFrame(
        {
            "segment": ["enterprise"] * 150 + ["smb"] * 150,
            "revenue": [*rng.normal(240, 10, 150), *rng.normal(100, 10, 150)],
            "note": [f"ticket-{index:04d}" for index in range(300)],
        }
    )
    profile = profile_dataset("x", "f.csv", frame)
    analysis = analyze_dataset(frame, profile)
    charts = build_charts(frame, profile, analysis)
    quality = check_dataset_quality(frame, profile)
    insights = build_insights(profile, analysis, quality, charts.charts).insights
    _, user = build_prompt(profile, insights)

    assert not any(f"ticket-{index:04d}" in user for index in range(300))
    # Column names and group names are part of a finding and belong there.
    assert "enterprise" in user
    assert "note" in user


def test_the_prompt_does_not_grow_with_the_number_of_rows():
    small = pd.DataFrame(
        {"segment": ["a"] * 30 + ["b"] * 30, "revenue": [*np.linspace(1, 30, 30)] * 2}
    )
    large = pd.DataFrame(
        {
            "segment": ["a"] * 3000 + ["b"] * 3000,
            "revenue": [*np.linspace(1, 3000, 3000)] * 2,
        }
    )
    sizes = []
    for frame in (small, large):
        profile = profile_dataset("x", "f.csv", frame)
        analysis = analyze_dataset(frame, profile)
        charts = build_charts(frame, profile, analysis)
        quality = check_dataset_quality(frame, profile)
        insights = build_insights(profile, analysis, quality, charts.charts).insights
        sizes.append(len(json.dumps(build_payload(profile, insights))))

    assert max(sizes) < 4 * min(sizes)


def test_an_explanation_built_from_the_given_numbers_is_kept():
    found = insight()
    text = "The two columns track each other closely, at r = 0.98 over 400 rows."

    assert verify(text, found) == text


def test_an_explanation_that_invents_a_number_is_dropped():
    found = insight()
    text = "The two columns track each other, and revenue grew 32% over the period."

    assert verify(text, found) is None


def test_a_rounded_number_is_still_the_number():
    found = insight(metrics={"highest_mean": 240.13, "sample_size": 300})

    assert verify("The higher group averages about 240 across 300 rows.", found) is not None


def test_an_explanation_claiming_cause_is_dropped():
    found = insight()

    assert verify("More spending drives more revenue.", found) is None


def test_an_explanation_denying_cause_is_kept():
    found = insight()
    text = "The two move together, but this does not show that one causes the other."

    assert verify(text, found) is not None


def test_an_empty_explanation_is_dropped():
    assert verify("   ", insight()) is None


def test_dates_in_an_explanation_are_not_read_as_invented_numbers():
    found = insight(metrics={"period": "2025-02-16", "delta": 364.9}, columns=["day"])
    text = "The largest single move happened at 2025-02-16, a change of 364.9."

    assert verify(text, found) is not None


def test_column_names_containing_digits_do_not_count_as_numbers():
    found = insight(metrics={"pearson": 0.9}, columns=["q1_revenue"])

    assert verify("q1_revenue moves with the other column, at 0.9.", found) is not None


def test_verified_explanations_come_back_for_their_findings():
    profile, insights = dataset()
    client = FakeClient(answer_for(insights, "The two groups sit clearly apart."))
    result = explain_insights(profile, insights, client)

    assert result.available is True
    assert {item.insight_id for item in result.explanations} == {
        found.id for found in insights
    }


def test_an_ungrounded_explanation_is_left_out_but_the_rest_survive():
    profile, insights = dataset()
    answers = {found.id: "The groups sit clearly apart." for found in insights}
    answers[insights[0].id] = "Revenue is up 47% on last year."
    result = explain_insights(profile, insights, FakeClient(json.dumps(answers)))

    assert insights[0].id not in {item.insight_id for item in result.explanations}
    assert len(result.explanations) == len(insights) - 1
    assert result.available is True


def test_a_failing_model_leaves_the_dashboard_with_its_computed_messages():
    profile, insights = dataset()
    result = explain_insights(profile, insights, FakeClient(LLMError("connection reset")))

    assert result.available is False
    assert "connection reset" in result.reason
    assert result.explanations == []


def test_an_answer_that_is_not_json_is_reported_rather_than_shown():
    profile, insights = dataset()
    result = explain_insights(profile, insights, FakeClient("Sure! Here are your insights."))

    assert result.available is False
    assert result.explanations == []


def test_a_fenced_json_answer_is_still_read():
    profile, insights = dataset()
    fenced = "```json\n" + answer_for(insights, "The groups sit apart.") + "\n```"
    result = explain_insights(profile, insights, FakeClient(fenced))

    assert len(result.explanations) == len(insights)


def test_the_same_findings_are_explained_once():
    profile, insights = dataset()
    client = FakeClient(answer_for(insights, "The groups sit apart."))
    explain_insights(profile, insights, client)
    explain_insights(profile, insights, client)

    assert client.calls == 1


def test_only_the_first_few_findings_are_sent():
    profile, insights = dataset()
    many = [
        insights[0].model_copy(update={"id": f"finding-{index}"})
        for index in range(settings.explanation_max_insights + 5)
    ]
    client = FakeClient(answer_for(many, "The groups sit apart."))
    explain_insights(profile, many, client)

    assert len(json.loads(client.user)["findings"]) == settings.explanation_max_insights


def test_without_a_key_there_is_no_client_and_no_call():
    profile, insights = dataset()
    assert default_client() is None

    result = explain_insights(profile, insights)
    assert result.available is False
    assert "key" in result.reason


def test_a_dataset_with_no_findings_needs_no_model():
    profile, _ = dataset()
    client = FakeClient("{}")
    result = explain_insights(profile, [], client)

    assert result.available is True
    assert result.explanations == []
    assert client.calls == 0


def test_the_rules_the_model_is_given_are_the_rules_of_the_project():
    profile, insights = dataset()
    system, _ = build_prompt(profile, insights)

    assert "Use only the numbers" in system
    assert "causes" in system
    assert "JSON" in system


def test_traceability_and_causation_helpers_agree_with_their_names():
    assert untraceable_numbers("up 5%", {"ratio": 0.05}, []) == set()
    assert untraceable_numbers("up 6%", {"ratio": 0.05}, []) == {"6%"}
    assert causal_claims("Spending causes revenue.")
    assert causal_claims("Spending does not cause revenue.") == []
