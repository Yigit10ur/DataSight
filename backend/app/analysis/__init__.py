import pandas as pd

from app.analysis.categorical_analysis import analyze_categorical
from app.analysis.correlation_analysis import analyze_correlations
from app.analysis.models import (
    CategoricalSummary,
    CorrelationPair,
    DatasetAnalysis,
    NumericSummary,
)
from app.analysis.numeric_analysis import analyze_numeric
from app.profiling.models import DatasetProfile

__all__ = [
    "CategoricalSummary",
    "CorrelationPair",
    "DatasetAnalysis",
    "NumericSummary",
    "analyze_categorical",
    "analyze_correlations",
    "analyze_dataset",
    "analyze_numeric",
]


def analyze_dataset(frame: pd.DataFrame, profile: DatasetProfile) -> DatasetAnalysis:
    """Run the type-appropriate analysis for every analysable column."""
    # Identifiers are unique by construction, so their statistics describe nothing.
    analysable = [column for column in profile.column_schemas if not column.is_probable_id]

    numeric_columns = [column.name for column in analysable if column.inferred_type == "numeric"]
    categorical_columns = [
        column.name for column in analysable if column.inferred_type in {"categorical", "boolean"}
    ]

    return DatasetAnalysis(
        dataset_id=profile.dataset_id,
        numeric=[analyze_numeric(frame[column]) for column in numeric_columns],
        categorical=[analyze_categorical(frame[column]) for column in categorical_columns],
        correlations=analyze_correlations(frame, numeric_columns),
    )
