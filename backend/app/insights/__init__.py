from app.analysis.models import DatasetAnalysis
from app.insights.insight_generator import generate_insights
from app.insights.insight_ranker import rank_insights, score_importance
from app.insights.models import Insight, InsightCollection, InsightType
from app.profiling.models import DatasetProfile
from app.provenance import Provenance
from app.quality.models import QualityReport
from app.visualization.models import ChartSpec

__all__ = [
    "Insight",
    "InsightCollection",
    "InsightType",
    "build_insights",
    "generate_insights",
    "rank_insights",
    "score_importance",
]


def build_insights(
    profile: DatasetProfile,
    analysis: DatasetAnalysis,
    quality: QualityReport,
    charts: list[ChartSpec],
    provenance: Provenance | None = None,
) -> InsightCollection:
    """Find everything worth saying about the dataset, most important first."""
    found = generate_insights(profile, analysis, quality, charts, provenance)
    return InsightCollection(dataset_id=analysis.dataset_id, insights=rank_insights(found))
