# MVP 2.5 — Shape Your Data (plan)

> **Status:** implemented. This was written as a plan before the recipe engine was built and is
> kept as its design record; details may differ from the code. The references below to Ask Your
> Data, MVP 3, the model, and the `ai/` layer describe features that were later removed. See
> [README.md](README.md) for the current app.

MVP 1 answered *what is in this file*. MVP 2 answered *what is worth knowing about it*. Both
decided for the reader — the reader only chose a file. MVP 2.5 hands part of that choice over:
the reader picks the columns, the rows and the operations, and the engine runs them. No code,
and no model.

## Why this earns a step in the roadmap

`Project_Fundamentals.md` §19 has nothing between the insight engine and Ask Your Data, so this
is an insertion. It earns one because it is not a detour from MVP 3 — it is MVP 3's foundation,
built where it can be finished and tested without a model.

`MVP-3-plan.md` describes a typed analysis plan from a closed vocabulary, validated against the
real columns of the real file, executed by Python, with the model only *filling it in*. Of that
layer it says:

> Phase 1 is most of the work and all of the risk. It is worth finishing before any prompt is
> written: a validated executor with no model attached is a feature on its own.

That sentence is this document. MVP 2.5 builds the executor and puts a **user interface** in
front of it instead of a model. MVP 3 then attaches the model to something already built,
already validated, and already covered by tests.

Written the other way round — a no-code builder with its own private engine — the same
validation logic would be written twice and would drift.

## The rule holds, and costs nothing here

> **Python calculates, AI explains.**

There is no model anywhere in this path. Every number a reader sees is one they asked Python to
compute. The explanation layer is untouched: it stays optional, stays behind the toggle, and
now has a second kind of dataset it can be pointed at.

This also sits correctly in the priority order of §20 — correctness and reproducibility before
AI capabilities.

## The primitive: a step

One vocabulary, two families. A **step** is a Pydantic model discriminated on its `op` field.
Nothing in it is a string that gets interpreted; every column is a name checked against the
schema, and every operation is an enum member that dispatches through an explicit table.

### Transform steps — frame in, frame out

| `op` | What it does | Validation |
|---|---|---|
| `select_columns` | Keep only the named columns | Each must exist |
| `drop_columns` | Remove the named columns | Each must exist; cannot drop all |
| `filter_rows` | Keep rows matching `{column, op, value}` clauses, combined with `and` / `or` | `op` from a fixed set per column type; `value` coerced to the column's type |
| `sort_rows` | Order by one or more columns | Each must exist |
| `limit_rows` | First *n* rows, or a seeded random sample of *n* | *n* capped |
| `drop_missing` | Drop rows missing values in the named columns (or any, or all) | Named columns must exist |
| `fill_missing` | Per column: median / mean / mode / constant / forward-fill | Method must suit the column's type — no median on text |
| `drop_duplicates` | On the named columns, or on all | Named columns must exist |
| `rename_column` | New name for one column | Source exists; target does not collide |
| `cast_column` | To numeric / datetime / categorical / text | Refused if coercion would lose more than a stated share of rows |
| `derive_column` | A new column from a **closed expression vocabulary** (below) | Inputs exist and have the right types; name does not collide |
| `aggregate` | Group by zero to two columns, apply `sum` / `mean` / `median` / `count` / `min` / `max` to named measures | Group columns must exist, be categorical, boolean or datetime, and not be ID-like or high-cardinality; measures must be numeric (except `count`) |

`derive_column` is the one place where the temptation to accept an expression *string* is
strongest, and it is refused for the same reason MVP 3 refuses model-written pandas. The
expression is a small typed tree:

| Expression | Example |
|---|---|
| `arithmetic` | `revenue - cost`, `revenue / 1000` — operands are column names or constants |
| `bin` | `age` into fixed edges or quantiles, with labels |
| `datetime_part` | `year` / `quarter` / `month` / `weekday` from a datetime column |
| `map_values` | An explicit `{old: new}` mapping over a categorical column |

Division guards against a zero denominator by producing a missing value, not an error, and the
step reports how many rows that affected.

### Analyze steps — frame in, statistical result out, terminal

