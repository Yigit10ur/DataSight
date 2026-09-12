import pandas as pd

from app.analysis.models import DatasetAnalysis
from app.profiling.models import DatasetProfile
from app.visualization.chart_selector import select_charts
from app.visualization.models import ChartCollection, ChartSpec, ChartType

__all__ = ["ChartCollection", "ChartSpec", "ChartType", "build_charts", "select_charts"]


def build_charts(
    frame: pd.DataFrame, profile: DatasetProfile, analysis: DatasetAnalysis
) -> ChartCollection:
    return ChartCollection(
        dataset_id=profile.dataset_id,
        charts=select_charts(frame, analysis),
    )
