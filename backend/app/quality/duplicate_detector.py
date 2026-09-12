from app.profiling.models import DatasetProfile
from app.quality.models import QualityIssue

WARNING_DUPLICATE_RATIO = 0.05


def detect_duplicates(profile: DatasetProfile) -> list[QualityIssue]:
    """Report fully identical rows, which usually mean a broken join or a double import."""
    if profile.duplicate_rows == 0 or profile.rows == 0:
        return []

    ratio = profile.duplicate_rows / profile.rows
    return [
        QualityIssue(
            id="duplicate_rows",
            issue_type="duplicate_rows",
            severity="warning" if ratio >= WARNING_DUPLICATE_RATIO else "info",
            columns=[],
            message=(
                f"{profile.duplicate_rows} rows ({ratio:.1%}) are exact duplicates of another row."
            ),
            metrics={"duplicate_rows": profile.duplicate_rows, "duplicate_ratio": ratio},
        )
    ]
