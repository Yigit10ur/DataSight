# MVP 2 — Insight Engine

MVP 1 answered *what is in this file*. MVP 2 answers *what is worth knowing about it*, and
then says it in plain language.

The rule from `Project_Fundamentals.md` has not moved: **Python calculates, AI explains.** An
LLM now writes prose, but it is given results it cannot alter and numbers it is not allowed to
add to. Every quantity on the screen was computed before any model was contacted, and the
product works fully with no model at all.

## What a dataset goes through now

```text
CSV / Excel upload
        ↓
validation + parsing            (ingestion/)     MVP 1
        ↓
schema + dataset profile        (profiling/)     MVP 1
        ↓
quality issues + score          (quality/)       score is new
        ↓
statistics, correlations,
group differences, timelines    (analysis/)      the last two are new
        ↓
chart selection                 (visualization/) now driven by analysis
        ↓
structured findings             (insights/)      new
        ↓
ranking and deduplication       (insights/)      new
        ↓
explanation and summary         (ai/)            new, optional
        ↓
dashboard                       (frontend/)
```

## Analysis: the two missing halves

MVP 1 computed single-column statistics and correlations. Box plots and time series existed,
but their numbers were calculated inside the chart layer at draw time, so no finding could
rest on them. Two modules close that gap.

### `analysis/group_analysis.py`

Compares one numeric column across the groups of one categorical column: per-group count,
mean, median, standard deviation, quartiles and whiskers; the highest and lowest group; the
ratio between their means; and an effect size with a p-value.

The test is **Kruskal–Wallis**, not ANOVA, because group sizes in an uploaded file are rarely
balanced and its numeric columns are rarely normal. The effect size reported is
epsilon-squared, read by the usual convention: 0.01 small, 0.06 moderate, 0.14 large.

Groups with fewer than five rows are excluded and counted separately. Without that rule a
single mistyped label becomes "the highest group".

A ratio is only reported when the lower group's mean is positive: "2.4x higher" means nothing
against a negative baseline, so the comparison falls back to a median difference.

### `analysis/datetime_analysis.py`

Describes how a numeric column moves against a datetime column: trend direction, change
ratio, slope, monotonicity, the largest single period-to-period move, and seasonality.

Change is measured between the **first and last quarter** of the timeline rather than between
the first and last point, so one unusual period cannot decide the direction of a trend.
Monotonicity — the rank correlation between position and value — separates a series that
climbs every period from one that steps up once; both have the same total change.

Seasonality is reported as the share of variation explained by the position in the calendar
cycle, and only when the series covers at least two full cycles.

The resampling period is chosen from the span of the data **and from the spacing of its
rows**. Span alone put monthly rows into weekly buckets, producing three empty periods for
every real one. A seasonality test found this; nothing else would have.

### `analysis/numbers.py`

One place that reads a column as numbers, treating infinity as missing. `pandas` produces
`inf` from a literal `inf` in a CSV, and a single such cell crashed `analyze_numeric` —
`np.histogram` refuses a non-finite range — which took the `/analysis` and `/charts`
endpoints down with it. An infinite value is not a measurement: it cannot be averaged,
binned or plotted.

### What this changed in the chart layer

`chart_generator` no longer computes anything. `box_chart` and `line_chart` take an analysis
result and relabel it. The side effect is better selection: the box chart now shows the
**most separated** pair rather than the first categorical column, and the line chart the
column that **moved most**, because the analysis layer ranks them before the chart layer sees
them.

## `quality/score.py`

A score out of 100 over the five dimensions of section 8, each computed the same way:

```text
score = 100 × (1 − observed / tolerance)
```

| Dimension | Measures | Tolerance | Weight |
|---|---|---|---|
| Completeness | share of missing cells | 0.50 | 0.30 |
| Consistency | share of categorical columns with spelling or spacing problems | 0.50 | 0.20 |
| Type consistency | share of columns stored in the wrong type | 0.50 | 0.20 |
| Duplicate score | share of duplicated rows | 0.30 | 0.15 |
| Outlier score | share of values outside the Tukey fences | 0.20 | 0.15 |

