import json
import threading

from app.ai.llm_client import LLMClient, LLMError, default_client
from app.ai.models import Explanation, ExplanationCollection
from app.ai.prompt_builder import build_prompt
from app.ai.verification import causal_claims, merge_metrics, untraceable_numbers
from app.config import settings
from app.insights.models import Insight
from app.profiling.models import DatasetProfile
from app.quality.models import QualityScore

NO_KEY_REASON = "No model API key is configured, so findings are shown as computed."

# Explanations of the same findings never change, and every call costs money.
_cache: dict[tuple[str, ...], tuple[str | None, list[Explanation]]] = {}

# One lock per set of findings, so a second request for the same explanations waits
# for the first rather than paying for it again. Checking the cache without one is
# only safe while requests arrive apart: React mounts an effect twice in
# development and sends exactly that overlapping pair, and so do two open tabs.
_locks: dict[tuple[str, ...], threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(key: tuple[str, ...]) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def _unavailable(dataset_id: str, reason: str) -> ExplanationCollection:
    return ExplanationCollection(
        dataset_id=dataset_id,
        available=False,
        reason=reason,
        summary=None,
        explanations=[],
    )


def _parse(text: str) -> tuple[str, dict[str, str]]:
    """Read the model's JSON, tolerating a code fence around it."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        cleaned = cleaned.removeprefix("json").strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise LLMError(f"The model did not answer with JSON: {error}") from error

    if not isinstance(parsed, dict):
        raise LLMError("The model answered with something other than an object.")

    explanations = parsed.get("explanations", {})
    if not isinstance(explanations, dict):
        raise LLMError("The model did not return an object of explanations.")

    return str(parsed.get("summary", "")), {
        str(key): str(value) for key, value in explanations.items()
    }


def _grounded(text: str, metrics: dict, columns: list[str]) -> str | None:
    """Return the text if every quantity in it came from the analysis, else nothing.

    Rejected whole rather than trimmed. A sentence removed from the middle of a
    paragraph leaves prose that reads as if it still makes its original point,
    which is worse than saying nothing.
    """
    if not text.strip():
        return None
    if untraceable_numbers(text, metrics, columns):
        return None
    if causal_claims(text):
        return None
    return text.strip()


def shown_metrics(insight: Insight) -> dict:
    """Every number the prompt put in front of the model for one finding.

    The payload carries rows_behind_it for every finding, but only some types
    repeat it inside metrics. Checking against metrics alone rejected a model
    that quoted a number the prompt had handed it.

    Keyed under the payload's own name so it sits beside a metrics["sample_size"]
    instead of overwriting it: both were shown, so both have to verify.
    """
    return {**insight.metrics, "rows_behind_it": insight.sample_size}


def dataset_metrics(profile: DatasetProfile, score: QualityScore) -> dict:
    """The file's own facts, which the prompt shows above every finding."""
    return {
        "rows": profile.rows,
        "columns": profile.columns,
        "missing_ratio": profile.missing_ratio,
        "duplicate_rows": profile.duplicate_rows,
        "score": score.score,
        "out_of": 100,
        **{dimension.name: dimension.score for dimension in score.dimensions},
    }


def verify(text: str, insight: Insight, dataset: dict | None = None) -> str | None:
    """Check one explanation against every number the prompt showed for it.

    The dataset facts belong in the pool because the payload puts them in front
    of the model too: "342 of the 360 rows" quotes the finding's own sample size
    and the file's row count, and only one of them used to be checkable.
    """
    shown = {
        **{f"dataset.{name}": value for name, value in (dataset or {}).items()},
        **shown_metrics(insight),
    }
    return _grounded(text, shown, insight.columns)


def verify_summary(
    text: str, profile: DatasetProfile, score: QualityScore, insights: list[Insight]
) -> str | None:
    """Check the paragraph against everything it was allowed to draw on."""
    metrics = merge_metrics(
        [shown_metrics(insight) for insight in insights],
        dataset_metrics(profile, score),
    )
    columns = [schema.name for schema in profile.column_schemas]
    return _grounded(text, metrics, columns)


def explain_insights(
    profile: DatasetProfile,
    score: QualityScore,
    insights: list[Insight],
    client: LLMClient | None = None,
) -> ExplanationCollection:
    """Ask a model to say what the findings mean, and keep only what checks out."""
    dataset_id = profile.dataset_id
    explained = insights[: settings.explanation_max_insights]

    client = client or default_client()
    if client is None:
        return _unavailable(dataset_id, NO_KEY_REASON)

    key = (dataset_id, *(insight.id for insight in explained))
    with _lock_for(key):
        if key not in _cache:
            system, user = build_prompt(profile, score, explained)
            try:
                summary, answers = _parse(client.complete(system, user))
            except LLMError as error:
                return _unavailable(dataset_id, str(error))

            dataset = dataset_metrics(profile, score)
            verified = [
                Explanation(insight_id=insight.id, text=text)
                for insight in explained
                if (text := verify(answers.get(insight.id, ""), insight, dataset))
                is not None
            ]
            _cache[key] = (verify_summary(summary, profile, score, explained), verified)

    summary, explanations = _cache[key]
    return ExplanationCollection(
        dataset_id=dataset_id,
        available=True,
        reason=None,
        summary=summary,
        explanations=explanations,
    )


def clear_cache() -> None:
    _cache.clear()
    with _locks_guard:
        _locks.clear()
