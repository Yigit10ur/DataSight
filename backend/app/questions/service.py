import json
import re
from typing import Any

import pandas as pd
from pydantic import TypeAdapter, ValidationError

from app.ai.insight_explainer import verify
from app.ai.llm_client import LLMClient, LLMError, default_client
from app.profiling.models import DatasetProfile
from app.store import DatasetStore, StoredDataset

from .executor import execute_plan
from .models import AnalysisPlan, PlanEnvelope, QuestionResponse
from app.question_state import question_lock
from .validator import PlanRefused

PLAN_ADAPTER = TypeAdapter(AnalysisPlan)
CAUSAL_QUESTION = re.compile(r"\b(why|cause[ds]?|because|reason|driv(?:e|es|en|ing))\b", re.I)
REFERENCE_QUESTION = re.compile(r"\b(those|them|these|top\s+(?:\d+|three|five|ten))\b", re.I)


def _json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1].removeprefix("json").strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise LLMError(f"The model did not return valid JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise LLMError("The model returned something other than a JSON object.")
    return parsed


def _schema_for_prompt(profile: DatasetProfile) -> list[dict[str, Any]]:
    """Planning metadata only: never sample values or rows from the file."""
    return [
        {
            "name": column.name,
            "type": column.inferred_type,
            "probable_id": column.is_probable_id,
            "high_cardinality": column.is_high_cardinality,
        }
        for column in profile.column_schemas
    ]


def _history_for_prompt(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"question": turn["question"], "plan": turn.get("plan")}
        for turn in turns[-5:]
        if turn.get("plan") is not None
    ]


def resolve_follow_up(question: str, turns: list[dict[str, Any]]) -> str:
    """Replace a conversational pointer with capped, previously computed labels."""
    if not turns or not REFERENCE_QUESTION.search(question):
        return question
    values = turns[-1].get("reference_values") or []
    if not values:
        return question
    explicit = ", ".join(json.dumps(value) for value in values[:20])
    return f"{question}\nResolved previous values (use explicit filters in the plan): [{explicit}]"


def planning_prompt(
    question: str, profile: DatasetProfile, turns: list[dict[str, Any]]
) -> tuple[str, str]:
    system = """You plan data analysis; you never calculate or answer the question.
Return JSON only: either {"plan": <one plan>, "refusal": null} or
{"plan": null, "refusal": "a useful reason"}. Use only the supplied closed schema.
Every plan must be complete and explicit. Never emit code, SQL, pandas syntax, formulas,
or column names absent from the schema. Refuse causal questions, unsupported analyses,
ambiguous columns, and requests for raw or individual rows."""
    user = json.dumps(
        {
            "question": question,
            "dataset": {
                "rows": profile.rows,
                "columns": _schema_for_prompt(profile),
            },
            "previous_turns": _history_for_prompt(turns),
            "plan_schema": PLAN_ADAPTER.json_schema(),
        },
        ensure_ascii=False,
    )
    return system, user


def plan_question(
    question: str,
    profile: DatasetProfile,
    turns: list[dict[str, Any]],
    client: LLMClient,
) -> PlanEnvelope:
    system, user = planning_prompt(question, profile, turns)
    try:
        return PlanEnvelope.model_validate(_json_object(client.complete(system, user)))
    except ValidationError as error:
        raise LLMError(f"The model returned an invalid analysis plan: {error.errors()[0]['msg']}") from error


def _explanation_prompt(
    question: str, plan: AnalysisPlan, computed
) -> tuple[str, str]:
    system = """Explain a verified Python result in one or two plain sentences.
Return JSON only as {"answer": "..."}. Use only the supplied result. Do not add
numbers, claim causality, mention unseen rows, or imply that truncated output is complete."""
    user = json.dumps(
        {
            "question": question,
            "plan": plan.model_dump(mode="json"),
            "computed_message": computed.insight.message,
            "metrics": computed.insight.metrics,
            "result_rows": computed.rows,
            "result_truncated": computed.result_truncated,
            "caveats": computed.insight.caveats,
        },
        ensure_ascii=False,
    )
    return system, user


def explain_result(
    question: str, plan: AnalysisPlan, computed, client: LLMClient
) -> tuple[str, bool, str | None]:
    system, user = _explanation_prompt(question, plan, computed)
    try:
        answer = str(_json_object(client.complete(system, user)).get("answer", ""))
    except LLMError as error:
        return computed.insight.message, False, str(error)
    grounded = verify(answer, computed.insight)
    if grounded is None:
        return (
            computed.insight.message,
            False,
            "The generated explanation was rejected because its numbers or causal claims were not verified.",
        )
    return grounded, True, None


def ask_question(
    store: DatasetStore,
    stored: StoredDataset,
    frame: pd.DataFrame,
    question: str,
    use_ai: bool,
    client: LLMClient | None = None,
) -> QuestionResponse:
    question = question.strip()
    if not question:
        return QuestionResponse.refused(stored.dataset_id, question, "Type a question first.")
    if not use_ai:
        return QuestionResponse.refused(
            stored.dataset_id,
            question,
            "Turn on AI to use Ask Your Data. No model was called.",
        )
    client = client or default_client()
    if client is None:
        return QuestionResponse.refused(
            stored.dataset_id,
            question,
            "Ask Your Data needs a configured model API key.",
        )
    if CAUSAL_QUESTION.search(question):
        return QuestionResponse.refused(
            stored.dataset_id,
            question,
            "This dataset can show patterns and associations, but it cannot establish why something happened.",
        )

    with question_lock(stored.dataset_id, question):
        return _ask_enabled_question(store, stored, frame, question, client)


def _ask_enabled_question(
    store: DatasetStore,
    stored: StoredDataset,
    frame: pd.DataFrame,
    question: str,
    client: LLMClient,
) -> QuestionResponse:

    turns = store.conversation(stored)
    resolved = resolve_follow_up(question, turns)
    cached = next(
        (
            turn.get("response")
            for turn in reversed(turns)
            if turn.get("question") == question and turn.get("resolved_question") == resolved
        ),
        None,
    )
    if cached is not None:
        return QuestionResponse.model_validate(cached)

    try:
        envelope = plan_question(resolved, stored.profile, turns, client)
    except LLMError as error:
        return QuestionResponse.refused(stored.dataset_id, question, str(error))
    if envelope.refusal is not None:
        return QuestionResponse.refused(stored.dataset_id, question, envelope.refusal)

    plan = envelope.plan
    assert plan is not None
    try:
        computed = execute_plan(frame, stored.profile, plan)
    except PlanRefused as error:
        return QuestionResponse.refused(stored.dataset_id, question, str(error))

    answer, explained, explanation_reason = explain_result(question, plan, computed, client)
    response = QuestionResponse(
        dataset_id=stored.dataset_id,
        question=question,
        status="answered",
        plan=plan,
        insight=computed.insight,
        chart=computed.chart,
        rows=computed.rows,
        result_truncated=computed.result_truncated,
        answer=answer,
        explained=explained,
        explanation_reason=explanation_reason,
    )
    store.remember_question(
        stored,
        {
            "question": question,
            "resolved_question": resolved,
            "plan": plan.model_dump(mode="json"),
            "reference_values": computed.reference_values,
            "response": response.model_dump(mode="json"),
        },
    )
    return response
