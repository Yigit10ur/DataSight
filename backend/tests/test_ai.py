import json
import threading
import time

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
from app.ai.insight_explainer import dataset_metrics
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


def analyse(frame: pd.DataFrame):
    profile = profile_dataset("x", "f.csv", frame)
    analysis = analyze_dataset(frame, profile)
    charts = build_charts(frame, profile, analysis)
    quality = check_dataset_quality(frame, profile)
    insights = build_insights(profile, analysis, quality, charts.charts).insights
    return profile, quality.score, insights


def dataset():
    rng = np.random.default_rng(0)
    return analyse(
        pd.DataFrame(
            {
                "segment": ["enterprise"] * 150 + ["smb"] * 150,
                "revenue": [*rng.normal(240, 10, 150), *rng.normal(100, 10, 150)],
            }
        )
    )


def answer_for(insights, text: str, summary: str = "A small, clean file.") -> str:
    return json.dumps(
        {"summary": summary, "explanations": {insight.id: text for insight in insights}}
    )


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
    profile, score, insights = analyse(frame)
    _, user = build_prompt(profile, score, insights)

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
        profile, score, insights = analyse(frame)
        sizes.append(len(json.dumps(build_payload(profile, score, insights))))

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
    profile, score, insights = dataset()
    client = FakeClient(answer_for(insights, "The two groups sit clearly apart."))
    result = explain_insights(profile, score, insights, client)

    assert result.available is True
    assert {item.insight_id for item in result.explanations} == {
        found.id for found in insights
    }


def test_an_ungrounded_explanation_is_left_out_but_the_rest_survive():
    profile, score, insights = dataset()
    answers = {found.id: "The groups sit clearly apart." for found in insights}
    answers[insights[0].id] = "Revenue is up 47% on last year."
    result = explain_insights(profile, score, insights, FakeClient(json.dumps(answers)))

    assert insights[0].id not in {item.insight_id for item in result.explanations}
    assert len(result.explanations) == len(insights) - 1
    assert result.available is True


def test_a_failing_model_leaves_the_dashboard_with_its_computed_messages():
    profile, score, insights = dataset()
    result = explain_insights(profile, score, insights, FakeClient(LLMError("connection reset")))

    assert result.available is False
    assert "connection reset" in result.reason
    assert result.explanations == []


def test_an_answer_that_is_not_json_is_reported_rather_than_shown():
    profile, score, insights = dataset()
    result = explain_insights(profile, score, insights, FakeClient("Sure! Here are your insights."))

    assert result.available is False
    assert result.explanations == []


def test_a_fenced_json_answer_is_still_read():
    profile, score, insights = dataset()
    fenced = "```json\n" + answer_for(insights, "The groups sit apart.") + "\n```"
    result = explain_insights(profile, score, insights, FakeClient(fenced))

    assert len(result.explanations) == len(insights)


def test_the_same_findings_are_explained_once():
    profile, score, insights = dataset()
    client = FakeClient(answer_for(insights, "The groups sit apart."))
    explain_insights(profile, score, insights, client)
    explain_insights(profile, score, insights, client)

    assert client.calls == 1


class SlowClient:
    """Stays inside one call long enough for a second caller to arrive during it."""

    def __init__(self, answer: str):
        self.answer = answer
        # Appended to rather than counted: a counter that loses an increment to a
        # race would hide the very failure this is here to catch.
        self.started: list[str] = []

    def complete(self, system: str, user: str) -> str:
        self.started.append(user)
        time.sleep(0.05)
        return self.answer


