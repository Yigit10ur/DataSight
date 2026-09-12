import pandas as pd

from app.analysis.numeric_analysis import count_iqr_outliers
from app.profiling.models import ColumnSchema
from app.quality.models import QualityIssue

WARNING_OUTLIER_RATIO = 0.05
REPORTABLE_OUTLIER_RATIO = 0.01


def detect_structural_issues(schemas: list[ColumnSchema]) -> list[QualityIssue]:
    """Report columns whose shape makes them unusable as features."""
    issues: list[QualityIssue] = []

    for schema in schemas:
        if schema.inferred_type == "empty":
            continue

        if schema.is_constant:
            issues.append(
                QualityIssue(
                    id=f"constant_column__{schema.name}",
                    issue_type="constant_column",
                    severity="info",
                    columns=[schema.name],
                    message=f"{schema.name} holds a single value for every row.",
                    metrics={"unique_count": schema.unique_count},
                )
            )
        if schema.is_probable_id:
            issues.append(
                QualityIssue(
                    id=f"identifier_column__{schema.name}",
                    issue_type="identifier_column",
                    severity="info",
                    columns=[schema.name],
                    message=(
                        f"{schema.name} looks like a row identifier and should probably not be "
                        "used as a feature."
                    ),
                    metrics={"unique_count": schema.unique_count},
                )
            )
        elif schema.is_high_cardinality:
            issues.append(
                QualityIssue(
                    id=f"high_cardinality__{schema.name}",
                    issue_type="high_cardinality",
                    severity="info",
                    columns=[schema.name],
                    message=(
                        f"{schema.name} has {schema.unique_count} distinct values, too many to "
                        "group or chart directly."
                    ),
                    metrics={"unique_count": schema.unique_count},
                )
            )

    return issues


def detect_outliers(frame: pd.DataFrame, schemas: list[ColumnSchema]) -> list[QualityIssue]:
    """Report numeric columns with an unusual share of values outside the Tukey fences."""
    issues: list[QualityIssue] = []

    for schema in schemas:
        if schema.inferred_type != "numeric" or schema.is_probable_id:
            continue

        values = pd.to_numeric(frame[schema.name], errors="coerce").dropna()
        if values.empty:
            continue

        count = count_iqr_outliers(values)
        ratio = count / len(values)
        if ratio < REPORTABLE_OUTLIER_RATIO:
            continue

        issues.append(
            QualityIssue(
                id=f"outliers__{schema.name}",
                issue_type="outliers",
                severity="warning" if ratio >= WARNING_OUTLIER_RATIO else "info",
                columns=[schema.name],
                message=(
                    f"{count} value(s) in {schema.name} ({ratio:.1%}) fall far outside the "
                    "interquartile range."
                ),
                metrics={
                    "outlier_count": count,
                    "outlier_ratio": ratio,
                    "minimum": float(values.min()),
                    "maximum": float(values.max()),
                },
            )
        )

    return issues
