from collections import defaultdict

from app.profiling.models import ColumnSchema, DatasetProfile
from app.provenance import Provenance
from app.quality.models import (
    DimensionName,
    QualityDimension,
    QualityIssue,
    QualityScore,
    ScoreContribution,
)

LABELS: dict[DimensionName, str] = {
    "completeness": "Completeness",
    "consistency": "Consistency",
    "duplicates": "Duplicate score",
    "outliers": "Outlier score",
    "type_consistency": "Type consistency",
}

# The share at which a dimension reaches zero. The three dimensions measured over
# cells or columns share a tolerance of one half: a dataset missing half its cells,
# or holding half its columns in the wrong shape, is not a dataset. Duplicates and
# outliers are measured over rows and values, where a much smaller share already
# means something is wrong — but a fifth of the numbers being extreme is unusual
# rather than broken, so outliers get the widest room of the two.
TOLERANCES: dict[DimensionName, float] = {
    "completeness": 0.5,
    "consistency": 0.5,
    "type_consistency": 0.5,
    "duplicates": 0.3,
    "outliers": 0.2,
}

# Missing values corrupt every later calculation, so they weigh most. Outliers
# weigh least: they are often the most interesting rows in the file, not errors.
WEIGHTS: dict[DimensionName, float] = {
    "completeness": 0.30,
    "consistency": 0.20,
    "type_consistency": 0.20,
    "duplicates": 0.15,
    "outliers": 0.15,
}

GAPS_SHAPED_CAVEAT = (
    "The gaps in this dataset were filled or dropped on the way here, so completeness "
    "describes the recipe as much as the data."
)
ROWS_REMOVED_CAVEAT = (
    "Rows were removed on the way here, so this scores what is left rather than the "
    "file it came from."
)
GROUPED_ROWS_SCORE_CAVEAT = (
    "Each row here is one group rather than one record, so a perfect duplicate score "
    "is what grouping produces rather than something the data earned."
)

CONSISTENCY_TYPES = {"categorical", "text", "boolean"}
CONSISTENCY_ISSUES = {"suspicious_categories", "inconsistent_formatting"}


def _dimension(
    name: DimensionName,
    observed: float,
    applicable: bool,
    contributions: list[ScoreContribution],
) -> QualityDimension:
    tolerance = TOLERANCES[name]
    reached = min(observed / tolerance, 1.0) if applicable else 0.0

    return QualityDimension(
        name=name,
        label=LABELS[name],
        score=round(100 * (1 - reached)) if applicable else 0,
        weight=0.0,
        observed=observed,
        tolerance=tolerance,
        applicable=applicable,
        contributions=contributions,
    )


def _completeness(
    profile: DatasetProfile, by_type: dict[str, list[QualityIssue]]
) -> QualityDimension:
    cells = profile.rows * profile.columns
    reported = [*by_type["missing_values"], *by_type["empty_column"]]

    return _dimension(
        name="completeness",
        # The dataset-level ratio, not the sum of the contributions below: columns
        # missing less than the reporting floor still count against the score.
        observed=profile.missing_ratio,
        applicable=cells > 0,
        contributions=[
            ScoreContribution(
                columns=issue.columns,
                issue_ids=[issue.id],
                share=issue.metrics["missing_count"] / cells,
            )
            for issue in reported
        ],
    )


def _duplicates(
    profile: DatasetProfile, by_type: dict[str, list[QualityIssue]]
) -> QualityDimension:
    issues = by_type["duplicate_rows"]

    return _dimension(
        name="duplicates",
        observed=profile.duplicate_rows / profile.rows if profile.rows else 0.0,
        applicable=profile.rows > 0,
        contributions=[
            ScoreContribution(
                columns=[],
                issue_ids=[issue.id],
                share=issue.metrics["duplicate_ratio"],
            )
            for issue in issues
        ],
    )