Tolerance is the share at which a dimension reaches zero. The three measured over cells or
columns share one tolerance, which is also how they are explained: half the file gone, or
half its columns in the wrong shape, is not a dataset. Duplicates and outliers are measured
over rows and values, where a much smaller share already means something is wrong.

Three decisions are worth keeping:

- **The score is a pure function of the profile and the issues already reported.** It computes
  nothing of its own, so it cannot disagree with the list printed beside it. Each dimension
  carries the columns that cost it points and the issue ids that explain them.
- **A dimension with nothing to measure gives its weight away.** A file with no numeric
  columns is not outlier-free; it is outside the question. Scoring it 100 would have lifted
  the total for free.
- **Structural notes are not scored.** A constant column, an identifier, a high-cardinality
  column: these describe what a column *is*, not that it is damaged.

## `insights/`

### The structured finding

```python
Insight(id, insight_type, columns, message, metrics,
        strength, confidence, sample_size, caveats, chart_id, importance)
```

Ten types are generated: `correlation`, `group_difference`, `trend`, `seasonality`,
`sudden_change`, `outliers`, `skewed_distribution`, `dominant_category`, `rare_categories`,
`missing_data`.

**The generator measures nothing.** Every number already exists in the analysis or the quality
report. This layer decides which of them are worth saying out loud and writes the sentence
that says it.

**Every number in `message` is also in `metrics`.** A test enforces it: each numeric token in
the message is extracted and rebuilt from the metrics using the same formatting helpers the
generator writes with. A message that starts formatting a number some other way fails until
that format is added deliberately. The same function later checks what the model writes.

Three numbers describe a finding, and they are kept apart on purpose:

- `strength` — how large the effect is, rescaled to 0–1 so types can be compared at all.
- `confidence` — how far the numbers can be leaned on. Caveats say this to the reader in
  prose; `confidence` says it to the ranker, which cannot read prose.
- `importance` — where it belongs in the list. Filled by the ranker, not the generator.

`chart_id` is matched against the charts that were actually selected, never guessed from a
naming convention, so a finding never points at a chart that does not exist.

### Caveats

Two are attached automatically. Every `correlation` finding carries the warning against
reading it as cause (section 21). A `group_difference` on a column with spelling variants
carries a warning that one real group may be split across several compared groups — and its
`confidence` drops to 0.6, because that genuinely undermines the comparison. The causation
caveat does not lower confidence: it is a reading instruction, not a doubt about the number.

### Ranking

```text
importance = strength × confidence × reliability(n) × type_weight
```

`reliability(n) = n / (n + 50)` is a curve, not a cutoff, so 49 rows and 51 rows are not
treated as different kinds of evidence.

`type_weight` runs from 1.00 for group differences and trends down to 0.40 for rare
categories. A difference between groups tells a reader something about their subject; a
skewed column tells them something about their file.

Two kinds of redundancy are removed:

- **Same phenomenon, two names.** Trend and sudden change, outliers and skew, dominant and
  rare categories: on the same columns, the stronger survives.
- **Correlation travels.** If a–b and b–c both hold, a–c follows and says nothing new. A
  correlation is dropped when both its columns are already covered by stronger pairs. This is
  visible on `growth.csv`, where three relationships collapse to two.

Caps: three per type, fifteen in total. Equal findings are ordered by id, so the list depends
on the data and not on the order the generator happened to produce them in.

### Thresholds, and one that was wrong

Nothing is reported below its threshold. The outlier threshold started at 2% and fired on
pure Gaussian noise: a normal distribution already puts about 0.7% of its values outside the
Tukey fences, and sampling at n = 300 pushed that to 2.3%. It is now 5%. Random data produces
zero findings; `dirty.csv` still reports its real tail.

`sales.csv` produces **no findings at all**, and that is the correct answer — every
measurement sits far below its threshold, not just under it. Inventing findings from noise is
the failure this layer exists to avoid.

## `ai/`

Optional, and structured so that its absence changes nothing except the prose.

| File | Responsibility |
|---|---|
| `llm_client.py` | The only place that talks to a model |
| `prompt_builder.py` | The system prompt and the payload |
| `verification.py` | Number traceability and causation checks |
| `insight_explainer.py` | Orchestration, verification, caching |

### Four rules, four mechanisms

