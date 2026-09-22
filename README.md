# DataSight

Upload a CSV or Excel file to explore its structure, spot data quality issues, and discover statistical insights. Shape the data through a no-code recipe builder, preview the result, and export it as CSV.

**Python calculates. AI explains.** Statistics, quality scores, findings, and chart data are computed in Python. Optional AI explanations turn those results into plain language; the core application works without an API key.

## Features

- **Dataset profiling:** row and column counts, inferred column types, missing values, duplicates, and identifier detection.
- **Data quality checks:** a score out of 100, missing-value reports, outliers, inconsistent categories, whitespace issues, and numbers stored as text.
- **Exploratory analysis:** numeric distributions, category frequencies, Pearson and Spearman correlations, group comparisons, and time trends.
- **Ranked insights and charts:** findings paired with relevant interactive Plotly visualizations.
- **No-code recipes:** filter and sort rows, select and rename columns, change types, fill missing values, remove duplicates, derive columns, and aggregate groups.
- **Recipe previews and export:** inspect intermediate results, run a focused analysis, save a derived dataset in the current session, or download the transformed rows as CSV.
- **Dataset lineage:** follow a derived dataset back through the transformations that produced it.
- **Optional AI explanations:** enable plain-language summaries and explanations from the dashboard. Explanations are off by default.
- **Ask Your Data:** turn on AI to ask validated natural-language questions, with Python-computed answers, charts, and contextual follow-ups.
- **Light and dark themes.**

## Run locally

### Requirements

- Python 3.12, used by the project's development environment.
- Node.js 20.9 or newer and npm.

Run the backend and frontend in separate terminals. The commands below assume macOS or Linux and start from the repository root.

### Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

