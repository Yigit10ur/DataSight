# MVP 1 — Core Data Engine

> **Status:** historical record. The LLM layer mentioned below was added in MVP 2 and later
> removed; DataSight now has no model at all. See [README.md](README.md) for the current app.

MVP 1 delivers the first half of the product promise in `Project_Fundamentals.md`: upload a
CSV or Excel file and immediately see what is in it — its shape, its column types, its quality
problems, its distributions and its relationships.

There is no AI in MVP 1. Every number shown to the user is computed by Python. The LLM layer
arrives in MVP 2 and will explain these results rather than produce them.

## What a dataset goes through

```text
CSV / Excel upload
        ↓
validation + parsing        (ingestion/)
        ↓
schema + dataset profile    (profiling/)
        ↓
quality issues              (quality/)
        ↓
statistics + correlations   (analysis/)
        ↓
chart selection             (visualization/)
        ↓
dashboard                   (frontend/)
```

## Backend

Python 3.12, FastAPI, pandas. Each module owns one step and depends only on the steps before it.

### `ingestion/`

| File | Responsibility |
|---|---|
| `validator.py` | Extension, size, empty-file and header-only checks before anything is parsed |
| `csv_loader.py` | CSV parsing with delimiter sniffing and an encoding fallback chain |
| `excel_loader.py` | First sheet of an `.xlsx` workbook |

Delimiter sniffing and the `utf-8 → utf-8-sig → latin-1` fallback exist because semicolon-separated
and latin-1 encoded exports are the normal output of Excel in many locales, and neither should
require the user to fix the file first.

### `profiling/`

| File | Responsibility |
|---|---|
| `schema_detector.py` | Semantic column type, independent of the pandas dtype |
| `dataset_profiler.py` | Dataset overview: rows, columns, type counts, missing cells, duplicates |
| `preview.py` | First N rows as JSON-safe records |

Columns are classified as `numeric`, `categorical`, `boolean`, `datetime`, `text` or `empty`, and
carry three flags: `is_constant`, `is_probable_id`, `is_high_cardinality`.

Two rules here are deliberately narrow, because a false flag is worse than a missing one:

- **Identifier detection** requires near-total uniqueness *and* either an id-like column name or a
  categorical type. Free text is near-unique too, and calling a comment field an identifier would
  wrongly exclude it from analysis.
- **High cardinality** is only reported for categorical and text columns. Five hundred distinct
  values is normal for a measured number and meaningless as a warning.

### `quality/`

| File | Detects |
|---|---|
| `missing_detector.py` | Missing values (severity by share), fully empty columns |
| `duplicate_detector.py` | Exact duplicate rows |
| `structure_detector.py` | IQR outliers, constant / identifier / high-cardinality columns |
| `consistency_checker.py` | Suspicious category spellings, stray whitespace, numbers stored as text |

Issues are returned ranked by severity (`serious` → `warning` → `info`).

Category comparison normalises with NFKD and strips combining marks before folding case.
`str.casefold()` alone keeps the dot on Turkish dotted capitals, which leaves `"İstanbul"`,
`"istanbul"` and `"Istanbul"` as three separate cities.

The engine **reports** problems and never modifies the dataset. A chart may therefore show one
city split across several bars; the quality panel above it explains why.

### `analysis/`

| File | Produces |
|---|---|
| `numeric_analysis.py` | Mean, median, std, quartiles, skewness, IQR outlier count, histogram bins |
| `categorical_analysis.py` | Frequencies, top categories, rare category count |
| `correlation_analysis.py` | Pearson and Spearman per numeric pair, strongest first |

Both correlation coefficients are computed because they disagree in exactly the case that matters.
On one test dataset a handful of extreme revenue values pulled Pearson down to 0.15 while the rank
correlation stayed at 0.94. Reporting only Pearson would have hidden a real relationship.

Identifier columns and zero-variance columns are excluded — their statistics describe nothing.

### `visualization/`

| File | Responsibility |
|---|---|
| `chart_selector.py` | Which charts are worth showing, and in what order |
| `chart_generator.py` | The data behind each chart, computed in pandas |

Selection follows the rules in `Project_Fundamentals.md` section 12, with relationships and trends
placed before single-column distributions: a correlation or a trend says more about a dataset than
another histogram.

A pair qualifies for a scatter plot on the **stronger of its two coefficients**, and the chart title
reports both (`r = 0.15, ρ = 0.94`) so the reader sees the disagreement rather than a single number.

The backend returns chart **specifications** — type, labels and precomputed data (histogram bins,
box-plot quartiles, resampled time series, correlation matrix) — not rendered figures. Quartiles and
bins are analysis and belong in Python; colours and layout are presentation and belong in the
frontend. This is what keeps the theme switch working without the backend knowing about themes.

### Storage

`store.py` keeps uploaded frames in memory, keyed by a `dataset_id` returned from the upload. Later
endpoints reuse that id, so no analysis requires a re-upload and no database is needed yet.
Datasets do not survive a server restart.

## API

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/health` | Service status |
| `POST` | `/api/upload` | Dataset profile, including the `dataset_id` used below |
| `GET` | `/api/datasets/{id}/profile` | The stored profile |
| `GET` | `/api/datasets/{id}/preview` | First `limit` rows (default 25, max 200) |
| `GET` | `/api/datasets/{id}/quality` | Quality issues, most severe first |
| `GET` | `/api/datasets/{id}/analysis` | Per-column statistics and correlations |
| `GET` | `/api/datasets/{id}/charts` | Chart specifications |

Rejected uploads return `400` with the validation message; unknown dataset ids return `404`.

Preview rows are serialised through pandas `to_json`, which turns `NaN` into `null` and numpy and
datetime scalars into JSON primitives. Python's own `json.dumps` emits bare `NaN`, which is not
valid JSON and cannot be parsed by the browser.

## Frontend

Next.js 16, TypeScript, Tailwind.

| File | Responsibility |
|---|---|
| `app/page.tsx` | Upload flow and page composition |
| `components/UploadDropzone.tsx` | Drag-and-drop and file picker |
| `components/ProfileOverview.tsx` | Row/column/missing/duplicate tiles and the type breakdown |
| `components/QualityIssues.tsx` | Quality issues, ranked |
| `components/ChartGrid.tsx`, `Chart.tsx` | Chart rendering |
| `components/ColumnTable.tsx` | Per-column schema and flags |
| `components/PreviewTable.tsx` | Raw data preview |
| `lib/api.ts` | Typed API client |
| `lib/charts.ts` | Chart spec → Plotly data and layout |

Plotly is loaded on demand inside the chart component, so its bundle stays out of the initial page
load. Chart colours are read from CSS custom properties at draw time and the chart is redrawn when
the colour scheme changes, which is what makes light and dark mode work without a second palette in
the backend.

The quality panel sits above the charts so a reader meets the explanation before the chart it
explains.

## Running it

```bash
# backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000

# frontend
cd frontend
npm install
npm run dev
```

The frontend reads the backend URL from `NEXT_PUBLIC_API_URL` (see `frontend/.env.example`).

## Tests

```bash
cd backend && .venv/bin/python -m pytest tests -q
```

71 tests cover ingestion, type detection, profiling, statistics, correlations, chart selection,
quality detection and the API surface.

## Not in MVP 1

Insight generation and ranking, LLM explanations, the data quality score, natural-language
questions, the cleaning workflow, advanced anomaly detection and any machine learning. The
`ai/`, `insights/` and `anomaly/` packages exist but are empty.

MVP 2 adds the structured insight model, insight ranking and the LLM explanation layer on top of
the results this engine already produces.
