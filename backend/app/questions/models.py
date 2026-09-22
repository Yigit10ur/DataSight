from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.insights.models import Insight
from app.recipes.models import AggregateFunction, FilterClause
from app.visualization.models import ChartSpec

MAX_QUESTION_LENGTH = 500
MAX_QUERY_FILTERS = 10
MAX_QUERY_GROUPS = 2
MAX_QUERY_LIMIT = 20


class PlanBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filters: list[FilterClause] = Field(default_factory=list, max_length=MAX_QUERY_FILTERS)


class AggregatePlan(PlanBase):
    operation: Literal["aggregate"] = "aggregate"
    measure: str | None = None
    function: AggregateFunction
    group_by: list[str] = Field(default_factory=list, max_length=MAX_QUERY_GROUPS)
    time_grain: Literal["day", "week", "month", "quarter", "year"] | None = None

    @model_validator(mode="after")
    def measure_for_function(self):
        if self.function != "count" and self.measure is None:
            raise ValueError(f"{self.function} needs a measure")
        return self


class RankPlan(PlanBase):
    operation: Literal["rank"] = "rank"
    measure: str | None = None
    function: AggregateFunction
    group_by: list[str] = Field(min_length=1, max_length=MAX_QUERY_GROUPS)
    order: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=5, ge=1, le=MAX_QUERY_LIMIT)
    time_grain: Literal["day", "week", "month", "quarter", "year"] | None = None

    @model_validator(mode="after")
    def measure_for_function(self):
        if self.function != "count" and self.measure is None:
            raise ValueError(f"{self.function} needs a measure")
        return self


class ComparePlan(PlanBase):
    operation: Literal["compare"] = "compare"
    measure: str
    group_by: str


class RelatePlan(PlanBase):
    operation: Literal["relate"] = "relate"
    measure: str
    secondary_measure: str


class TrendPlan(PlanBase):
    operation: Literal["trend"] = "trend"
    measure: str
    time: str


class DistributionPlan(PlanBase):
    operation: Literal["distribution"] = "distribution"
    column: str


class CountPlan(PlanBase):
    operation: Literal["count"] = "count"


class DescribePlan(PlanBase):
    operation: Literal["describe"] = "describe"
    column: str


AnalysisPlan = Annotated[
    AggregatePlan
    | RankPlan
    | ComparePlan
    | RelatePlan
    | TrendPlan
    | DistributionPlan
    | CountPlan
    | DescribePlan,
    Field(discriminator="operation"),
]


class PlanEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: AnalysisPlan | None = None
    refusal: str | None = None

    @model_validator(mode="after")
    def exactly_one_outcome(self):
        if (self.plan is None) == (self.refusal is None):
            raise ValueError("Return exactly one of plan or refusal")
        return self


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)
    use_ai: bool = False


class ComputedQuery(BaseModel):
    insight: Insight
    chart: ChartSpec | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    result_truncated: bool = False
    reference_values: list[str] = Field(default_factory=list)


class QuestionResponse(BaseModel):
    dataset_id: str
    question: str
    status: Literal["answered", "refused"]
    refusal: str | None = None
    plan: AnalysisPlan | None = None
    insight: Insight | None = None
    chart: ChartSpec | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    result_truncated: bool = False
    answer: str | None = None
    explained: bool = False
    explanation_reason: str | None = None

    @classmethod
    def refused(cls, dataset_id: str, question: str, reason: str) -> "QuestionResponse":
        return cls(dataset_id=dataset_id, question=question, status="refused", refusal=reason)