def test_findings_asked_about_twice_at_once_are_still_explained_once():
    """The cache only saves money if the second caller waits instead of racing.

    A browser sends this pair unprompted: React mounts an effect twice in
    development, so both requests are in flight before either has answered.
    """
    profile, score, insights = dataset()
    client = SlowClient(answer_for(insights, "The groups sit apart."))
    results: list = []

    def ask() -> None:
        results.append(explain_insights(profile, score, insights, client))

    threads = [threading.Thread(target=ask) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(client.started) == 1
    assert len(results) == 2
    assert all(len(result.explanations) == len(insights) for result in results)


def test_only_the_first_few_findings_are_sent():
    profile, score, insights = dataset()
    many = [
        insights[0].model_copy(update={"id": f"finding-{index}"})
        for index in range(settings.explanation_max_insights + 5)
    ]
    client = FakeClient(answer_for(many, "The groups sit apart."))
    explain_insights(profile, score, many, client)

    assert len(json.loads(client.user)["findings"]) == settings.explanation_max_insights


def test_without_a_key_there_is_no_client_and_no_call():
    profile, score, insights = dataset()
    assert default_client() is None

    result = explain_insights(profile, score, insights)
    assert result.available is False
    assert "key" in result.reason


def test_a_dataset_with_no_findings_still_gets_a_summary():
    profile, score, _ = dataset()
    client = FakeClient(json.dumps({"summary": "Nothing here stands out.", "explanations": {}}))
    result = explain_insights(profile, score, [], client)

    assert result.available is True
    assert result.explanations == []
    assert result.summary == "Nothing here stands out."


def test_the_rules_the_model_is_given_are_the_rules_of_the_project():
    profile, score, insights = dataset()
    system, _ = build_prompt(profile, score, insights)

    assert "Use only the numbers" in system
    assert "causes" in system
    assert "JSON" in system


def test_traceability_and_causation_helpers_agree_with_their_names():
    assert untraceable_numbers("up 5%", {"ratio": 0.05}, []) == set()
    assert untraceable_numbers("up 6%", {"ratio": 0.05}, []) == {"6%"}
    assert causal_claims("Spending causes revenue.")
    assert causal_claims("Spending does not cause revenue.") == []


def test_a_number_the_prompt_shows_is_a_number_the_check_accepts():
    """rows_behind_it is in the payload for every finding, so it has to verify.

    Only some insight types repeat the sample size inside metrics. A model that
    quoted it on the others was rejected for using a number it had been given.
    """
    trend = insight(metrics={"change_ratio": -0.316}, columns=["date", "revenue"])
    trend.sample_size = 342

    assert verify("It draws on 342 rows.", trend) is not None
    # A row count that was never shown is still refused.
    assert verify("It draws on 999 rows.", trend) is None


def test_an_explanation_may_quote_the_size_of_the_file_it_describes():
    """The payload shows the dataset block above every finding, so it must verify."""
    profile, score, insights = dataset()
    found = insights[0]
    facts = dataset_metrics(profile, score)

    assert verify(f"It rests on all {profile.rows} rows.", found, facts) is not None
    # A file size that was never shown is still refused.
    assert verify("It rests on all 7777 rows.", found, facts) is None


def test_calling_a_result_unlikely_to_be_chance_is_not_a_causal_claim():
    """The phrase list matches the verb; the object decides what it means."""
    assert causal_claims("The gap is unlikely to be due to chance alone.") == []
    assert causal_claims("This is not due to sampling.") == []
    # A real claim beside the idiom is still caught.
    assert causal_claims("Unlikely to be due to chance, since spend drives revenue.")
    assert causal_claims("Revenue is due to spend.")


def test_a_negative_metric_is_traceable_written_either_way():
    """Direction in the verb or on the number: both quote the same measurement.

    The generator writes the magnitude unsigned ("fell 31.6%" from -0.316), so a
    check that only accepted the signed form rejected the sentence the analysis
    engine itself produced.
    """
    metrics = {"change_ratio": -0.316}

    assert untraceable_numbers("fell 31.6%", metrics, []) == set()
    assert untraceable_numbers("changed by -31.6%", metrics, []) == set()
    # The magnitude still has to be the one that was measured.
    assert untraceable_numbers("fell 47.2%", metrics, []) == {"47.2%"}


def summary_from(text: str):
    profile, score, insights = dataset()
    answer = json.dumps({"summary": text, "explanations": {}})
    return explain_insights(profile, score, insights, FakeClient(answer)).summary


def test_a_summary_may_use_the_numbers_of_any_finding_it_draws_on():
    profile, score, insights = dataset()
    ratio = insights[0].metrics["mean_ratio"]
    answer = json.dumps(
        {
            "summary": f"Across 300 rows the higher group averages {ratio:.1f}x the lower.",
            "explanations": {},
        }
    )
    result = explain_insights(profile, score, insights, FakeClient(answer))

    assert result.summary is not None


def test_a_summary_may_use_the_shape_and_score_of_the_dataset():
    assert summary_from("300 rows across 2 columns, scoring 100 out of 100.") is not None


def test_a_summary_that_invents_a_number_is_dropped():
    assert summary_from("The file holds 300 rows and 14% of them are duplicates.") is None


def test_a_summary_claiming_cause_is_dropped():
    assert summary_from("Being an enterprise account causes the higher revenue.") is None


def test_a_dropped_summary_does_not_take_the_explanations_with_it():
    profile, score, insights = dataset()
    answer = json.dumps(
        {
            "summary": "Revenue grew 47% this year.",
            "explanations": {insight.id: "The groups sit apart." for insight in insights},
        }
    )
    result = explain_insights(profile, score, insights, FakeClient(answer))

    assert result.summary is None
    assert len(result.explanations) == len(insights)
    assert result.available is True


def test_the_summary_and_the_explanations_come_from_one_call():
    profile, score, insights = dataset()
    client = FakeClient(answer_for(insights, "The groups sit apart.", "A clean file."))
    result = explain_insights(profile, score, insights, client)

    assert client.calls == 1
    assert result.summary == "A clean file."
    assert len(result.explanations) == len(insights)


def test_the_quality_score_is_offered_to_the_model():
    profile, score, insights = dataset()
    _, user = build_prompt(profile, score, insights)
    payload = json.loads(user)

    assert payload["quality_score"]["overall"] == score.score
    assert payload["quality_score"]["dimensions"]


def test_an_answer_without_a_summary_still_yields_explanations():
    profile, score, insights = dataset()
    answer = json.dumps(
        {"explanations": {insight.id: "The groups sit apart." for insight in insights}}
    )
    result = explain_insights(profile, score, insights, FakeClient(answer))

    assert result.summary is None
    assert len(result.explanations) == len(insights)


def test_an_answer_whose_explanations_are_not_an_object_is_rejected():
    profile, score, insights = dataset()
    result = explain_insights(
        profile, score, insights, FakeClient(json.dumps({"explanations": ["a", "b"]}))
    )

    assert result.available is False