The backend runs at [http://localhost:8000](http://localhost:8000). Interactive API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs), and the health endpoint is [http://localhost:8000/api/health](http://localhost:8000/api/health).

### Frontend

In a second terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

The frontend connects to `http://localhost:8000` by default. To use another backend address, create `frontend/.env.local` using [frontend/.env.example](frontend/.env.example) and set `NEXT_PUBLIC_API_URL` to the backend's base URL, without `/api`. Restart the frontend after changing it.

### Try it

1. Upload a `.csv` or `.xlsx` file.
2. Review the dataset profile, quality report, ranked findings, and charts.
3. Use **Shape this data** and the column menus to build a recipe and preview its results.
4. Turn on **AI** and use **Ask your data** for questions such as “Which products generate the most revenue?”
5. Save the result as a derived dataset for further exploration, or download the transformed rows as CSV.

Excel imports read the first worksheet. The default upload limit is 100 MiB.
Files exceeding the configured limit receive HTTP 413. The application reads in
chunks and stops after at most the limit plus one byte, before parsing or storing
an oversized file. Existing CSV and XLSX content validation still applies.

Datasets are temporary: by default, an upload and every dataset derived from it
expire **one hour after the original upload**. Reading, previewing, and saving a
recipe do not reset this deadline. Expired IDs return `404 Dataset not found.`
Export your results with **Download CSV** before they expire.

## Optional AI explanations

Create `backend/.env` using [backend/.env.example](backend/.env.example), or edit your existing file, and set:

```dotenv
DATASIGHT_ANTHROPIC_API_KEY=your_anthropic_api_key
```

Restart the backend, then turn on **AI** in the dashboard. The browser remembers your choice. Model calls use your Anthropic account and may incur charges.

The backend sends column names, dataset summary statistics, quality scores, and selected computed findings to Anthropic. It does not send the uploaded file or raw rows; findings can still contain category labels or other information derived from your data.

Generated explanations are checked for unsupported numbers and causal claims. If the model is unavailable or an explanation fails verification, the computed findings remain available.

Ask Your Data uses two model calls for a successful new question: one selects a complete plan
from a closed vocabulary, then Python validates and executes it; the other explains
the verified result. No model-generated Python, SQL, pandas expression, `eval`, or
`DataFrame.query` is accepted. Planning prompts contain schema metadata but no
sample values or raw rows. Explanation results are capped at 20 aggregate rows;
identifier-like, high-cardinality, and near-unique groupings are refused. Identical
questions with the same resolved context reuse their stored response.

Both `backend/.env` and `frontend/.env.local` are ignored by Git. Keep API keys in the backend environment file.

## Configuration

Backend settings are defined in [backend/app/config.py](backend/app/config.py) and can be supplied through environment variables or `backend/.env`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATASIGHT_ANTHROPIC_API_KEY` | Empty | Enables access to the optional explanation service. |
| `DATASIGHT_EXPLANATION_MODEL` | `claude-sonnet-5` | Model identifier passed to Anthropic; set this to a model available to your account. |
| `DATASIGHT_EXPLANATION_MAX_INSIGHTS` | `8` | Maximum number of findings submitted for explanation. |
| `DATASIGHT_EXPLANATION_MAX_TOKENS` | `1500` | Output token budget per model request. |
| `DATASIGHT_EXPLANATION_TIMEOUT_SECONDS` | `30` | Model request timeout in seconds. |
| `DATASIGHT_MAX_UPLOAD_BYTES` | `104857600` | Maximum accepted file size in bytes. |
| `DATASIGHT_DATASET_TTL_SECONDS` | `3600` | Fixed lifetime of an upload and its descendants, in seconds. Must be positive and finite. |
| `DATASIGHT_MAX_DATASETS` | `100` | Maximum total uploaded and derived datasets retained by the backend process. Must be positive. |
| `DATASIGHT_DASHBOARD_CACHE_SIZE` | `16` | Maximum datasets whose computed dashboard results are retained. Must be positive. |
| `DATASIGHT_QUESTION_MAX_TURNS` | `10` | Maximum successful Ask Your Data turns retained per dataset. Must be positive. |
| `DATASIGHT_CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed frontend origins, expressed as a JSON array. |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend setting; configure in `frontend/.env.local`. |

## Development checks

Run the backend tests from the repository root:

```bash
cd backend
.venv/bin/python -m pytest tests -q
```

Tests use fake model clients and clear the configured API key, so they do not require an Anthropic key or make model API calls.

Run frontend checks from the repository root in another terminal:

```bash
cd frontend
npm test
npm run lint
npm run typecheck
npm run build
```

`npm test` runs the Vitest and React Testing Library interaction suite once;
`npm run test:watch` reruns tests while editing. Tests cover file upload and its
loading state, computed dashboard results, API errors and retry, and adding and
removing a recipe step with a preview. HTTP responses are mocked at the fetch
boundary, and Plotly drawing is stubbed because jsdom has no canvas renderer.
No running backend or API key is needed. `typecheck` generates Next.js route types
before checking TypeScript, so it also works on a fresh clone.

[CI](.github/workflows/ci.yml) runs on pull requests and pushes to `main`, using
Python 3.12 and Node.js 20.9.0 (the minimum supported version), with pip and npm
dependency caches. Backend tests, frontend tests, lint, type checking, and the
production build must all succeed; any failed command fails its job. CI does not
use an Anthropic secret. The production build downloads Google fonts, so it needs
network access even though tests do not.

## Project structure

```text
backend/
  app/
    ingestion/       CSV and Excel parsing and validation
    profiling/       Schema detection and dataset summaries
    quality/         Quality checks and scoring
    analysis/        Statistical analysis
    insights/        Finding generation and ranking
    visualization/   Chart selection and chart data
    recipes/         Transformation validation and execution
    ai/              Optional explanations and verification
    api/             FastAPI endpoints
    dashboard.py     Shared bounded dashboard computation cache
    questions/       Typed question plans, validation, execution, and verified explanations
    store.py         In-memory datasets and lineage
  tests/             Backend test suite
frontend/
  app/               Next.js pages, layout, and styles
  components/        Dashboard, charts, and recipe interface
  lib/               API client and frontend helpers
```

The backend uses FastAPI, pandas, NumPy, and SciPy. The frontend uses Next.js, React, TypeScript, Tailwind CSS, and Plotly.

## Current scope

DataSight is a development-stage application. Uploaded and derived datasets are held in backend memory and are lost when the backend restarts, including development reloads. Use CSV export to keep transformed data. Run a single backend process; dataset storage is not shared across workers.

Expired datasets are removed during store access and by an idle sweep every 60
seconds. Removal includes dependent recipes, profiles, cached derived frames, and
cached dashboard results and AI explanations. Derived datasets share the original upload's deadline,
so lineage never points to an expired parent. A full store refuses new uploads
and derived saves with HTTP 409 instead of evicting work that has not expired.
Expired entries are reclaimed before checking capacity. The count limit includes
derived recipe records; the existing four-frame derived cache, per-parent limit
of 20 children, and lineage depth limit of 10 also apply.

These are retention bounds, **not a total process-memory budget**. Parsed CSV data
and decompressed XLSX workbooks can be much larger than the upload; parsing,
profiling, analyses, and recipes can allocate temporary copies. In-flight requests
may keep references until they finish. The multipart parser receives and spools
the request before the route's bounded read, so the route limit does not bound
incoming traffic or temporary disk usage. Before public hosting, add reverse-proxy
body limits, request/concurrency limits, parsing time and memory budgets, XLSX
expansion limits, and disk quotas. The API also has no authentication or per-user
dataset access controls, and no durable storage; those capabilities must be planned
separately before accepting private data from unrelated users.

Dashboard endpoints share one deterministic computation per dataset. For a normal
dashboard load (`charts`, `quality`, and `insights`), the previous request path ran
the main analysis twice, chart generation twice, and quality checks twice. The
shared path runs analysis, quality, chart generation, and insight generation once
each; concurrent requests for the same dataset wait for that result. The existing
endpoint response shapes are unchanged, and optional AI explanations remain a
separate request that reuses the verified computed results.

The dashboard cache defaults to 16 datasets and uses least-recently-used eviction.
Entries are keyed by dataset ID, so uploaded and derived datasets cannot share
results. They contain Pydantic result models, including bounded chart arrays, but no
DataFrame copies. This trades some memory for fewer repeated calculations; lower
`DATASIGHT_DASHBOARD_CACHE_SIZE` where memory is tighter. Dataset expiration or
removal clears its cache entry immediately.

Ask Your Data conversations are temporary and expire with their dataset. The
current operation vocabulary covers aggregation, ranking, comparison,
relationships, trends, distributions, counts, and column descriptions. Causal
diagnosis, forecasting, arbitrary multi-stage programs, and interactive ambiguity
clarification remain outside the MVP; see [MVP 3](MVP-3-plan.md).

## Design notes

- [Project fundamentals](Project_Fundamentals.md): product vision and design principles.
- [MVP 1](MVP-1.md): core ingestion, profiling, analysis, and visualization engine.
- [MVP 2](MVP-2.md): quality scoring, ranked insights, and optional explanations.
- [MVP 2.5 plan](MVP-2.5-plan.md): design behind the no-code recipe workflow.
- [MVP 3](MVP-3-plan.md): implemented natural-language analysis and remaining scope.

These documents record implementation milestones and plans; some details describe earlier versions.

## License

[MIT](LICENSE) — Copyright (c) 2026 Yigit10ur.
