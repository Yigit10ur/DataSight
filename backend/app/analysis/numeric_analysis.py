import math

import numpy as np
import pandas as pd

from app.analysis.models import Histogram, NumericSummary
from app.analysis.numbers import numeric_values

MAX_HISTOGRAM_BINS = 30
IQR_OUTLIER_FACTOR = 1.5


def _finite(value: float | None) -> float | None:
    """Convert numpy/pandas results into JSON-safe floats."""
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def count_iqr_outliers(values: pd.Series) -> int:
    """Count values outside the Tukey fences, the standard first-pass outlier rule."""
    q1, q3 = values.quantile(0.25), values.quantile(0.75)
    iqr = q3 - q1
    if not math.isfinite(iqr) or iqr == 0:
        return 0
    lower = q1 - IQR_OUTLIER_FACTOR * iqr
    upper = q3 + IQR_OUTLIER_FACTOR * iqr
    return int(((values < lower) | (values > upper)).sum())


def build_histogram(values: pd.Series) -> Histogram:
    if values.empty:
        return Histogram(bin_edges=[], counts=[])

    bins = min(MAX_HISTOGRAM_BINS, max(int(values.nunique()), 1))
    counts, edges = np.histogram(values.to_numpy(dtype=float), bins=bins)
    return Histogram(bin_edges=[float(edge) for edge in edges], counts=[int(count) for count in counts])


def analyze_numeric(series: pd.Series) -> NumericSummary:
    """Describe the distribution of a numeric column."""
    values = numeric_values(series).dropna()
    outlier_count = count_iqr_outliers(values) if not values.empty else 0

    return NumericSummary(
        column=str(series.name),
        count=int(values.count()),
        missing_count=int(series.isna().sum()),
        mean=_finite(values.mean()) if not values.empty else None,
        median=_finite(values.median()) if not values.empty else None,
        std=_finite(values.std()) if len(values) > 1 else None,
        minimum=_finite(values.min()) if not values.empty else None,
        maximum=_finite(values.max()) if not values.empty else None,
        q1=_finite(values.quantile(0.25)) if not values.empty else None,
        q3=_finite(values.quantile(0.75)) if not values.empty else None,
        skewness=_finite(values.skew()) if len(values) > 2 else None,
        outlier_count=outlier_count,
        outlier_ratio=outlier_count / len(values) if len(values) else 0.0,
        histogram=build_histogram(values),
    )
