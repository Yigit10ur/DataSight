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
4. Save the result as a derived dataset for further exploration, or download the transformed rows as CSV.

Excel imports read the first worksheet. The default upload limit is 100 MiB.

## Optional AI explanations

Create `backend/.env` using [backend/.env.example](backend/.env.example), or edit your existing file, and set:

```dotenv
DATASIGHT_ANTHROPIC_API_KEY=your_anthropic_api_key
```

Restart the backend, then turn on **AI** in the dashboard. The browser remembers your choice. Model calls use your Anthropic account and may incur charges.

The backend sends column names, dataset summary statistics, quality scores, and selected computed findings to Anthropic. It does not send the uploaded file or raw rows; findings can still contain category labels or other information derived from your data.

Generated explanations are checked for unsupported numbers and causal claims. If the model is unavailable or an explanation fails verification, the computed findings remain available.

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
npm run lint
npx tsc --noEmit
npm run build
```

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

The API currently has no authentication or per-user dataset access controls. Public hosting requires additional access controls and resource limits.

Natural-language questions and conversational follow-ups are planned. The current recipe interface offers structured transformations and analysis choices.

## Design notes

- [Project fundamentals](Project_Fundamentals.md): product vision and design principles.
- [MVP 1](MVP-1.md): core ingestion, profiling, analysis, and visualization engine.
- [MVP 2](MVP-2.md): quality scoring, ranked insights, and optional explanations.
- [MVP 2.5 plan](MVP-2.5-plan.md): design behind the no-code recipe workflow.
- [MVP 3 plan](MVP-3-plan.md): planned natural-language analysis.

These documents record implementation milestones and plans; some details describe earlier versions.

## License

[MIT](LICENSE) — Copyright (c) 2026 Yigit10ur.
