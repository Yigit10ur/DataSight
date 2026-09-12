import pandas as pd

from app.analysis.categorical_analysis import analyze_categorical
from app.analysis.correlation_analysis import analyze_correlations
from app.analysis.datetime_analysis import analyze_timeline, build_timelines
from app.analysis.group_analysis import MAX_GROUP_COUNT, analyze_groups, compare_groups
from app.analysis.models import (
    CategoricalSummary,
    CorrelationPair,
    DatasetAnalysis,
    GroupComparison,
    NumericSummary,
    Timeline,
)
from app.analysis.numeric_analysis import analyze_numeric
from app.profiling.models import DatasetProfile

__all__ = [
    "CategoricalSummary",
    "CorrelationPair",
    "DatasetAnalysis",
    "GroupComparison",
    "NumericSummary",
    "Timeline",
    "analyze_categorical",
    "analyze_correlations",
    "analyze_dataset",
    "analyze_groups",
    "analyze_numeric",
    "analyze_timeline",
    "build_timelines",
    "compare_groups",
]


def analyze_dataset(frame: pd.DataFrame, profile: DatasetProfile) -> DatasetAnalysis:
    """Run the type-appropriate analysis for every analysable column."""
    # Identifiers are unique by construction, so their statistics describe nothing.
    analysable = [column for column in profile.column_schemas if not column.is_probable_id]

    numeric_columns = [column.name for column in analysable if column.inferred_type == "numeric"]
    categorical_columns = [
        column.name for column in analysable if column.inferred_type in {"categorical", "boolean"}
    ]
    datetime_columns = [column.name for column in analysable if column.inferred_type == "datetime"]

    categorical = [analyze_categorical(frame[column]) for column in categorical_columns]
    # Too many groups and a comparison stops being a comparison; the reader cannot
    # hold twenty group means side by side, and neither can a single sentence.
    group_columns = [
        summary.column for summary in categorical if 2 <= summary.unique_count <= MAX_GROUP_COUNT
    ]

    return DatasetAnalysis(
        dataset_id=profile.dataset_id,
        numeric=[analyze_numeric(frame[column]) for column in numeric_columns],
        categorical=categorical,
        correlations=analyze_correlations(frame, numeric_columns),
        groups=compare_groups(frame, group_columns, numeric_columns),
        timelines=build_timelines(frame, datetime_columns, numeric_columns),
    )
