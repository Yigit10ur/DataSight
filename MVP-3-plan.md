# MVP 3 — Ask Your Data (plan)

This is a plan, not a record. `MVP-1.md` and `MVP-2.md` describe what was built; this
describes what is intended, and should be replaced by a record of the same name once it is.

The goal from `Project_Fundamentals.md` §11: a reader types a question in their own words and
gets an answer computed from their file, with a chart when one helps, and follow-up questions
that understand what was just asked.

## The one hard problem

Every previous layer chose its own analyses. The analyst decided what to compute; the reader
only chose a file. MVP 3 hands that choice to the reader, which means something has to turn an
English sentence into an analysis — and the obvious way to do that breaks the rule the whole
project rests on.

> **Python calculates, AI explains.** Every number shown was computed before a model was
> contacted, and no number a model produced is ever displayed.

A model that answers "which products generate the most revenue?" from the data has produced
the number. That is the failure mode this project exists to avoid, and it does not become safe
because the question was good.

## The design that keeps the rule

Split the model's job in two, and put the arithmetic between them:

```
question ──▶ [model] ──▶ analysis plan ──▶ [Python] ──▶ result ──▶ [model] ──▶ prose
                            (validated)     (computes)   (numbers)   (verified)
```

The model chooses **what** to compute. It never computes. The plan is a typed object from a
closed vocabulary, validated against the actual columns of the actual file before anything
runs. The result carries its numbers in the same shape as an `Insight`, so the verification
layer built in MVP 2 applies to the prose **unchanged**: every quantity in the answer must
trace back to the result, or the answer is rejected whole.

This is the load-bearing decision of MVP 3. Everything below follows from it.

### Why not let the model write code

The tempting version is: the model writes a pandas expression or a SQL string, and Python runs
it. It is less work and it is wrong twice.

It is unsafe: `df.query` and anything near `eval` turn a sentence from an untrusted source into
execution on the server. There is no way to review a string for that at runtime that is easier
than not accepting the string.

It is also unverifiable, which matters more. If the model can express any computation, nothing
downstream can check that the computation answered the question, used the right column, or
filtered the way it claimed. A closed vocabulary is a vocabulary you can validate: every field
is checked against the profile, every operation has a known result shape, and an invalid plan
is refused with a reason instead of half-executed.

## The analysis plan

A Pydantic model, filled by the model, validated by Python. Sketch:

| Field | Meaning | Validation |
|---|---|---|
| `operation` | One of a fixed set (below) | Enum |
| `measure` | The numeric column being summarised | Must exist, must be numeric |
| `function` | `sum` / `mean` / `median` / `count` / `min` / `max` | Enum |
| `group_by` | Zero to two columns to split by | Must exist; categorical or datetime; not ID-like |
| `filters` | List of `{column, op, value}` | `op` from a fixed set; `value` coerced to the column's type |
| `order` | `asc` / `desc` | Enum |
| `limit` | How many rows to return | Capped |

Operations, each mapping onto analysis code that already exists:

| Operation | Question it answers | Reuses |
|---|---|---|
| `aggregate` | "What is average revenue by city?" | `analysis/numeric_analysis.py` |
| `rank` | "Which products generate the most revenue?" | `aggregate` plus order and limit |
| `compare` | "Do enterprise customers spend more than SMB?" | `analysis/group_analysis.py` |
| `relate` | "Does marketing spend track revenue?" | `analysis/correlation_analysis.py` |
| `trend` | "How has revenue moved this year?" | `analysis/datetime_analysis.py` |
| `distribution` | "What does the age spread look like?" | `analysis/numeric_analysis.py` |
| `count` | "How many orders were returned?" | Filter and count |
| `describe` | "What is in the `score_text` column?" | `profiling/` |

A value that will not coerce to its column's type is a **refusal, not a guess**. "Revenue over
1000" against a text column is a question the file cannot answer, and saying so is the correct
answer.

## What gets reused

MVP 3 is mostly assembly. The parts that already exist and should not be rewritten:

