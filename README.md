# DataSight

Upload a CSV or Excel file to explore its structure, spot data quality issues, and discover statistical insights. Shape the data through a no-code recipe builder, preview the result, and export it as CSV.

Statistics, quality scores, findings, and chart data are all computed in Python. No API key or external service is needed.

## Features

- **Dataset profiling:** row and column counts, inferred column types, missing values, duplicates, and identifier detection.
- **Data quality checks:** a score out of 100, missing-value reports, outliers, inconsistent categories, whitespace issues, and numbers stored as text.
- **Exploratory analysis:** numeric distributions, category frequencies, Pearson and Spearman correlations, group comparisons, and time trends.
- **Ranked insights and charts:** findings paired with relevant interactive Plotly visualizations.
- **No-code recipes:** filter and sort rows, select and rename columns, change types, fill missing values, remove duplicates, derive columns, and aggregate groups.
- **Recipe previews and export:** inspect intermediate results, run a focused analysis, save a derived dataset in the current session, or download the transformed rows as CSV.
- **Dataset lineage:** follow a derived dataset back through the transformations that produced it.
- **Example dataset:** a 60-row synthetic CSV in [example-data/](example-data/), with planted quality issues, so a fresh clone has something to upload.
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

New here? Follow the [walkthrough with the example data](#walkthrough-with-the-example-data)
below, which needs no dataset of your own. Otherwise:

1. Upload a `.csv` or `.xlsx` file.
2. Review the dataset profile, quality report, ranked findings, and charts.
3. Use **Shape this data** and the column menus to build a recipe and preview its results.
4. Save the result as a derived dataset for further exploration, or download the transformed rows as CSV.

Excel imports read the first worksheet. The default upload limit is 100 MiB, and a
file may have at most 1,000 columns.
Files exceeding the configured limit receive HTTP 413. The application reads in
chunks and stops after at most the limit plus one byte, before parsing or storing
an oversized file. Existing CSV and XLSX content validation still applies.

Datasets are temporary: by default, an upload and every dataset derived from it
expire **one hour after the original upload**. Reading, previewing, and saving a
recipe do not reset this deadline. Expired IDs return `404 Dataset not found.`
Export your results with **Download CSV** before they expire.

## Walkthrough with the example data

[example-data/orders-sample.csv](example-data/orders-sample.csv) is a 60-row synthetic
sales extract committed to this repository, so a fresh clone has something to upload.
It is invented data with deliberate defects in it: every
number below is computed in Python. See
[example-data/README.md](example-data/README.md) for the columns and the full list of
planted issues.

The steps are written out rather than shown in screenshots or a recording: a picture
of the interface goes stale the first time a label moves, and nothing fails to say so.
These figures have a test behind them instead — see [Verifying it](#verifying-it).

### 1. Start the app and upload the file

Start the backend and the frontend as described under [Run locally](#run-locally),
then open [http://localhost:3000](http://localhost:3000). Drop
`example-data/orders-sample.csv` onto the upload area, or click it and pick the file.

The dashboard appears with four tiles across the top:

| Rows | Columns | Missing cells | Duplicate rows |
| --- | --- | --- | --- |
| 60 | 9 | 1.3% (7 cells) | 3 |

Below them, the type badges read 4 numeric, 3 categorical, 1 datetime, 1 text.
`discount_pct` is counted as categorical rather than numeric, which is one of the
quality findings below.

### 2. Read three of the findings

**Data quality** reports a score of **80** out of 100 and lists 9 issues, 6 of them
warnings. **What stands out** lists 10 findings, most important first. Three worth
stopping on:

1. **Three rows are duplicates.** Data quality: *"3 rows (5.0%) are exact duplicates
   of another row."* `ORD-1004`, `ORD-1023`, and `ORD-1045` each appear twice, the way
   a double import leaves them. Any total computed now counts those orders twice.

2. **`discount_pct` holds numbers written as text.** Data quality: *"discount_pct is
   stored as text but 93% of its values are numeric, so it is excluded from numeric
   analysis."* Four rows say `pending`, and those four keep the whole column out of
   the numeric charts — it appears under **Charts** as a bar chart of most common
   values rather than as a distribution.

3. **Orders are much larger in one region.** The leading finding under **What stands
   out**: *"region = West has 1.8x the average order_total of North (440.5 against
   239.5 across 60 rows)."* It comes with a box plot of `order_total` by `region`.

The quality report also flags `delivery_days` missing in 11.7% of rows, three
deliveries far outside the interquartile range, and `channel` spellings that differ
only in case or spacing (`Online` / `online` / `" Online"`).

### 3. Apply a recipe

Finding 3 is worth a real answer — revenue by region — but finding 1 says the raw
totals are wrong. The recipe fixes that first. Scroll to **Shape this data**:

1. In the **Recipe** panel, click **+ add a step**, choose **Remove duplicate rows**
   under *Rows*, and click **Add**. The preview footer now reads `60 → 57 rows`.
2. In the preview table, click the **`region`** column heading, choose **Group by this
   and summarise** under *Summarise*, set *taking the* to **total** and *of* to
   **`order_total`**, and click **Add**.

The preview footer reads `60 → 4 rows · 9 → 2 columns`, and the table shows:

| region | sum_order_total |
| --- | --- |
| East | 4698.53 |
| North | 3523.1 |
| South | 3914.06 |
| West | 6083.31 |

Removing the duplicates is what makes these right. Delete the first step with the
**×** next to it and East, North, and West jump to 4991.21, 3831.54, and 6606.83 —
three regions overstated by one repeated order each. Add the step back before
carrying on.

### 4. Export the result

Click **Download CSV** in the Recipe panel. The browser saves
`orders-sample (2 steps).csv`, holding the four rows above. The export runs the
recipe again and streams the rows; it stores nothing, so the download does not create
a dataset or extend anything's lifetime.

Totals are written at full floating-point precision, so the file reads
`West,6083.3099999999995` where the table on screen rounds to `6083.31`. Any
spreadsheet or reader will show the rounded figure.

**Save as a dataset** instead keeps the four rows in the backend as a dataset of its
own, with its own profile, findings, and lineage back to the upload. That dataset
expires with the original upload — one hour after it — so download anything you want
to keep.

### Verifying it

Every figure quoted above is asserted in
[backend/tests/test_example_dataset.py](backend/tests/test_example_dataset.py), which
reads the committed file exactly as an upload does. The example is deterministic, so
a change to an analysis threshold — a missing-value band, a Tukey fence, the
effect-size floor — fails that test instead of quietly making this walkthrough wrong.
Run it on its own with:

```bash
cd backend
.venv/bin/python -m pytest tests/test_example_dataset.py -q
```

## Configuration

Backend settings are defined in [backend/app/config.py](backend/app/config.py) and can be supplied through environment variables or `backend/.env`.

`backend/.env` may only contain the backend settings below. The backend refuses to start if
the file has any other key, including `DATASIGHT_ANTHROPIC_API_KEY` and the
`DATASIGHT_EXPLANATION_*` settings from earlier versions; delete those lines. Unrecognised
environment variables are ignored.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATASIGHT_MAX_UPLOAD_BYTES` | `104857600` | Maximum accepted file size in bytes. |
| `DATASIGHT_DATASET_TTL_SECONDS` | `3600` | Fixed lifetime of an upload and its descendants, in seconds. Must be positive and finite. |
| `DATASIGHT_MAX_DATASETS` | `100` | Maximum total uploaded and derived datasets retained by the backend process. Must be positive. |
| `DATASIGHT_DASHBOARD_CACHE_SIZE` | `16` | Maximum datasets whose computed dashboard results are retained. Must be positive. |
| `DATASIGHT_API_DOCS` | `true` | Serves the interactive API docs at `/docs`, `/redoc`, and `/openapi.json`. Set to `false` where the API is public. |
| `DATASIGHT_CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed frontend origins, expressed as a JSON array. |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend setting; configure in `frontend/.env.local`. |

## Deploy

[compose.yaml](compose.yaml) runs the production stack on any server with Docker:
the backend and frontend images, and a [Caddy](https://caddyserver.com) proxy
([deploy/Caddyfile](deploy/Caddyfile)) that is the only public entry point. Caddy
obtains the HTTPS certificate automatically, puts the site behind one shared login,
rate-limits requests, rejects oversized uploads before they reach the backend, and
sets security headers. The site is served from one domain: `/api/*` goes to the
backend and everything else to the frontend.

1. Point the domain's DNS at the server and open ports 80 and 443.
2. Copy [.env.example](.env.example) to `.env` and set the domain, a login name, and
   a password hash from `docker run --rm caddy:2 caddy hash-password`.
3. Run `docker compose up -d --build`.

The backend runs as a single worker with a memory limit and restarts if it is
killed. A restart loses every dataset held in memory. Size
`DATASIGHT_MAX_UPLOAD_BYTES`, `DATASIGHT_MAX_DATASETS`, and `DATASIGHT_BACKEND_MEMORY`
to the server's RAM.

## Development checks

Run the backend tests from the repository root:

```bash
cd backend
.venv/bin/python -m pytest tests -q
```

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
No running backend is needed. `typecheck` generates Next.js route types
before checking TypeScript, so it also works on a fresh clone.

[CI](.github/workflows/ci.yml) runs on pull requests and pushes to `main`, using
Python 3.12 and Node.js 20.9.0 (the minimum supported version), with pip and npm
dependency caches. Backend tests, frontend tests, lint, type checking, and the
production build must all succeed; any failed command fails its job. The production build downloads Google fonts, so it needs
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
    api/             FastAPI endpoints
    dashboard.py     Shared bounded dashboard computation cache
    provenance.py    What a recipe changed about the meaning of a dataset's rows
    store.py         In-memory datasets and lineage
  tests/             Backend test suite
example-data/      Synthetic sample CSV used by the walkthrough
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
cached dashboard results. Derived datasets share the original upload's deadline,
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
endpoint response shapes are unchanged.

The dashboard cache defaults to 16 datasets and uses least-recently-used eviction.
Entries are keyed by dataset ID, so uploaded and derived datasets cannot share
results. They contain Pydantic result models, including bounded chart arrays, but no
DataFrame copies. This trades some memory for fewer repeated calculations; lower
`DATASIGHT_DASHBOARD_CACHE_SIZE` where memory is tighter. Dataset expiration or
removal clears its cache entry immediately.

## Design notes

- [Project fundamentals](Project_Fundamentals.md): product vision and design principles.
- [MVP 1](MVP-1.md): core ingestion, profiling, analysis, and visualization engine.
- [MVP 2](MVP-2.md): quality scoring and ranked insights.
- [MVP 2.5 plan](MVP-2.5-plan.md): design behind the no-code recipe workflow.
- [MVP 3 plan](MVP-3-plan.md): Ask Your Data, a natural-language question feature that was built and later removed.

These documents record implementation milestones and plans. Some details describe earlier
versions, including an optional LLM layer (MVP 2 explanations and MVP 3 questions) that has
since been removed; each document opens with a note on its current status.

## License

[MIT](LICENSE) — Copyright (c) 2026 Yigit10ur.
