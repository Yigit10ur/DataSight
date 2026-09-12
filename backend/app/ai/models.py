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
    # One paragraph about the dataset as a whole. Absent when the model was not
    # reached, and also when what it wrote could not be checked against the numbers.
    summary: str | None
    explanations: list[Explanation]
