import pandas as pd

from app.analysis.models import CategoricalSummary, CategoryCount

TOP_CATEGORY_COUNT = 10
RARE_CATEGORY_RATIO = 0.01


def analyze_categorical(series: pd.Series) -> CategoricalSummary:
    """Describe the frequency distribution of a categorical column."""
    values = series.dropna()
    counts = values.value_counts()
    total = int(values.count())

    top = [
        CategoryCount(value=str(value), count=int(count), ratio=count / total)
        for value, count in counts.head(TOP_CATEGORY_COUNT).items()
    ]
    rare_count = int((counts / total < RARE_CATEGORY_RATIO).sum()) if total else 0

    return CategoricalSummary(
        column=str(series.name),
        count=total,
        missing_count=int(series.isna().sum()),
        unique_count=int(counts.size),
        top_categories=top,
        rare_category_count=rare_count,
    )
