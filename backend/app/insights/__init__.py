from app.analysis.models import DatasetAnalysis
from app.insights.insight_generator import generate_insights
from app.insights.models import Insight, InsightCollection, InsightType
from app.quality.models import QualityReport
from app.visualization.models import ChartSpec

__all__ = [
    "Insight",
    "InsightCollection",
    "InsightType",
    "build_insights",
    "generate_insights",
]


def build_insights(
    analysis: DatasetAnalysis, quality: QualityReport, charts: list[ChartSpec]
) -> InsightCollection:
    return InsightCollection(
        dataset_id=analysis.dataset_id,
        insights=generate_insights(analysis, quality, charts),
    )
