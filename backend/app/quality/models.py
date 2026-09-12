from typing import Any, Literal

from pydantic import BaseModel

IssueType = Literal[
    "missing_values",
    "empty_column",
    "duplicate_rows",
    "outliers",
    "constant_column",
    "high_cardinality",
    "identifier_column",
    "suspicious_categories",
    "inconsistent_formatting",
    "mistyped_column",
]

Severity = Literal["info", "warning", "serious"]

SEVERITY_ORDER: dict[Severity, int] = {"serious": 0, "warning": 1, "info": 2}


class QualityIssue(BaseModel):
    id: str
    issue_type: IssueType
    severity: Severity
    columns: list[str]
    message: str
    metrics: dict[str, Any]


class QualityReport(BaseModel):
    dataset_id: str
    issues: list[QualityIssue]
