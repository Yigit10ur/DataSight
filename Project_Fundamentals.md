# DataSight

## 1. Project Vision

DataSight is a data analysis application.

The main goal is simple:

> A user uploads a CSV or Excel dataset, and the system automatically discovers, analyzes, and visualizes the most important insights in the data, then lets the user shape it further without writing code.

The product should behave like an intelligent first-pass data analyst rather than a simple visualization dashboard.

A useful product philosophy is:

> **"Upload your dataset and get a data analyst's first 30 minutes of analysis instantly."**

The system should focus on answering:

> **"What should I know about this dataset?"**

rather than simply generating large numbers of charts.

---

## 2. Core Principle

The most important architectural principle of the project is:

> **Python calculates.**

Every number, score, finding, and chart shown to the user is computed by deterministic Python code. There is no language model in the product and no API key is needed.

```text
Dataset
    ↓
Python Analysis Engine
    ↓
Structured Statistical Results
    ↓
Ranked Findings and Messages
    ↓
Dashboard
```

Python and deterministic analytical tools calculate metrics, statistics, correlations, outliers, aggregations, and other quantitative results. Findings are written from those results by templates, so every figure in a sentence is a figure the engine produced.

Earlier versions added an optional LLM layer that wrote explanations and planned natural-language questions (see [MVP 2](MVP-2.md) and [MVP 3](MVP-3-plan.md)). It was removed: every result is now computed and phrased in Python.

---

## 3. Core Workflow

The application flow is:

```text
CSV / Excel Upload
        ↓
Dataset Validation
        ↓
Schema & Data Profiling
        ↓
Data Quality Analysis
        ↓
Exploratory Data Analysis
        ↓
Statistical Analysis
        ↓
Insight Discovery
        ↓
Visualization
        ↓
Shape the Data (no-code recipes)
        ↓
Export or Save as a Derived Dataset
```

---

## 4. Supported Input

Supported formats:

- `.csv`
- `.xlsx` (first worksheet)

Possible future formats:

- JSON
- Parquet
- SQL databases
- APIs
- Cloud data warehouses

---

## 5. Dataset Profiling

Immediately after upload, the system generates a dataset overview.

Example:

```text
Dataset: sales.csv

Rows: 52,340
Columns: 17
Numeric Columns: 8
Categorical Columns: 6
Datetime Columns: 2
Possible ID Columns: 1
Missing Cells: 3.4%
Duplicate Rows: 127
```

The profiling engine should automatically detect:

- Numeric columns
- Categorical columns
- Boolean columns
- Datetime columns
- Text columns
- Possible ID columns
- Constant columns
- High-cardinality columns
- Missing values
- Duplicate rows
- Unique value counts

---

## 6. Automatic Exploratory Data Analysis

The system automatically performs EDA depending on column types.

### Numeric Features

Analyze:

- Mean
- Median
- Standard deviation
- Min / max
- Quantiles
- Distribution
- Skewness
- Missing values
- Potential outliers

Possible visualizations:

- Histogram
- Box plot
- KDE/distribution plot

### Categorical Features

Analyze:

- Unique categories
- Frequency
- Most common category
- Rare categories
- Missing categories
- Cardinality

Possible visualization:

- Bar chart

### Numeric vs Numeric

Analyze:

- Pearson correlation
- Spearman correlation
- Possible strong relationships

Possible visualizations:

- Scatter plot
- Correlation heatmap

### Categorical vs Numeric

Analyze differences between groups.

Possible visualizations:

- Box plot
- Bar chart
- Group statistics

### Datetime Features

If datetime columns exist, analyze:

- Trends
- Growth/decline
- Seasonality
- Sudden changes
- Period comparisons

Possible visualization:

- Line chart

---

## 7. Data Quality Engine

The application detects common data quality problems.

Examples:

- Missing values
- Duplicate rows
- Extreme outliers
- Invalid values
- Suspicious categories
- Inconsistent formatting
- Constant columns
- Extremely high-cardinality columns
- Potential identifier columns
- Incorrect inferred data types