def _outliers(
    profile: DatasetProfile, schemas: list[ColumnSchema], by_type: dict[str, list[QualityIssue]]
) -> QualityDimension:
    numeric = [
        schema
        for schema in schemas
        if schema.inferred_type == "numeric" and not schema.is_probable_id
    ]
    values = sum(profile.rows - schema.missing_count for schema in numeric)
    issues = by_type["outliers"]
    flagged = sum(issue.metrics["outlier_count"] for issue in issues)

    return _dimension(
        name="outliers",
        observed=flagged / values if values else 0.0,
        # Nothing to measure without numbers; a text-only file is not outlier-free,
        # it is outside the question.
        applicable=bool(numeric) and values > 0,
        contributions=[
            ScoreContribution(
                columns=issue.columns,
                issue_ids=[issue.id],
                share=issue.metrics["outlier_count"] / values,
            )
            for issue in issues
        ],
    )


def _consistency(
    schemas: list[ColumnSchema], by_type: dict[str, list[QualityIssue]]
) -> QualityDimension:
    candidates = [schema for schema in schemas if schema.inferred_type in CONSISTENCY_TYPES]
    issues = [issue for name in CONSISTENCY_ISSUES for issue in by_type[name]]

    # Measured per column rather than per issue: one column with both stray
    # whitespace and mixed spellings is one inconsistent column, not two.
    by_column: dict[str, list[str]] = defaultdict(list)
    for issue in issues:
        for column in issue.columns:
            by_column[column].append(issue.id)

    share = 1 / len(candidates) if candidates else 0.0
    return _dimension(
        name="consistency",
        observed=len(by_column) * share,
        applicable=bool(candidates),
        contributions=[
            ScoreContribution(columns=[column], issue_ids=issue_ids, share=share)
            for column, issue_ids in by_column.items()
        ],
    )


def _type_consistency(
    profile: DatasetProfile, by_type: dict[str, list[QualityIssue]]
) -> QualityDimension:
    issues = by_type["mistyped_column"]
    share = 1 / profile.columns if profile.columns else 0.0

    return _dimension(
        name="type_consistency",
        observed=len(issues) * share,
        applicable=profile.columns > 0,
        contributions=[
            ScoreContribution(columns=issue.columns, issue_ids=[issue.id], share=share)
            for issue in issues
        ],
    )


def score_dataset(
    profile: DatasetProfile,
    issues: list[QualityIssue],
    provenance: Provenance | None = None,
) -> QualityScore:
    """Rate the dataset out of 100 along the five dimensions of section 8.

    The score is a pure function of the profile and the issues already reported,
    so it can never disagree with the list the reader sees next to it. Structural
    notes — constant columns, identifiers, high cardinality — are deliberately not
    scored: they describe what a column is, not whether it is damaged.

    A shaped dataset is scored exactly the same way and then told on. A recipe that
    drops every row with a gap earns a hundred for completeness, which is true and
    useless; changing the number would be pretending the data is worse than it is,
    so the number stands and the reason it is high is written next to it.
    """
    by_type: dict[str, list[QualityIssue]] = defaultdict(list)
    for issue in issues:
        by_type[issue.issue_type].append(issue)

    schemas = profile.column_schemas
    dimensions = [
        _completeness(profile, by_type),
        _consistency(schemas, by_type),
        _type_consistency(profile, by_type),
        _duplicates(profile, by_type),
        _outliers(profile, schemas, by_type),
    ]

    # A dimension with nothing to measure hands its weight to the others rather
    # than scoring a free 100 and lifting the total.
    measurable = [dimension for dimension in dimensions if dimension.applicable]
    total_weight = sum(WEIGHTS[dimension.name] for dimension in measurable)
    for dimension in dimensions:
        dimension.weight = WEIGHTS[dimension.name] / total_weight if dimension.applicable else 0.0

    overall = sum(dimension.score * dimension.weight for dimension in measurable)
    shaped = provenance or Provenance()
    caveats = [
        *([GAPS_SHAPED_CAVEAT] if shaped.gaps_were_shaped else []),
        # Grouping removes rows too, and says so better: "each row is a group" is the
        # reason these numbers look the way they do, and repeating the weaker version
        # underneath it would only crowd the stronger one.
        *(
            [GROUPED_ROWS_SCORE_CAVEAT]
            if shaped.rows_are_groups
            else [ROWS_REMOVED_CAVEAT]
            if shaped.rows_were_removed
            else []
        ),
    ]

    return QualityScore(
        dataset_id=profile.dataset_id,
        score=round(overall) if total_weight else 0,
        dimensions=dimensions,
        caveats=caveats,
    )