| Existing | Used for |
|---|---|
| `ai/verification.py` | Number traceability and causation checks on the answer — no change expected |
| `ai/llm_client.py` | Still the only place that talks to a model |
| `insights/models.py` | The result becomes an `Insight`, so caveats and charts already work |
| `visualization/chart_selector.py` | Picks the chart from the result's shape |
| `profiling/` | The schema the plan is validated against |
| `store.py` | Holds the frame the plan runs on |

If a question's result cannot be expressed as an `Insight`, that is a signal the operation is
too broad, not that the model needs a new one.

## Conversation

Follow-ups ("compare the top three by month") need the previous turn. The rule that keeps this
honest: **references are resolved into explicit plans, never carried as pointers.**

The model is given the previous questions and their *plans* — not their result rows — and must
emit a new, complete plan. "The top three" comes back as a filter naming those three values
explicitly, which Python then validates like any other. There is no state inside the executor
and no plan that means anything except by itself.

A conversation is a list of turns held next to the dataset in `store.py`. It dies on restart,
like the datasets do. That is acceptable for MVP 3 and should be written down rather than
discovered.

## A subtlety worth naming early

MVP 2 could promise that no row of the dataset reaches the prompt, because the payload held
only findings. A query result is different: `aggregate` grouped by a near-unique column returns
something close to the rows themselves, and it has to be shown to the model to be described.

So the promise needs a second guard, not just the old test:

- refuse `group_by` on ID-like or high-cardinality columns — the profiler already flags both
- cap the rows of any result sent for description, and tell the model the result was truncated
- keep the existing test and add one that drives it through a *question*, not a finding

## Cost

Every question is two model calls: one to plan, one to describe. The plan call is small; the
description call is the size of one result. With the explanation toggle off there is no Ask
Your Data at all, which is a product decision that has to be made deliberately: hiding the
panel makes the feature undiscoverable, so it should be visible and disabled, with one line
saying what turns it on.

Identical questions about the same dataset should be cached the way explanations are.

## Build order

Phased so the expensive part comes last and the bulk of the work costs nothing to test.

| Phase | Work | Needs a key |
|---|---|---|
| 0 | Bring `MVP-2.md` up to date — it predates the AI toggle and the explanation lock, and still says 188 tests | No |
| 1 | Plan model, validator, executor. Hand-written plans, end to end, no model | **No** |
| 2 | Question → plan, against a fake client and a golden set of question/plan pairs | No |
| 3 | Result → prose, through the existing verification | No |
| 4 | Charts for results | No |
| 5 | Conversation and follow-ups | No |
| 6 | Frontend panel | No |
| 7 | Live run against the real API, as MVP 2 ended | Yes |

Phase 1 is most of the work and all of the risk. It is worth finishing before any prompt is
written: a validated executor with no model attached is a feature on its own, and it makes
every later phase testable against a fake.

## Tests the phase is not done without

- A plan naming a column that is not in the file is refused, with a reason.
- A plan whose measure is a text column is refused.
- A filter value that will not coerce to its column's type is refused, not coerced loosely.
- No string from a model reaches `eval`, `query`, or any dynamic attribute lookup.
- Every number in an answer traces to the result it describes — the MVP 2 invariant, now over
  query results.
- No row of the dataset reaches the prompt, driven through a question.
- A question the vocabulary cannot express produces a refusal, and the refusal says why.

## Open questions

**Ambiguity.** Two columns could both be "revenue". Asking the reader which one is right is
better than picking, but it is a conversation turn that the plan step does not currently have.

**Questions that are not analyses.** "Why did revenue drop in March?" asks for a cause. The
project's answer has to be that the data cannot show that — the same refusal the explanation
layer already makes, moved to the question step.

**Multi-step questions.** "Compare the top three products by month" is two operations. Whether
the plan holds a list of steps or the conversation runs two turns is undecided, and the simpler
answer is probably two turns.

**When the answer is boring.** "Revenue by city" on a file with one city is a valid plan and a
useless answer. The insight ranker already knows how to judge that; whether it should sit in
this path is undecided.

## Not in MVP 3

The cleaning workflow, advanced anomaly detection, ML task detection and baseline models stay
in MVP 4. The `anomaly/` package stays empty. Exportable reports stay in MVP 4.
