from typing import Any, Literal

from pydantic import BaseModel

InsightType = Literal[
    "correlation",
    "group_difference",
    "trend",
    "seasonality",
    "sudden_change",
    "outliers",
    "skewed_distribution",
    "dominant_category",
    "rare_categories",
    "missing_data",
    "aggregate",
    "ranking",
    "count",
    "description",
]


class Insight(BaseModel):
    """One finding, in the structured form of section 18.

    Every number in `message` is also in `metrics`. That is what makes the finding
    checkable: the sentence is a rendering of the numbers, never a claim beside
    them, and the explanation layer later gets the metrics rather than the prose.
    """

    id: str
    insight_type: InsightType
    columns: list[str]
    message: str
    metrics: dict[str, Any]
    # How large this effect is on its own terms, rescaled to 0-1 so that findings
    # of different types can be compared at all. Turning it into a position in a
    # list is the ranker's job, not this one's.
    strength: float
    # How much the numbers behind this finding can be leaned on, separately from how
    # large the effect is. Caveats say the same thing to the reader in prose; this
    # says it to the ranker, which cannot read prose.
    confidence: float
    sample_size: int
    caveats: list[str]
    chart_id: str | None
    # Position in the list is decided by the ranker, from the three fields above
    # together with what kind of finding this is. Zero until it has run.
    importance: float = 0.0


class InsightCollection(BaseModel):
    dataset_id: str
    insights: list[Insight]
