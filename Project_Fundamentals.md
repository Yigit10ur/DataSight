# AI Data Insight Engine

## 1. Project Vision

AI Data Insight Engine is an AI-assisted data analysis application.

The main goal is simple:

> A user uploads a CSV or Excel dataset, and the system automatically discovers, analyzes, visualizes, and explains the most important insights in the data.

The product should behave like an intelligent first-pass data analyst rather than a simple visualization dashboard.

A useful product philosophy is:

> **"Upload your dataset and get a data analyst's first 30 minutes of analysis instantly."**

The system should focus on answering:

> **"What should I know about this dataset?"**

rather than simply generating large numbers of charts.

---

## 2. Core Principle

The most important architectural principle of the project is:

> **Python calculates. AI explains.**

The LLM should not be trusted to calculate statistics directly from raw data.

Instead:

```text id="jwf1g3"
Dataset
    ↓
Python Analysis Engine
    ↓
Structured Statistical Results
    ↓
LLM
    ↓
Human-Readable Insights
```

Python and deterministic analytical tools should calculate metrics, statistics, correlations, anomalies, aggregations, and other quantitative results.

The AI layer should interpret those verified results and communicate them clearly to the user.

Whenever deterministic code can solve a problem reliably, it should be preferred over AI.

---

## 3. Core Workflow

The basic application flow should be:

```text id="szkh2n"
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
AI Interpretation
        ↓
Interactive "Ask Your Data"
```

---

## 4. Supported Input

Initial versions should support:

- `.csv`
- `.xlsx`

Possible future formats:

- JSON
- Parquet
- SQL databases
- APIs
- Cloud data warehouses

CSV and Excel should be prioritized for the MVP.

---

## 5. Dataset Profiling

Immediately after upload, the system should generate a dataset overview.

Example:

```text id="l7mg0u"
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

The system should automatically perform EDA depending on column types.

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

The application should detect common data quality problems.

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

```text id="qbdq2r"
⚠ customer_age contains 7.2% missing values.

⚠ 14 rows contain ages above 120 and may represent data-entry errors.

⚠ "Istanbul", "istanbul", and "İstanbul" may represent the same category.
```

---

## 8. Data Quality Score

A future feature should generate an overall dataset quality score.

Example:

```text id="5clkg7"
Data Quality Score: 82 / 100

Completeness:      88
Consistency:       79
Duplicate Score:   95
Outlier Score:     71
Type Consistency:  84
```

The scoring methodology should be deterministic and explainable.

The LLM should explain the score but should NOT calculate it.

---

## 9. Insight Discovery Engine

One of the most important components of the application.

The system should attempt to automatically identify interesting patterns.

Examples:

```text id="hjg0xi"
Revenue increased 18% during Q4.

Enterprise customers generate 2.4x higher average revenue.

Monthly subscribers have significantly higher churn than annual subscribers.

Marketing spend and revenue have a strong positive correlation (r = 0.81).

17 transactions have unusually high values compared with the rest of the dataset.
```

Insights should be ranked by importance.

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

---

## 10. AI Layer

The LLM should primarily be used for:

- Insight explanation
- Natural-language summaries
- Analysis planning
- User interaction
- Data-cleaning explanations
- Translating statistical results into understandable language

The LLM should NOT be the source of truth for quantitative results.

For example, the analysis engine may produce:

```json id="7wktnb"
{
  "relationship": {
    "feature_a": "marketing_spend",
    "feature_b": "revenue",
    "pearson_correlation": 0.81,
    "sample_size": 52340
  }
}
```

The LLM can transform this into:

> Marketing spend and revenue show a strong positive relationship (r = 0.81). However, this relationship should not automatically be interpreted as causal.

### Critical Rule

> **Python calculates. AI explains.**

Every quantitative AI-generated statement should be grounded in results produced by the analysis engine.

---

## 11. Ask Your Data

Users should eventually be able to interact with their dataset through natural language.

Example:

```text id="i8x7rq"
User:
Which products generate the most revenue?
```

The system should:

1. Understand the question.
2. Determine the required analysis.
3. Execute the analysis using the Python data engine.
4. Validate the result.
5. Generate an appropriate visualization when useful.
6. Explain the result using AI.

Example response:

```text id="zix0nq"
Product A generated the highest total revenue.

It accounted for approximately 23.4% of total sales.
```

Follow-up questions should also be supported.

Example:

```text id="0tt8fj"
User:
Compare the top three products by month.
```

The application should understand the conversational context and perform another analysis.

---

## 12. Visualization Recommendation Engine

The application should automatically choose reasonable visualizations.

Basic rules:

```text id="k7vw12"
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

## 13. Data Cleaning Suggestions

The application may recommend cleaning operations.

Examples:

```text id="1r2skj"
customer_age contains 3% missing values.
Median imputation may be appropriate.

CustomerID appears to be an identifier and should probably not be used as a predictive feature.

Three categories may represent different spellings of the same city.
```

Initially, the application should recommend transformations instead of automatically modifying the dataset.

Future versions may allow:

```text id="fl8h8f"
Suggested Action
      ↓
User Approval
      ↓
Apply Transformation
      ↓
Show Before / After
```

Every modification should be reversible.

---

## 14. Anomaly Detection

Future versions can include automatic anomaly detection.

Initial methods:

- IQR
- Z-score

Advanced methods:

- Isolation Forest
- Local Outlier Factor

The system should explain why an observation was flagged instead of simply labeling it as anomalous.

---

## 15. Machine Learning Suggestions

This is NOT required for the first MVP.

Future versions may inspect datasets and identify potential ML tasks.

Example:

```text id="c1j9qx"
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

## 16. Proposed Technical Architecture

### Frontend

```text id="ld1z6v"
React / Next.js
```

Responsibilities:

- File upload
- Dashboard
- Charts
- Insight cards
- Data preview
- Chat interface

### Backend

```text id="l21vnr"
Python
FastAPI
```

Responsibilities:

- File processing
- Analysis requests
- Dataset management
- AI orchestration

### Data Analysis

```text id="hns2jg"
Pandas
NumPy
SciPy
scikit-learn
```

### Visualization

```text id="dtusmy"
Plotly
```

### AI Layer

LLM API used for:

- Insight explanation
- Analysis planning
- Natural-language interaction
- Summaries
- Data-cleaning explanations

---

## 17. Suggested Internal Architecture

Avoid building the entire backend as one large analysis script.

Prefer modular components.

Example:

```text id="gktygk"
backend/

    ingestion/
        csv_loader
        excel_loader
        validator

    profiling/
        schema_detector
        column_profiler
        dataset_profiler

    quality/
        missing_detector
        duplicate_detector
        consistency_checker

    analysis/
        numeric_analysis
        categorical_analysis
        correlation_analysis
        datetime_analysis

    anomaly/
        outlier_detector

    insights/
        insight_generator
        insight_ranker

    visualization/
        chart_selector
        chart_generator

    ai/
        llm_client
        prompt_builder
        insight_explainer
        query_planner

    api/
        routes
```

The exact folder structure can change during development.

The important principle is separation of concerns.

---

## 18. Structured Insight Model

Insights should preferably have a structured internal representation.

Example:

```json id="r93pn7"
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
- Send information to the LLM
- Test the analysis engine
- Prevent hallucinations

---

## 19. MVP Roadmap

### MVP 1 — Core Data Engine

Implement:

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

No complex AI agent is necessary yet.

### MVP 2 — Insight Engine

Add:

- Structured insight generation
- Insight ranking
- LLM explanations
- Data quality summary
- Better visualization recommendations

### MVP 3 — Ask Your Data

Add:

- Natural-language data questions
- Analysis planning
- Dynamic chart generation
- Follow-up questions
- Conversational context

### MVP 4 — Advanced Analytics

Potential features:

- Data-cleaning workflow
- Advanced anomaly detection
- Automatic ML task detection
- Baseline ML models
- Time-series analysis
- Exportable analysis reports

---

## 20. Development Priorities

When implementing features, prioritize in this order:

```text id="jvkku9"
1. Correctness
2. Reproducibility
3. Useful insights
4. Explainability
5. User experience
6. AI capabilities
7. Advanced ML
```

Do not add AI simply because a feature can use AI.

If deterministic Python/statistical logic can solve the problem more reliably, prefer it.

---

## 21. Important Engineering Principles

### Avoid Hallucinated Insights

Every quantitative statement shown to the user should originate from actual computation whenever possible.

Bad architecture:

```text id="lrzpgt"
Raw Dataset
    ↓
LLM
    ↓
Statistical Claims
```

Preferred architecture:

```text id="mb2o6h"
Raw Dataset
    ↓
Python
    ↓
Verified Structured Results
    ↓
LLM
    ↓
Explanation
```

### Separate Analysis From Presentation

Statistical analysis should not depend on the frontend.

### Keep Raw Data Handling Controlled

Do not unnecessarily send entire datasets to an external LLM.

Prefer sending:

- Schema
- Aggregations
- Statistical results
- Selected samples when necessary

### Explain Important Results

The application should help non-experts understand what statistics mean.

### Do Not Confuse Correlation With Causation

The system must clearly distinguish:

- Correlation
- Association
- Prediction
- Causality

---

## 22. Long-Term Product Direction

The project can eventually evolve from:

```text id="m2fb6m"
Automatic EDA Tool
```

into:

```text id="u4z7g5"
AI Data Analyst
```

and potentially:

```text id="9m8upj"
AI Analytics Platform
```

The long-term experience could become:

```text id="t4x5su"
Upload Data
     ↓
"What happened?"
     ↓
"Why did it happen?"
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

## 23. Final Product Goal

The central goal of AI Data Insight Engine is:

> **Turn raw datasets into trustworthy, understandable, and actionable insights with minimal manual effort.**

The application should not try to replace statistical computation with an LLM.

Instead, it should combine the strengths of deterministic data analysis and modern language models:

> **Python calculates. AI explains.**