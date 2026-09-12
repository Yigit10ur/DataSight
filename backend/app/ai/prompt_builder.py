import json

from app.insights.models import Insight
from app.profiling.models import DatasetProfile
from app.quality.models import QualityScore

SYSTEM_PROMPT = """You explain the results of a statistical analysis to someone who \
has just uploaded their own data and is not a statistician.

You are given findings that have already been computed. You are not given the data, \
and you are not asked to analyse anything. Your only job is to say what each finding \
means for the person reading it.

Rules you must follow:

1. Use only the numbers you are given. Never calculate a new one, never estimate, and \
never bring in a number from outside. Rounding a number you were given is fine; \
producing one you were not given is not.
2. Never say or imply that one column causes, drives, explains or produces another. \
These are measured associations. If a reader might read cause into a finding, say \
plainly that the data cannot show that.
3. Do not guess what the columns mean in the real world, what industry the data is \
from, or what the reader should do about it. You do not know.
4. Two or three sentences for each finding. Plain words. No headings, no bullet \
points, no opening phrases like "This finding shows".
5. Do not repeat the finding back word for word. Say what it means: what it tells the \
reader about their data, and what it does not tell them.

Also write one short paragraph about the dataset as a whole: how big it is, what \
condition it is in, and what stands out about it. Three or four sentences. Do not \
walk through the findings one by one, and do not open with a phrase like "This \
dataset". If nothing stands out, say so plainly rather than filling the space.

Answer with a JSON object and nothing else, shaped like this:

{"summary": "your paragraph", "explanations": {"finding-id": "your explanation"}}"""


def build_payload(
    profile: DatasetProfile, score: QualityScore, insights: list[Insight]
) -> dict:
    """The structured findings, and nothing else.

    The dataset itself never leaves this machine. What the model sees is the shape
    of the file and the numbers that came out of the analysis, so the size of this
    payload depends on how many findings there are, never on how many rows.
    """
    return {
        "dataset": {
            "rows": profile.rows,
            "columns": profile.columns,
            "column_names": [schema.name for schema in profile.column_schemas],
            "missing_cell_share": profile.missing_ratio,
            "duplicate_rows": profile.duplicate_rows,
        },
        "quality_score": {
            "overall": score.score,
            "out_of": 100,
            "dimensions": {
                dimension.label: dimension.score
                for dimension in score.dimensions
                if dimension.applicable
            },
        },
        "findings": [
            {
                "id": insight.id,
                "type": insight.insight_type,
                "columns": insight.columns,
                "computed_message": insight.message,
                "metrics": insight.metrics,
                "rows_behind_it": insight.sample_size,
                "caveats": insight.caveats,
            }
            for insight in insights
        ],
    }


def build_prompt(
    profile: DatasetProfile, score: QualityScore, insights: list[Insight]
) -> tuple[str, str]:
    payload = build_payload(profile, score, insights)
    return SYSTEM_PROMPT, json.dumps(payload, ensure_ascii=False, indent=2, default=str)
