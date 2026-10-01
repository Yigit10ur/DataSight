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
- **Accounts:** anyone can sign up with a username and password, or with a Google or
  GitHub account once [set up](#signing-in-with-google); each account sees only its
  own datasets.
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
python -m pip install -r requirements-dev.txt
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

1. Create an account (**Create an account** under the log-in form), or log in.
2. Upload a `.csv` or `.xlsx` file.
3. Review the dataset profile, quality report, ranked findings, and charts.
4. Use **Shape this data** and the column menus to build a recipe and preview its results.
5. Save the result as a derived dataset for further exploration, or download the transformed rows as CSV.

Excel imports read the first worksheet. The default upload limit is 100 MiB, a
file may have at most 1,000 columns, and a workbook may unpack to at most 128 MiB.
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
then open [http://localhost:3000](http://localhost:3000) and create an account. Drop
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
| `DATASIGHT_MAX_STORE_BYTES` | `1073741824` | Memory the retained datasets may occupy, as pandas measures them. Cached derived frames give way first; past that, uploads and derived saves receive HTTP 409. |
| `DATASIGHT_MAX_CONCURRENT_JOBS` | `2` | Parses, dashboard computations, and recipe runs allowed at once; others wait their turn. |
| `DATASIGHT_MAX_WORKBOOK_BYTES` | `134217728` | Maximum unpacked size of an `.xlsx`, checked before it is read. |
| `DATASIGHT_MAX_USER_STORE_BYTES` | `268435456` | One account's share of `DATASIGHT_MAX_STORE_BYTES`, counted over its uploads. |
| `DATASIGHT_MAX_DATASETS_PER_USER` | `20` | One account's share of `DATASIGHT_MAX_DATASETS`, uploaded and derived. |
| `DATASIGHT_DATABASE_PATH` | `backend/datasight.db` | SQLite file holding accounts and sessions. Created on first use. |
| `DATASIGHT_SESSION_TTL_SECONDS` | `604800` | How long a log-in lasts, in seconds (7 days). |
| `DATASIGHT_SECURE_COOKIES` | `false` | Sends the session cookie over HTTPS only. Leave off for local http; the deployment turns it on. |
| `DATASIGHT_GOOGLE_CLIENT_ID` | empty | OAuth client ID for signing in with Google. Google is offered only when this and the secret are set. |
| `DATASIGHT_GOOGLE_CLIENT_SECRET` | empty | That OAuth client's secret. |
| `DATASIGHT_GOOGLE_REDIRECT_URI` | `http://localhost:8000/api/auth/google/callback` | Where Google returns the browser; must be listed in the OAuth client exactly. |
| `DATASIGHT_GITHUB_CLIENT_ID` | empty | GitHub OAuth app's client ID. GitHub is offered only when this and the secret are set. |
| `DATASIGHT_GITHUB_CLIENT_SECRET` | empty | That OAuth app's client secret. |
| `DATASIGHT_GITHUB_REDIRECT_URI` | `http://localhost:8000/api/auth/github/callback` | Where GitHub returns the browser; must be the OAuth app's callback URL. |
| `DATASIGHT_APP_URL` | `http://localhost:3000` | The frontend's address, where the browser lands after signing in with Google. |
| `DATASIGHT_DASHBOARD_CACHE_SIZE` | `16` | Maximum datasets whose computed dashboard results are retained. Must be positive. |
| `DATASIGHT_API_DOCS` | `true` | Serves the interactive API docs at `/docs`, `/redoc`, and `/openapi.json`. Set to `false` where the API is public. |
| `DATASIGHT_CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed frontend origins, expressed as a JSON array. They receive credentialed access, and writes from any other origin are refused. |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend setting; configure in `frontend/.env.local`. |

## Signing in with Google

Google sign-in is off until it has an OAuth client, which you create once in
[Google Cloud](https://console.cloud.google.com):

1. Create or pick a project. Under **APIs & Services → OAuth consent screen**, set it up
   as **External**, with an app name and your email. The only scopes used are
   `openid` and `email`, which need no review by Google.
2. Under **APIs & Services → Credentials**, choose **Create credentials → OAuth client
   ID**, of type **Web application**.
3. Add the authorized redirect URIs: `http://localhost:8000/api/auth/google/callback`
   for local development, and `https://<your domain>/api/auth/google/callback` for the
   deployment.
4. Put the client ID and secret in `backend/.env` locally, or in the deployment's
   `.env`, as `DATASIGHT_GOOGLE_CLIENT_ID` and `DATASIGHT_GOOGLE_CLIENT_SECRET`, and
   restart the backend.

While the consent screen is in **Testing**, only the Google accounts listed as its
test users can sign in; publish it to open sign-in to every Google account.

A Google account becomes a DataSight account on its first sign-in, named after the
part of its address before the `@` (with a number added if that name is taken). It
is matched on Google's ID for the account, not the address, and has no password.
Accounts made with a password are not joined to Google ones.

## Signing in with GitHub

GitHub sign-in is off until it has an OAuth app, which you register once on GitHub:

1. Open **Settings → Developer settings → OAuth Apps → New OAuth App** (or go to
   <https://github.com/settings/applications/new>).
2. **Application name:** `DataSight`. **Homepage URL:** `http://localhost:3000`.
   **Authorization callback URL:** `http://localhost:8000/api/auth/github/callback`.
   Leave **Enable Device Flow** off, and click **Register application**.
3. Copy the **Client ID**, click **Generate a new client secret**, and copy the secret.
4. Put both in `backend/.env` as `DATASIGHT_GITHUB_CLIENT_ID` and
   `DATASIGHT_GITHUB_CLIENT_SECRET`, and restart the backend.

An OAuth app has a single callback URL, so the deployment needs a second app whose
callback URL is `https://<your domain>/api/auth/github/callback` and whose homepage
is `https://<your domain>`, with its ID and secret in the deployment's `.env`.

No permissions are requested: DataSight reads only the public profile. A GitHub
account becomes a DataSight account on its first sign-in, named after its GitHub
username, and is matched on GitHub's permanent ID for it, so renaming on GitHub
keeps the same DataSight account. Accounts from Google, GitHub, and passwords are
never joined to one another.

## Deploy

[compose.yaml](compose.yaml) runs the production stack on any server with Docker:
the backend and frontend images, and a [Caddy](https://caddyserver.com) proxy
([deploy/Caddyfile](deploy/Caddyfile)) that is the only public entry point. Caddy
obtains the HTTPS certificate automatically, rate-limits requests (log-in and
sign-up to 10 a minute per address), rejects oversized uploads before they reach the
backend, and sets security headers. The site is served from one domain: `/api/*`
goes to the backend and everything else to the frontend.

1. Point the domain's DNS at the server and open ports 80 and 443.
2. Copy [.env.example](.env.example) to `.env` and set the domain.
3. Run `docker compose up -d --build`.

Sign-up is open: anyone who reaches the site can create an account. Accounts and
sessions are kept in SQLite on the `datasight_data` volume, so they survive restarts
and rebuilds; back up that volume to keep them. Each account may hold 10 datasets
and 160 MB of uploads by default, so no single sign-up can fill the server. There is
no password reset, since the server sends no email.

Each container keeps at most 50 MB of logs (`docker compose logs` reads them).
The backend runs as a single worker with a memory limit and restarts if it is
killed. A restart loses every dataset held in memory, so the defaults keep the
backend inside its 2 GB: 640 MB of retained datasets, two jobs at a time, 25 MiB
uploads, and workbooks that unpack to at most 128 MiB. Raising
`DATASIGHT_BACKEND_MEMORY` means raising `DATASIGHT_MAX_STORE_BYTES` with it; raising
the upload or workbook limit, or the job count, means leaving more of the memory
unclaimed by datasets. Measured on a 25 MB CSV: 154 MB once stored, about 450 MB
while it is parsed and analysed.

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
network access even though tests do not. A third job builds the production Docker
images, starts the backend and frontend until both report healthy, and validates
the Caddy configuration.

`backend/requirements.txt` holds what the server runs and is all the Docker image
installs; `backend/requirements-dev.txt` adds the test tools.

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
    accounts/        Users, password hashing, and sessions in SQLite
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

Memory is bounded in two parts. Retained frames, uploaded and cached derived, count
against `DATASIGHT_MAX_STORE_BYTES`; cached derived frames are dropped first, since
any can be rebuilt from its recipe. Work in flight is bounded by
`DATASIGHT_MAX_CONCURRENT_JOBS`, since parsing, profiling, analyses, and recipes
allocate temporary copies several times a frame's size. Workbooks are refused
before reading if they would unpack past `DATASIGHT_MAX_WORKBOOK_BYTES`. These are
estimates rather than a hard ceiling, which is why the deployment also sets a
container memory limit.

A job cannot be interrupted once started, so there is no time limit beyond what
the upload and workbook limits imply. The multipart parser receives and spools the
request before the route's bounded read; in the [deployment](#deploy) the proxy
rejects oversized bodies first and `/tmp` is a size-capped tmpfs. Every dataset
belongs to the account that uploaded it; another account's dataset answers exactly
as a missing one. Datasets themselves are not durable: only accounts are stored on
disk.

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
