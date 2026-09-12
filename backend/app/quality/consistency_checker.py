import re
import unicodedata
from collections import defaultdict

import pandas as pd

from app.profiling.models import ColumnSchema
from app.quality.models import QualityIssue

MAX_CHECKED_CATEGORIES = 500
MAX_REPORTED_GROUPS = 3
MISTYPED_NUMERIC_RATIO = 0.8
WHITESPACE_PATTERN = re.compile(r"^\s|\s$|\s{2,}")


def normalise_category(value: str) -> str:
    """Fold case, accents and spacing so spellings of one category collapse together.

    Turkish dotted capitals are the motivating case: "İstanbul", "Istanbul" and
    "istanbul" are one city, but casefold alone keeps the combining dot and
    leaves them as three distinct values.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_marks).strip().casefold()


def detect_suspicious_categories(series: pd.Series, schema: ColumnSchema) -> QualityIssue | None:
    """Find distinct category values that are probably the same category."""
    values = series.dropna().astype(str).unique()
    if len(values) > MAX_CHECKED_CATEGORIES:
        return None

    groups: dict[str, list[str]] = defaultdict(list)
    for value in values:
        groups[normalise_category(value)].append(value)

    collisions = [variants for variants in groups.values() if len(variants) > 1]
    if not collisions:
        return None

    examples = ", ".join(
        " / ".join(f'"{variant}"' for variant in variants)
        for variants in collisions[:MAX_REPORTED_GROUPS]
    )
    return QualityIssue(
        id=f"suspicious_categories__{schema.name}",
        issue_type="suspicious_categories",
        severity="warning",
        columns=[schema.name],
        message=(
            f"{schema.name} has {len(collisions)} group(s) of values that differ only in case, "
            f"accents or spacing and may be the same category: {examples}."
        ),
        metrics={"group_count": len(collisions), "groups": collisions[:MAX_REPORTED_GROUPS]},
    )


def detect_inconsistent_formatting(series: pd.Series, schema: ColumnSchema) -> QualityIssue | None:
    """Find values carrying stray whitespace, which silently splits categories."""
    values = series.dropna().astype(str)
    affected = int(values.str.contains(WHITESPACE_PATTERN, regex=True).sum())
    if affected == 0:
        return None

    return QualityIssue(
        id=f"inconsistent_formatting__{schema.name}",
        issue_type="inconsistent_formatting",
        severity="warning",
        columns=[schema.name],
        message=(
            f"{affected} value(s) in {schema.name} have leading, trailing or repeated whitespace."
        ),
        metrics={"affected_rows": affected},
    )


def detect_mistyped_column(series: pd.Series, schema: ColumnSchema) -> QualityIssue | None:
    """Find text columns that actually hold numbers, so they never reach numeric analysis."""
    if schema.inferred_type not in {"categorical", "text"}:
        return None

    values = series.dropna()
    if values.empty:
        return None

    numeric_ratio = pd.to_numeric(values, errors="coerce").notna().mean()
    if numeric_ratio < MISTYPED_NUMERIC_RATIO:
        return None

    return QualityIssue(
        id=f"mistyped_column__{schema.name}",
        issue_type="mistyped_column",
        severity="warning",
        columns=[schema.name],
        message=(
            f"{schema.name} is stored as text but {numeric_ratio:.0%} of its values are numeric, "
            "so it is excluded from numeric analysis."
        ),
        metrics={"numeric_ratio": float(numeric_ratio)},
    )


def check_consistency(frame: pd.DataFrame, schemas: list[ColumnSchema]) -> list[QualityIssue]:
    issues: list[QualityIssue] = []

    for schema in schemas:
        if schema.inferred_type not in {"categorical", "text", "boolean"}:
            continue

        series = frame[schema.name]
        candidates = [
            detect_mistyped_column(series, schema),
            detect_suspicious_categories(series, schema),
            detect_inconsistent_formatting(series, schema),
        ]
        issues.extend(issue for issue in candidates if issue is not None)

    return issues