These do not produce a frame, so a recipe holds at most one and it comes last.

| `op` | Question | Reuses | Returns |
|---|---|---|---|
| `compare` | Does this numeric column differ across these groups? | `analysis/group_analysis.py` | `GroupComparison` |
| `relate` | Do these two numeric columns move together? | `analysis/correlation_analysis.py` | `CorrelationPair` |
| `trend` | How has this moved over time? | `analysis/datetime_analysis.py` | `Timeline` |
| `distribution` | What does this column's spread look like? | `analysis/numeric_analysis.py`, `analysis/categorical_analysis.py` | `NumericSummary` / `CategoricalSummary` |

Every one of these returns a model that already exists in `analysis/models.py`, which is the
point: the chart layer and the insight layer already know how to render them.

### Why `aggregate` is a transform and not an analysis

Because its output is a table, and treating it as one makes the vocabulary smaller.

`MVP-3-plan.md` lists `rank` and `count` as separate operations. They are not needed. "Which
three products generate the most revenue?" is `aggregate` by product, then `sort_rows`
descending, then `limit_rows` 3 — three steps the reader can see, adjust and reorder. "How many
orders were returned?" is `filter_rows` then `aggregate` with `count`. Composition replaces two
special cases, and a reader who wants the fourth product changes one number instead of asking a
new question.

It also means `filter_rows` after `aggregate` is a `HAVING` clause and needs no new vocabulary.

## A recipe

```text
Recipe = ordered list of transform steps
         + at most one analyze step, last

sales.csv  (1,204 rows, 9 columns)
   │
   ├─ 1  select_columns   [city, product, revenue, cost, order_date]
   ├─ 2  filter_rows      revenue > 1000  and  city != "Unknown"
   ├─ 3  fill_missing     cost → median
   ├─ 4  derive_column    margin = revenue - cost
   ├─ 5  aggregate        sum(margin) by city
   ├─ 6  sort_rows        margin desc
   └─ 7  limit_rows       10
                          ↓
                 ┌────────┴────────┐
                 ▼                 ▼
          preview (cheap)    apply → new dataset_id
                                    ↓
                        the entire existing pipeline
```

## Schema propagation is the load-bearing part

Step 6 sorts by `margin`, a column that did not exist in the file. Step 2 filters on `revenue`,
which step 1 may or may not have kept. So validation cannot be done against the uploaded
profile — it has to be done against the schema **as it stands at that point in the chain**.

Every step therefore needs two functions:

```text
plan_schema(schema, step) -> schema     # what the columns look like after, without running
apply(frame, step)        -> frame      # what actually happens
```

Validation walks the recipe with the projected schema; execution walks it with the frame. They
must agree, and the test that they agree — for every step, on every column type — is the single
most important test in this MVP. A disagreement is how a validated recipe blows up at run time,
and how a reader gets offered a column that will not be there.

Projection also drives the UI: the column menu on step 5 can only offer what the schema says
exists after step 4, and it can know that without executing anything.

## Derived datasets: what comes for free

[`store.py`](backend/app/store.py) keys everything on `dataset_id`, and all seven dataset
endpoints in [`api/routes.py`](backend/app/api/routes.py) take nothing but a `dataset_id`. So a
recipe's output, registered as a dataset in its own right, gets profiling, the quality report
and score, chart selection, insights and explanations **with no change to any of those layers**.

`POST /recipe/apply` returns a `DatasetProfile`, exactly as `/upload` does. The frontend's
existing fan-out in [`app/page.tsx`](frontend/app/page.tsx) — the `Promise.all` over preview,
charts, quality and insights — then runs unchanged over the shaped data.

The original is never modified. A derived dataset carries its parent and the recipe that made
it, so every change is reversible by construction, which is what §13 asks for.

### Storage: keep the recipe, not the frame

The obvious implementation holds every derived frame in memory, and a reader iterating on a
recipe would produce a dozen copies of their file.

Store `(parent_id, recipe, profile)` instead and materialise the frame on demand behind a small
LRU cache. Recipes are deterministic and the original is immutable, so re-execution always
yields the same frame; the cache is an optimisation and never a correctness question. The
profile is computed once at apply time and kept, because later validation needs it and it is
far smaller than the frame.

