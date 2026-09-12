from pydantic import BaseModel


class Explanation(BaseModel):
    insight_id: str
    text: str


class ExplanationCollection(BaseModel):
    dataset_id: str
    # False when no explanation could be produced at all: no key, or the call
    # failed. The dashboard keeps working either way, on the computed messages.
    available: bool
    reason: str | None
    explanations: list[Explanation]
