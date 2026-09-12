import pandas as pd

from app.profiling.models import DatasetProfile
from app.quality.consistency_checker import check_consistency, normalise_category
from app.quality.duplicate_detector import detect_duplicates
from app.quality.missing_detector import detect_missing_values
from app.quality.models import SEVERITY_ORDER, QualityIssue, QualityReport, QualityScore
from app.quality.score import score_dataset
from app.quality.structure_detector import detect_outliers, detect_structural_issues

__all__ = [
    "QualityIssue",
    "QualityReport",
    "QualityScore",
    "check_dataset_quality",
    "normalise_category",
    "score_dataset",
]


def check_dataset_quality(frame: pd.DataFrame, profile: DatasetProfile) -> QualityReport:
    """Collect every quality problem found in the dataset, most severe first."""
    schemas = profile.column_schemas
    issues = [
        *detect_missing_values(schemas),
        *detect_duplicates(profile),
        *detect_outliers(frame, schemas),
        *check_consistency(frame, schemas),
        *detect_structural_issues(schemas),
    ]
    issues.sort(key=lambda issue: SEVERITY_ORDER[issue.severity])

    return QualityReport(
        dataset_id=profile.dataset_id,
        score=score_dataset(profile, issues),
        issues=issues,
    )
