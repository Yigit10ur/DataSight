import math
from itertools import combinations

import pandas as pd

from app.analysis.models import CorrelationPair

MIN_SAMPLE_SIZE = 3
MAX_PAIRS = 50


def analyze_correlations(frame: pd.DataFrame, columns: list[str]) -> list[CorrelationPair]:
    """Correlate every numeric column pair, strongest relationship first."""
    pairs: list[CorrelationPair] = []

    for column_a, column_b in combinations(columns, 2):
        both = frame[[column_a, column_b]].apply(pd.to_numeric, errors="coerce").dropna()
        if len(both) < MIN_SAMPLE_SIZE:
            continue
        # A column with no variance correlates with nothing, and dividing by its
        # zero standard deviation would only produce a warning and a NaN.
        if both[column_a].std() == 0 or both[column_b].std() == 0:
            continue

        pearson = both[column_a].corr(both[column_b], method="pearson")
        if not math.isfinite(pearson):
            continue
        spearman = both[column_a].corr(both[column_b], method="spearman")

        pairs.append(
            CorrelationPair(
                column_a=column_a,
                column_b=column_b,
                pearson=float(pearson),
                spearman=float(spearman) if math.isfinite(spearman) else None,
                sample_size=len(both),
            )
        )

    pairs.sort(key=lambda pair: abs(pair.pearson), reverse=True)
    return pairs[:MAX_PAIRS]
