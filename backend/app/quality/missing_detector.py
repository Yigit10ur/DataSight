from app.profiling.models import ColumnSchema
from app.quality.models import QualityIssue, Severity

SERIOUS_MISSING_RATIO = 0.5
WARNING_MISSING_RATIO = 0.1
REPORTABLE_MISSING_RATIO = 0.01


def _severity(ratio: float) -> Severity:
    if ratio >= SERIOUS_MISSING_RATIO:
        return "serious"
    if ratio >= WARNING_MISSING_RATIO:
        return "warning"
    return "info"


def detect_missing_values(schemas: list[ColumnSchema]) -> list[QualityIssue]:
    """Report columns with enough missing values to affect an analysis."""
    issues: list[QualityIssue] = []

    for schema in schemas:
        if schema.inferred_type == "empty":
            issues.append(
                QualityIssue(
                    id=f"empty_column__{schema.name}",
                    issue_type="empty_column",
                    severity="serious",
                    columns=[schema.name],
                    message=f"{schema.name} has no values at all.",
                    metrics={"missing_count": schema.missing_count},
                )
            )
        elif schema.missing_ratio >= REPORTABLE_MISSING_RATIO:
            issues.append(
                QualityIssue(
                    id=f"missing_values__{schema.name}",
                    issue_type="missing_values",
                    severity=_severity(schema.missing_ratio),
                    columns=[schema.name],
                    message=(
                        f"{schema.name} is missing {schema.missing_ratio:.1%} of its values "
                        f"({schema.missing_count} rows)."
                    ),
                    metrics={
                        "missing_count": schema.missing_count,
                        "missing_ratio": schema.missing_ratio,
                    },
                )
            )

    return issues