## Endpoints

| Method | Path | Body / returns |
|---|---|---|
| `POST` | `/datasets/{id}/recipe/preview` | Recipe → first rows, row counts per step, refusals. Persists nothing |
| `POST` | `/datasets/{id}/recipe/apply` | Recipe → `DatasetProfile` of a new derived dataset |
| `GET` | `/datasets/{id}/lineage` | Parent chain and the recipe at each hop |
| `GET` | `/datasets/{id}/export` | The frame as CSV |

Preview is the one the UI calls constantly, so it is cheap by construction: it runs the recipe,
reuses `build_preview` from [`profiling/preview.py`](backend/app/profiling/preview.py) with its
existing 200-row cap, and throws the frame away.

## Refusals

A step that cannot be applied returns a **reason**, not a guess. The refusal names the step
index, the column and what was wrong, and the UI shows it against that step while leaving the
recipe intact so the reader can fix it.

```text
Step 3  fill_missing(city, median)
        Refused — "city" is a text column and has no median.
        Try: most frequent value, or a constant.
```

A refusal is a normal response, not an error. Preview returns the frame as it stood *before*
the refused step, so the reader keeps their context.

## Safety

The threat model is smaller than MVP 3's, because no model writes anything here — but the input
is still untrusted, and the guards are the ones MVP 3 will inherit:

- No string from a request reaches `eval`, `df.query`, `df.eval`, or a dynamic attribute lookup.
  Operations dispatch through an explicit mapping from enum member to function.
- Column names are matched exactly against the schema and never interpolated into anything.
- Filter and fill values are coerced to the column's declared type; a value that will not coerce
  is a refusal, never a loose comparison.
- Caps on steps per recipe, derived datasets per parent, and `limit_rows`.
- `derive_column` accepts a typed tree, never an expression string.

## What "selecting rows" means

"Choose the rows" has two readings and only one of them survives being re-run.

A **condition** — `revenue > 1000` — is reproducible: it means the same thing after the file is
re-uploaded, after an earlier step changes, and when it is read back a week later.

**Ticking individual rows** is positional. Insert a step above it and it silently selects
different data. So direct row selection is offered only as a filter: ticking rows in the preview
produces a filter on an identifying column when the profiler has found one
(`is_probable_id`), and is refused with that reason when it has not. Refusing is better than
recording a recipe that quietly means something else later.

## Frontend

The preview table stops being a read-only display and becomes the place steps are made.

```text
┌─ Recipe ─────────────┐ ┌─ Preview ──────────────────────────────┐
│ 1 select 5 columns ⓧ │ │ city    product   revenue   margin     │
│ 2 revenue > 1000   ⓧ │ │ ──────  ────────  ───────   ──────     │
│ 3 fill cost median ⓧ │ │ IST     A           4,200    1,180     │
│ 4 margin = rev-costⓧ │ │ ANK     C           3,100      940     │
│ 5 sum by city      ⓧ │ │                                        │
│                      │ │ 1,204 → 340 rows · 9 → 5 columns       │
│ + add step           │ └────────────────────────────────────────┘
│                      │
│ [ Save as dataset ]  │   Clicking a column header opens only the
│ [ Download CSV   ]   │   steps that suit that column's type.
└──────────────────────┘
```

Three things this shape buys: the step list is the recipe, so there is nothing hidden; removing
a step is the undo; and the column menu is generated from the projected schema, so it cannot
offer an operation that will be refused.

A lineage line above the dashboard — `sales.csv › 4 steps` — says which dataset the insights on
screen were computed from, and gets back to the original in one click.

## What gets reused

| Existing | Used for |
|---|---|
| `store.py` | Extended with parent, recipe and lazy materialisation |
| `profiling/` | The schema every step is validated against; re-profiles derived data |
| `profiling/preview.py` | The preview payload, cap included |
| `analysis/` | The four analyze steps, unchanged |
| `visualization/chart_selector.py` | Picks the chart for an analyze step's result |
| `insights/`, `quality/`, `ai/` | Run over a derived dataset with no change at all |

## Build order

