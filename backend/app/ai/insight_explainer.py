import json

from app.ai.llm_client import LLMClient, LLMError, default_client
from app.ai.models import Explanation, ExplanationCollection
from app.ai.prompt_builder import build_prompt
from app.ai.verification import causal_claims, untraceable_numbers
from app.config import settings
from app.insights.models import Insight
from app.profiling.models import DatasetProfile

NO_KEY_REASON = "No model API key is configured, so findings are shown as computed."

# Explanations of the same findings never change, and every call costs money.
_cache: dict[tuple[str, ...], list[Explanation]] = {}


def _parse(text: str) -> dict[str, str]:
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
    return {str(key): str(value) for key, value in parsed.items()}


def verify(text: str, insight: Insight) -> str | None:
    """Return the explanation if it is grounded, or nothing if it is not.

    An explanation is rejected whole rather than trimmed. A sentence removed from
    the middle of a paragraph leaves prose that reads as if it still makes its
    original point, which is worse than saying nothing.
    """
    if not text.strip():
        return None
    if untraceable_numbers(text, insight.metrics, insight.columns):
        return None
    if causal_claims(text):
        return None
    return text.strip()


def explain_insights(
    profile: DatasetProfile,
    insights: list[Insight],
    client: LLMClient | None = None,
) -> ExplanationCollection:
    """Ask a model to say what the findings mean, and keep only what checks out."""
    dataset_id = profile.dataset_id
    explained = insights[: settings.explanation_max_insights]

    if not explained:
        return ExplanationCollection(
            dataset_id=dataset_id, available=True, reason=None, explanations=[]
        )

    client = client or default_client()
    if client is None:
        return ExplanationCollection(
            dataset_id=dataset_id, available=False, reason=NO_KEY_REASON, explanations=[]
        )

    key = (dataset_id, *(insight.id for insight in explained))
    if key in _cache:
        return ExplanationCollection(
            dataset_id=dataset_id, available=True, reason=None, explanations=_cache[key]
        )

    system, user = build_prompt(profile, explained)
    try:
        answers = _parse(client.complete(system, user))
    except LLMError as error:
        return ExplanationCollection(
            dataset_id=dataset_id, available=False, reason=str(error), explanations=[]
        )

    explanations = []
    for insight in explained:
        verified = verify(answers.get(insight.id, ""), insight)
        if verified is not None:
            explanations.append(Explanation(insight_id=insight.id, text=verified))

    _cache[key] = explanations
    return ExplanationCollection(
        dataset_id=dataset_id, available=True, reason=None, explanations=explanations
    )


def clear_cache() -> None:
    _cache.clear()