**The dataset never leaves the machine.** The payload holds the shape of the file, the quality
score, and the structured findings. A test gives every row a value that appears nowhere else
and asserts none of them reach the prompt; another compares the payload for a 30-row file and
a 6000-row file. Prompt size depends on how many findings there are, never on how many rows.

**Every number is checked.** Each quantity in the returned text is rebuilt from the metrics of
the finding it belongs to. Rounding is accepted — a rounded number is still the number —
while a number that was never given is not. An unverified explanation is **rejected whole,
not trimmed**: a sentence removed from the middle of a paragraph leaves prose that reads as
if it still makes its original point, which is worse than saying nothing.

**Causal claims are rejected.** Checked per sentence: a causal verb with no negation in the
same sentence fails. "Spending drives revenue" is dropped; "this does not show that one
causes the other" — the sentence the prompt asks for — is kept.

**No key means no degradation of the numbers.** `default_client()` returns `None` rather than
raising. The endpoint answers `available: false` with a reason, and the dashboard runs on the
computed messages. The LLM is a layer, not a dependency.

### The summary

One paragraph about the dataset as a whole, produced in the **same call** as the
explanations — the model already has every finding in front of it, and a second call would
cost twice and risk the two disagreeing.

It is verified against a wider pool: the metrics of every finding it drew on, merged under
namespaced keys so that reused names like `count` do not collide, plus the file's own facts —
rows, columns, missing share, duplicate rows, the score and its five dimensions.

Summary and explanations are verified separately. A fabricated number in the paragraph drops
the paragraph and leaves the explanations standing.

A dataset with **no findings still gets a summary**. That is precisely when a reader wants
someone to say that the file is clean and unremarkable.

