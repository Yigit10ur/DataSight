import re

from app.insights.formatting import multiple, number, percent

# Numbers as they appear in prose: 1,240.5 / 15.1% / 2.4x
NUMBER_PATTERN = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?[%x]?")
SENTENCE_PATTERN = re.compile(r"[^.!?]+[.!?]?")

# Renderings a faithful writer might choose for the same measured value. Rounding
# is allowed because a rounded number is still the number; inventing a different
# one is not.
NUMBER_FORMATS = (
    "{:.0f}",
    "{:.1f}",
    "{:.2f}",
    "{:,.0f}",
    "{:,.1f}",
    "{:,.2f}",
    "{:.0%}",
    "{:.1%}",
)

CAUSAL_PHRASES = (
    "cause",
    "causes",
    "caused",
    "causing",
    "leads to",
    "led to",
    "drives",
    "driving",
    "driven by",
    "results in",
    "resulting in",
    "because of",
    "due to",
    "thanks to",
    "the reason for",
)

# A sentence that denies causation is the sentence we asked for, not the one we
# are guarding against.
NEGATIONS = ("not", "n't", "never", "no evidence", "cannot", "rather than", "without")


def renderings(metrics: dict) -> set[str]:
    """Every way a metric value could honestly be written."""
    written: set[str] = set()

    for value in metrics.values():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        written.update({str(value), number(value), percent(value), multiple(value)})
        for template in NUMBER_FORMATS:
            try:
                written.add(template.format(value))
            except (ValueError, TypeError):
                continue

    # 1,240 and 1240 are the same number written two ways.
    return written | {written_value.replace(",", "") for written_value in written}


def untraceable_numbers(text: str, metrics: dict, columns: list[str]) -> set[str]:
    """Numbers in the text that no metric accounts for.

    An empty result means every quantity in the sentence came from the analysis
    engine. Anything else is a number the writer produced on its own, which is
    exactly the failure this project is built to avoid.
    """
    remaining = text
    for value in metrics.values():
        if isinstance(value, str):
            remaining = remaining.replace(value, " ")
    for column in columns:
        remaining = remaining.replace(column, " ")

    printed = set(NUMBER_PATTERN.findall(remaining))
    return printed - renderings(metrics)


def causal_claims(text: str) -> list[str]:
    """Sentences that assert one column acts on another."""
    claims = []

    for sentence in SENTENCE_PATTERN.findall(text):
        lowered = sentence.lower()
        if not any(phrase in lowered for phrase in CAUSAL_PHRASES):
            continue
        if any(negation in lowered for negation in NEGATIONS):
            continue
        claims.append(sentence.strip())

    return claims


def merge_metrics(metric_sets: list[dict], extra: dict) -> dict:
    """One pool of values for checking a sentence that draws on several findings.

    Keys are namespaced because findings reuse names like "count"; only the values
    matter to the check, but a collision would quietly drop one of them.
    """
    merged = dict(extra)
    for position, metrics in enumerate(metric_sets):
        for key, value in metrics.items():
            merged[f"{position}.{key}"] = value
    return merged