Every phase runs without an API key. That is the whole argument for doing this first.

| Phase | Work | Needs a key |
|---|---|---|
| 1 | Step models, `plan_schema`, validator. No execution | No |
| 2 | Executor for transform steps. Hand-written recipes, end to end | No |
| 3 | Preview and apply endpoints; store lineage and lazy materialisation | No |
| 4 | Analyze steps over the existing `analysis/` modules | No |
| 5 | Recipe panel and interactive preview table | No |
| 6 | CSV export | No |
| 7 | Insights and charts over derived data — confirm nothing broke, guard the small-frame cases | No |

Phases 1 and 2 are most of the work. Phase 7 is where the surprises will be.

## Tests the phase is not done without

- For every step and every column type, `plan_schema` predicts exactly the column set and types
  that executing the step then profiling produces.
- A step naming a column that does not exist *at that point in the chain* is refused, with a
  reason — including a column dropped by an earlier step, and one created by an earlier step.
- `fill_missing` with `median` on a text column is refused, not silently switched to mode.
- A filter value that will not coerce to its column's type is refused, not compared loosely.
- `cast_column` that would lose more rows than the threshold is refused, and says how many.
- No string from a request reaches `eval`, `query`, `eval` on a frame, or a dynamic attribute
  lookup.
- A derived dataset re-materialised from its recipe is identical to the frame produced when it
  was applied.
- The original dataset is unchanged after any recipe runs against it.
- `aggregate` is refused on an ID-like or high-cardinality group column.
- Profile, quality, charts and insights all return successfully for a derived dataset.
- Ticking rows without an identifying column is refused, with that reason.

## What this changes about MVP 3

Mostly it shrinks it.

`MVP-3-plan.md` Phase 1 — plan model, validator, executor — is this document, so it can be
struck. Phases 3 through 6 land on a running feature instead of an empty package.

The model's output becomes a **recipe**, not a flat plan. That is a real trade: a list of
composable steps is harder for a model to emit correctly than a single flat object, and the
prompt work in MVP 3 Phase 2 gets harder. It buys two things worth more than that cost. The
model can only emit steps a reader could have built by hand, so there is nothing to validate
that is not already validated. And an answer can be **shown as its recipe** — the reader sees
which columns were used, which rows were dropped and in what order, and can edit it. An
Ask Your Data that shows its work is a different product from one that does not.

If the composition proves too hard for the model, the fallback is to constrain it to a fixed
recipe shape — filter, then aggregate, then sort, then limit — which is the flat plan again,
expressed in the same vocabulary rather than a second one.

`MVP-3-plan.md` should be updated to say this once MVP 2.5 is a record.

## Open questions

**Insights on shaped data.** The ranker and the insight generator were built for raw uploads. A
five-row aggregate will either produce nothing or produce something silly — a correlation over
five city totals is not a finding about the business. Whether the answer is a minimum row count,
a different ranking profile for derived data, or marking derived datasets so some insight types
are skipped, is undecided. Phase 7 is where it gets decided, with real files.

**Analyze after aggregate.** `compare` run on group means treats aggregates as observations,
which is usually wrong and occasionally what the reader means. Refusing is too strong and
silence is too weak; a caveat on the result is the likely answer, and `insights/models.py`
already carries caveats.

**Quality score on derived data.** A recipe that drops every row with a missing value produces a
dataset scoring 100 on completeness. That is true and useless. The score may need to know it is
looking at derived data and say so.

**Recipes across files.** A recipe is validated against one file's schema. Applying a saved
recipe to next month's file is obviously wanted and is a schema-compatibility problem that is
not being solved now.

**Joins.** Combining two uploaded files is the largest missing operation in any no-code data
tool. It needs two datasets in one recipe and a key-matching UI, and it is out of scope here.

## Not in MVP 2.5

Joins and multi-dataset recipes. Saved or shareable recipe templates. Pivot and unpivot.
Window functions and running totals. Natural-language questions, analysis planning and
conversational follow-ups — all still MVP 3. Advanced anomaly detection, ML task detection,
baseline models and exportable analysis reports stay in MVP 4. The `anomaly/` package stays
empty.