Example insights:

```text
⚠ customer_age contains 7.2% missing values.

⚠ 14 rows contain ages above 120 and may represent data-entry errors.

⚠ "Istanbul", "istanbul", and "İstanbul" may represent the same category.
```

---

## 8. Data Quality Score

The application generates an overall dataset quality score.

Example:

```text
Data Quality Score: 82 / 100

Completeness:      88
Consistency:       79
Duplicate Score:   95
Outlier Score:     71
Type Consistency:  84
```

The scoring methodology is deterministic and explainable: each dimension lists the columns that cost it points and the issues behind them.

---

## 9. Insight Discovery Engine

One of the most important components of the application.

The system attempts to automatically identify interesting patterns.

Examples:

```text
Revenue increased 18% during Q4.

Enterprise customers generate 2.4x higher average revenue.

Monthly subscribers have significantly higher churn than annual subscribers.

Marketing spend and revenue have a strong positive correlation (r = 0.81).

17 transactions have unusually high values compared with the rest of the dataset.
```

Insights are ranked by importance.

Possible categories:

- Strong correlations
- Large group differences
- Trends
- Anomalies
- Outliers
- Missing-data problems
- Distribution changes
- Dominant categories
- Rare categories
- Time-series patterns

Each finding carries caveats where the statistics call for them. A correlation, for example, is reported as an association and never as a cause.

---

## 10. Visualization Recommendation Engine

The application automatically chooses reasonable visualizations.

Basic rules:

```text
Numeric
→ Histogram / Box Plot

Categorical
→ Bar Chart

Numeric + Numeric
→ Scatter Plot

Categorical + Numeric
→ Box Plot / Grouped Bar Chart

Datetime + Numeric
→ Line Chart

Many Numeric Columns
→ Correlation Heatmap
```

The visualization system should prioritize useful charts rather than generating every possible visualization.

---

## 11. Shaping Data: No-Code Recipes

Users shape a dataset by building a **recipe**: an ordered list of typed steps, each validated against the schema it will meet before anything runs.

Available steps include filtering and sorting rows, selecting and renaming columns, changing types, filling missing values, removing duplicates, deriving columns, and aggregating groups. A recipe can end in a focused analysis of the shaped data.

```text
Build a Step
      ↓
Validate Against the Schema
      ↓
Preview the Result
      ↓
Download CSV or Save as a Derived Dataset
```

The uploaded data is never modified. A recipe is stored rather than its output, every step can be removed, and a derived dataset keeps its lineage back to the upload.

Future versions may suggest steps from quality findings:

```text
customer_age contains 3% missing values.
Median imputation may be appropriate.

Three categories may represent different spellings of the same city.
```

A suggestion should become an ordinary recipe step that the user approves and can remove.

---

## 12. Anomaly Detection

Future versions can include dedicated anomaly detection beyond the current IQR-based outlier checks.

Initial methods:

- IQR
- Z-score

Advanced methods:

- Isolation Forest
- Local Outlier Factor

The system should explain why an observation was flagged instead of simply labeling it as anomalous.

---

## 13. Machine Learning Suggestions

This is not part of the current application.

Future versions may inspect datasets and identify potential ML tasks.

Example:

```text
Potential ML Task

Problem:
Binary Classification

Potential Target:
Churn

Suggested Baselines:
- Logistic Regression
- Random Forest
- Gradient Boosting
```

Potential supported tasks:

- Classification
- Regression
- Clustering
- Time-series forecasting

Eventually, the system may train baseline models automatically.

However:

> **Data understanding and insight discovery have higher priority than AutoML.**

---

## 14. Technical Architecture

### Frontend

```text
Next.js / React / TypeScript
Tailwind CSS
Plotly
```

Responsibilities:

- File upload
- Dashboard
- Charts
- Insight cards
- Data preview
- Recipe builder and previews

### Backend

```text
Python
FastAPI
```

Responsibilities:

- File processing
- Analysis requests
- Dataset management and lineage
- Recipe validation and execution

### Data Analysis

```text
Pandas
NumPy
SciPy
```

scikit-learn is listed in the backend requirements for future ML work but is not used yet.

---

## 15. Internal Architecture

The backend is built from modular components rather than one large analysis script:

```text
backend/app/
    ingestion/       csv_loader, excel_loader, validator
    profiling/       schema_detector, dataset_profiler, preview
    quality/         missing, duplicate, consistency, and structure detectors; score
    analysis/        numeric, categorical, correlation, group, and datetime analysis
    insights/        insight_generator, insight_ranker, formatting
    visualization/   chart_selector, chart_generator
    recipes/         schema, validator, executor, provenance
    api/             routes
    dashboard.py     shared, bounded dashboard computation cache
    store.py         in-memory datasets and lineage
```

The folder structure can change during development. The important principle is separation of concerns.

---

## 16. Structured Insight Model

Insights have a structured internal representation.

Example:

```json
{
  "type": "correlation",
  "importance": 0.86,
  "columns": [
    "marketing_spend",
    "revenue"
  ],
  "metrics": {
    "pearson": 0.81
  },
  "message": "Strong positive relationship detected."
}
```

This makes it easier to:

- Rank insights
- Filter insights
- Generate UI cards
- Attach caveats and charts
- Test the analysis engine

---

## 17. MVP Roadmap

### MVP 1 — Core Data Engine (done)

- CSV upload
- Excel upload
- Data preview
- Schema detection
- Basic dataset statistics
- Missing-value analysis
- Duplicate detection
- Numeric distributions
- Categorical distributions
- Correlation analysis
- Basic outlier detection
- Automatic charts

### MVP 2 — Insight Engine (done)

- Structured insight generation
- Insight ranking
- Data quality score
- Better visualization recommendations

MVP 2 also shipped optional LLM explanations. They have since been removed.

### MVP 2.5 — Shape Your Data (done)

- No-code recipes
- Recipe previews
- Derived datasets with lineage
- CSV export

### MVP 3 — Ask Your Data (removed)

Natural-language questions, analysis planning, and conversational follow-ups were built on top of the recipe engine, then removed along with every other model-dependent feature.

### Next — Advanced Analytics

Potential features:

- Cleaning suggestions that become recipe steps
- Advanced anomaly detection
- Automatic ML task detection
- Baseline ML models
- Time-series analysis
- Exportable analysis reports

---

## 18. Development Priorities

When implementing features, prioritize in this order:

```text
1. Correctness
2. Reproducibility
3. Useful insights
4. Explainability
5. User experience
6. Advanced ML
```

If deterministic Python or statistical logic can solve a problem reliably, prefer it.

---

## 19. Important Engineering Principles

### Every Number Comes From Computation

Every quantitative statement shown to the user originates from actual computation. Messages are built from computed results, never written independently of them.

### Separate Analysis From Presentation

Statistical analysis should not depend on the frontend.

### Keep Raw Data Handling Controlled

Datasets stay in the backend process. They are not sent to external services, and they expire after a fixed lifetime.

### Explain Important Results

The application should help non-experts understand what statistics mean.

### Do Not Confuse Correlation With Causation

The system must clearly distinguish:

- Correlation
- Association
- Prediction
- Causality

---

## 20. Long-Term Product Direction

The project can eventually evolve from:

```text
Automatic EDA Tool
```

into:

```text
No-Code Analytics Workbench
```

The long-term experience could become:

```text
Upload Data
     ↓
"What happened?"
     ↓
"What should I investigate?"
     ↓
"Can you visualize it?"
     ↓
"Can you clean the problem?"
     ↓
"Can you build a predictive model?"
```

---

## 21. Final Product Goal

The central goal of DataSight is:

> **Turn raw datasets into trustworthy, understandable, and actionable insights with minimal manual effort.**

Statistical computation stays deterministic, reproducible, and testable:

> **Python calculates.**
