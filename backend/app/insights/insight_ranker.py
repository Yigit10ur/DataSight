from app.insights.models import Insight, InsightType

# What each kind of finding is worth when it is equally strong and equally certain.
# A difference between groups or a movement over time tells a reader something about
# their subject; a skewed column tells them something about their file.
TYPE_WEIGHTS: dict[InsightType, float] = {
    "group_difference": 1.00,
    "trend": 1.00,
    "correlation": 0.95,
    "sudden_change": 0.90,
    "seasonality": 0.85,
    "missing_data": 0.80,
    "outliers": 0.70,
    "dominant_category": 0.60,
    "skewed_distribution": 0.50,
    "rare_categories": 0.40,
}

# Rows at which a finding is trusted half as much as an arbitrarily large sample.
# A curve rather than a cutoff, so that 49 rows and 51 rows are not treated as
# different kinds of evidence.
HALF_RELIABILITY_ROWS = 50

MAX_PER_TYPE = 3
MAX_INSIGHTS = 15

# Pairs that describe one phenomenon from two sides. A column with a long tail has
# extreme values by definition, and a series that steps up once has risen.
REDUNDANT_TYPES: dict[InsightType, set[InsightType]] = {
    "trend": {"sudden_change"},
    "sudden_change": {"trend"},
    "outliers": {"skewed_distribution"},
    "skewed_distribution": {"outliers"},
    "dominant_category": {"rare_categories"},
    "rare_categories": {"dominant_category"},
}


def reliability(sample_size: int) -> float:
    """How far a finding can be trusted given how many rows it rests on."""
    if sample_size <= 0:
        return 0.0
    return sample_size / (sample_size + HALF_RELIABILITY_ROWS)


def score_importance(insight: Insight) -> float:
    """How large, how certain, how well evidenced, and how interesting the finding is."""
    return (
        insight.strength
        * insight.confidence
        * reliability(insight.sample_size)
        * TYPE_WEIGHTS[insight.insight_type]
    )


def _describes_the_same_thing(insight: Insight, kept: Insight) -> bool:
    return kept.insight_type in REDUNDANT_TYPES.get(insight.insight_type, set()) and set(
        kept.columns
    ) == set(insight.columns)


def rank_insights(insights: list[Insight]) -> list[Insight]:
    """Order the findings, drop the ones that repeat each other, and keep the top.

    Everything here works on the scores already attached to each finding, so the
    order is a property of the data and not of the order the generator happened to
    produce them in.
    """
    for insight in insights:
        insight.importance = score_importance(insight)

    ordered = sorted(insights, key=lambda insight: (-insight.importance, insight.id))

    kept: list[Insight] = []
    per_type: dict[InsightType, int] = {}
    # Columns already accounted for by a stronger relationship.
    related: set[str] = set()

    for insight in ordered:
        if per_type.get(insight.insight_type, 0) >= MAX_PER_TYPE:
            continue
        if any(_describes_the_same_thing(insight, other) for other in kept):
            continue
        if insight.insight_type == "correlation":
            # Correlation travels: if a and b move together and b and c move together,
            # a and c will too. Only a pair that brings in a column no stronger pair
            # has covered says something new.
            if all(column in related for column in insight.columns):
                continue
            related.update(insight.columns)

        kept.append(insight)
        per_type[insight.insight_type] = per_type.get(insight.insight_type, 0) + 1
        if len(kept) >= MAX_INSIGHTS:
            break

    return kept
