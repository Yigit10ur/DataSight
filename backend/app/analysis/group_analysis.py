import math

import numpy as np
import pandas as pd
from scipy import stats

from app.analysis.models import GroupComparison, GroupStats
from app.analysis.numbers import numeric_values

MIN_GROUP_SIZE = 5
MAX_GROUP_COUNT = 10
IQR_WHISKER_FACTOR = 1.5

MAX_GROUP_COLUMNS = 3
MAX_VALUE_COLUMNS = 5
MAX_COMPARISONS = 15


def _describe_group(name: str, values: pd.Series) -> GroupStats:
    q1, median, q3 = values.quantile([0.25, 0.5, 0.75])
    iqr = q3 - q1
    within = values[
        (values >= q1 - IQR_WHISKER_FACTOR * iqr) & (values <= q3 + IQR_WHISKER_FACTOR * iqr)
    ]
    # An all-outlier group cannot happen with a real IQR, but a degenerate one can.
    whiskers = within if not within.empty else values

    return GroupStats(
        name=name,
        count=len(values),
        mean=float(values.mean()),
        median=float(median),
        std=float(values.std()) if len(values) > 1 else 0.0,
        minimum=float(values.min()),
        maximum=float(values.max()),
        q1=float(q1),
        q3=float(q3),
        lower_whisker=float(whiskers.min()),
        upper_whisker=float(whiskers.max()),
    )


def _kruskal_effect(samples: list[np.ndarray]) -> tuple[float | None, float | None]:
    """Epsilon-squared and p-value from a Kruskal-Wallis test.

    Rank-based rather than ANOVA because group sizes are usually uneven and the
    numeric columns in an uploaded file are rarely normally distributed.
    """
    group_count = len(samples)
    total = sum(len(sample) for sample in samples)
    if total <= group_count:
        return None, None

    try:
        statistic, p_value = stats.kruskal(*samples)
    except ValueError:
        # Raised when every value across every group is identical.
        return None, None
    if not math.isfinite(statistic):
        return None, None

    epsilon_squared = (statistic - group_count + 1) / (total - group_count)
    return min(max(epsilon_squared, 0.0), 1.0), float(p_value)


def analyze_groups(
    frame: pd.DataFrame, group_column: str, value_column: str
) -> GroupComparison | None:
    """Compare one numeric column across the groups of one categorical column."""
    values = numeric_values(frame[value_column])
    paired = pd.DataFrame(
        {"group": frame[group_column].where(frame[group_column].notna()), "value": values}
    ).dropna()

    described: list[GroupStats] = []
    samples: list[np.ndarray] = []
    ignored = 0

    for name, group in paired.groupby(paired["group"].astype(str))["value"]:
        # A handful of rows describes its group too poorly to compare against others,
        # and a single stray label would otherwise become the "highest" group.
        if len(group) < MIN_GROUP_SIZE:
            ignored += 1
            continue
        described.append(_describe_group(str(name), group))
        samples.append(group.to_numpy(dtype=float))

    if len(described) < 2:
        return None

    described.sort(key=lambda group: group.mean, reverse=True)
    highest, lowest = described[0], described[-1]
    effect_size, p_value = _kruskal_effect(samples)

    return GroupComparison(
        group_column=group_column,
        value_column=value_column,
        groups=described,
        sample_size=sum(group.count for group in described),
        ignored_group_count=ignored,
        highest_group=highest.name,
        lowest_group=lowest.name,
        # "2.4x higher" only means something when the baseline is positive.
        mean_ratio=highest.mean / lowest.mean if lowest.mean > 0 else None,
        median_difference=highest.median - lowest.median,
        effect_size=effect_size,
        p_value=p_value,
    )


def compare_groups(
    frame: pd.DataFrame, group_columns: list[str], value_columns: list[str]
) -> list[GroupComparison]:
    """Compare every eligible categorical/numeric pair, biggest difference first."""
    comparisons = [
        comparison
        for group_column in group_columns[:MAX_GROUP_COLUMNS]
        for value_column in value_columns[:MAX_VALUE_COLUMNS]
        if (comparison := analyze_groups(frame, group_column, value_column)) is not None
    ]

    comparisons.sort(key=lambda comparison: comparison.effect_size or 0.0, reverse=True)
    return comparisons[:MAX_COMPARISONS]