## API

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/datasets/{id}/quality` | Issues **and the score**, most severe first |
| `GET` | `/api/datasets/{id}/analysis` | Statistics, correlations, **group comparisons, timelines** |
| `GET` | `/api/datasets/{id}/insights` | Ranked structured findings |
| `GET` | `/api/datasets/{id}/explanations` | Summary and per-finding explanations |

Explanations are a separate endpoint on purpose. The dashboard renders from the first three
and asks for this one afterwards, so a slow model — or no model — never holds the numbers off
the screen. Repeat requests for the same findings are served from a cache: the answer would
not change, and every call costs money.

Two requests for the same findings that arrive *together* wait behind one lock rather than
both proceeding. Reading a cache without one is only safe while callers arrive apart, and a
second open tab or a refresh taken while the first answer is still coming is enough to break
that — at which point the cache saves nothing and the file is explained twice at full price.

## Frontend

The page now leads with meaning rather than with charts:

```text
row / column / missing / duplicate tiles
quality score and its five dimensions
What stands out   ← summary paragraph, then ranked findings, each with its chart
data quality issues
other charts
columns
data preview
```

| File | Responsibility |
|---|---|
| `components/QualityScore.tsx` | Score and dimension bars |
| `components/InsightList.tsx` | Summary, ranked findings, empty state |
| `components/InsightCard.tsx` | One finding, its explanation, its caveats, its chart |
| `components/ExplanationsToggle.tsx` | The switch that decides whether a model is asked at all |
| `lib/explanations.ts` | Where that choice is kept and remembered |

A chart shown inside a finding is removed from the grid below, and the grid's heading changes
to "Other charts" when that has happened. Inside a card the chart's own title is hidden: the
sentence directly above it is already the caption.

When nothing stands out the list says so and says why, rather than rendering empty. When the
model wrote a summary, that paragraph replaces the fallback — the two are never both shown.

### The switch

Explanations sit behind a switch in the header, beside the theme toggle, and it is **off until
someone turns it on**. It governs the request rather than the display: turned off, the
dashboard never asks for `/explanations` at all, so a reader who came for the profile, the
quality score, the findings and the charts is billed nothing. None of those depend on it —
they are computed in Python — which is why spending is opted into rather than out of.

Only an explicit choice turns it on. A reader who has never touched it, a browser that refuses
storage, and a stored value written by some later version all land on the setting that costs
nothing.

Turned back on, it explains the dataset already on the screen instead of asking for the file
again. The request therefore lives in an effect keyed on the dataset and the switch, not in
the upload handler, and an explanation is held together with the id of the dataset it was
written about. That pairing is what lets the switch hide and restore prose without fetching it
twice, and what keeps the previous file's paragraph off the screen while the next one loads.

## Running it

As in MVP 1, plus an optional key:

```bash
# backend/.env
DATASIGHT_ANTHROPIC_API_KEY=sk-ant-...
```

Without it, everything works except the prose. With it, the prose still does not appear until
the header switch is turned on: the key makes explanations possible, not automatic, and the
browser remembers the choice. `backend/.env.example` lists the optional overrides
(`DATASIGHT_EXPLANATION_MODEL`, default `claude-sonnet-5`, and
`DATASIGHT_EXPLANATION_MAX_INSIGHTS`, default 8).

The file is located from `app/config.py` rather than from the working directory, so it is found
however the process was started. A relative path read the key when the server was launched from
`backend/` and quietly did not from anywhere else, which turns a missing explanation layer into
a puzzle with no error to read.

## Tests

```bash
cd backend && .venv/bin/python -m pytest tests -q
```

189 tests, up from 71. The AI layer is tested against an injected fake client; **the suite
makes no network calls and needs no API key.** That is enforced rather than assumed: a fixture
in `tests/conftest.py` clears the configured key for every test. Before it existed the promise
held only while no key was present — a key in the developer's own `.env` reached the endpoint
test for the no-key path, which then called the real API and billed for it.

Two tests are worth knowing about, because they encode the project's central claim rather
than a behaviour:

- `test_no_message_contains_a_number_that_is_not_in_its_metrics` — the generator cannot print
  a number it did not compute.
- `test_no_row_of_the_dataset_reaches_the_prompt` — the data does not leave the machine.
- `test_findings_asked_about_twice_at_once_are_still_explained_once` — the cache is a promise
  about money, and a promise that only holds when requests are politely spaced is not one.

## What the live path showed

The layer has now been run against the real API. Four defects were found, and all four were
one mistake wearing different clothes: **the checker did not recognise a number the prompt had
already shown the model.**

- The generator writes a magnitude unsigned — "revenue fell 31.6%" — against a metric of
  -0.316, and only the signed rendering was accepted. Every falling trend and every negative
  correlation failed. The generator's own messages did not pass their own check, and the test
  that claims they do used four rising fixtures.
- The payload carries `rows_behind_it` for every finding, but only some types repeat it inside
  `metrics`. A model that wrote "342 of the 360 rows" was rejected for quoting a number it had
  been handed.
- The dataset block — rows, columns, missing share, the score — was pooled when checking the
  summary and not when checking an individual explanation, so the file's own row count failed
  the same way.
- `due to` is in the causal phrase list, which read "unlikely to be due to chance" — the
  ordinary way to say a result is significant — as a claim that one column acts on another,
  and dropped the whole explanation for it.

The first was found without a key at all, by putting the prompt through a model by hand and
running the answer through the checker. The other three needed a real call.

With all four fixed, a run over a 360-row file returns a verified summary and two of its three
explanations, in both runs measured — a different explanation rejected each time. Those
rejections are the model's own: in one it wrote 9,949 for a mean of 9,948.47, and the check
refused it. That is the layer doing its job.

## Known gaps

Adaptive thinking is on for `claude-sonnet-5` whenever the `thinking` parameter is omitted, and
its tokens share the `max_tokens` budget with the answer. At three findings the response
finished well inside 1500; at the configured maximum of eight it has not been measured. A
truncated answer is not shortened prose but unparseable JSON, which drops the whole layer
rather than part of it.

How often a faithful explanation is still refused has not been measured over enough runs to put
a number on. Two of three, twice, is not a rate.

The histogram attached to a skew finding is accurate and hard to read: a long tail renders as
one tall bar and a row of invisible ones. A log axis is a presentation decision that has not
been made.

Correlation redundancy is resolved by coverage, not by partial correlation. Two relationships
that survive may still share most of their explanation.

## Not in MVP 2

Natural-language questions about the data, analysis planning, dynamic chart generation and
conversational follow-ups — all of MVP 3. The cleaning workflow, advanced anomaly detection
and any machine learning remain in MVP 4. The `anomaly/` package is still empty.
