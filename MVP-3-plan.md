# MVP 3 — Ask Your Data

> **Status:** removed. Ask Your Data was implemented and later removed along with every other
> model-dependent feature, including the `questions/` package, the question endpoint, and
> `DATASIGHT_QUESTION_MAX_TURNS`. This document is kept as a design record. The recipe engine it
> built on remains; see [MVP-2.5-plan.md](MVP-2.5-plan.md).

MVP 3 is implemented. A reader can ask a natural-language question about the
current dataset, receive an answer calculated by Python, view a suitable chart,
and ask a contextual follow-up.

The architectural rule remains:

> **Python calculates. AI explains.**

The request path is:

```text
question → model planning → typed plan validation → Python execution
         → verified result → model explanation → number/causality verification
```

The model never receives permission to execute code and never supplies a number
that is trusted as a result. It selects one plan from a closed Pydantic vocabulary.
Python validates every referenced column, filter value, type, grouping, limit, and
privacy condition against the uploaded dataset before executing the plan.

## Implemented operations

| Operation | Example | Deterministic implementation |
| --- | --- | --- |
| `aggregate` | Average revenue by segment | Typed filtering and pandas aggregation |
| `rank` | Products with the most revenue | Aggregation, stable ordering, capped limit |
| `compare` | Compare revenue by segment | Existing group comparison analysis |
| `relate` | Does cost track revenue? | Existing Pearson/Spearman analysis |
| `trend` | How has revenue moved? | Existing datetime analysis |
| `distribution` | Show the revenue spread | Existing numeric/categorical analysis |
| `count` | How many enterprise rows? | Typed filtering and row count |
| `describe` | What is in this column? | Profile metadata without raw samples |

Filters use the existing closed recipe operators. A literal that cannot be read as
the target column's type is refused rather than guessed. Ranking is capped at 20
rows. Grouping supports up to two categorical, boolean, or datetime columns;
datetime grouping requires an explicit day, week, month, quarter, or year grain.

## Safety and privacy

- Plans reject unknown operations and extra fields. There is no field for Python,
  SQL, pandas expressions, attribute access, `eval`, or `DataFrame.query`.
- Unknown columns, text measures, invalid filter values, self-correlations, and
  unsuitable time columns produce useful refusals.
- Causal questions are refused before a model call. The system can report patterns
  and associations but cannot establish why something happened.
- Planning prompts contain column names, semantic types, privacy flags, row count,
  and prior questions/plans. They do not contain profile samples or dataset rows.
- Identifier-like and high-cardinality columns cannot be grouped. Execution also
  refuses a grouping whose typical result represents fewer than three source rows,
  and near-unique categorical distributions. Results exposed to the explanation
  model are capped at 20 aggregate rows. Descriptions use metadata rather than raw
  values.
- Explanations pass through the existing number-traceability and causality checks.
  Rejected or unavailable prose is replaced by the deterministic Python message.
- With the AI toggle off, the panel is disabled and the question endpoint refuses
  without creating a model client. Tests use fake clients and require no API key.

## Conversation

Successful turns are held with the dataset in the in-memory store and share its
expiration. Each turn stores the question, complete plan, capped reference labels,
and verified response. At most `DATASIGHT_QUESTION_MAX_TURNS` turns are retained.

Follow-up references such as “the top three” are resolved in Python from the prior
capped ranking labels. The planner receives a rewritten question containing those
explicit labels and must emit a complete plan with ordinary validated filters.
The executor itself is stateless; every plan means the same thing on its own.
Identical questions with the same resolved context reuse their stored response.

## Frontend behavior

The Ask Your Data panel is visible after upload. While AI is off it explains how to
enable the feature and makes no request. While a question is running it shows a
loading state. Answers can include a compact result table and a histogram, bar,
box, scatter, or line chart. Planning refusals and transport errors remain visible
and actionable.

## Remaining scope

The following are deliberately deferred:

- Causal diagnosis and “why” questions: observational data does not establish a
  cause, so these are refused rather than approximated.
- Forecasting, predictive modeling, clustering, and anomaly detection: these
  belong to the later advanced-analytics milestone.
- Arbitrary multi-stage programs: the implemented vocabulary supports filtered
  aggregations, rankings, and two-dimensional grouped follow-ups. More general
  pipelines would need additional typed operations and validators; model-written
  code will not be used.
- Interactive ambiguity clarification: if a model cannot choose an exact column,
  it must refuse. A future UI can turn that refusal into a choice prompt.
- Durable or cross-dataset conversations: conversations remain in process memory
  and expire with their dataset.
- A paid live-model smoke test was not run during automated implementation. Fake
  clients cover planning and explanation without a key or network call.

Automated coverage includes successful ranking, grouping, comparison,
relationship, trend, distribution, count, and description questions; invalid
columns and filter types; privacy guards; prompt contents; explanation
verification; result caps; causal and unsupported refusals; caching; expiration;
follow-up resolution; and frontend disabled, loading, success, refusal, and error
states.
