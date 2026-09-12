import math

import numpy as np
import pandas as pd

from app.analysis.models import Seasonality, Timeline, TimelineChange, TimelinePoint
from app.analysis.numbers import numeric_values

MAX_TIMELINE_POINTS = 400
MIN_TIMELINE_POINTS = 3
FLAT_CHANGE_RATIO = 0.05
MAX_TIMELINES = 5

RULES = ["D", "W", "MS"]
AGGREGATION_LABELS = {"D": "daily mean", "W": "weekly mean", "MS": "monthly mean"}
CYCLE_LABELS = {"D": "day of week", "W": "month of year", "MS": "month of year"}
# Two full cycles, so a "strongest month" rests on at least two observations of it.
SEASONAL_MINIMUM_POINTS = {"D": 14, "W": 104, "MS": 24}


def _resample_rule(span_days: int, gap_days: float) -> str:
    """Pick a period that keeps the series readable without inventing gaps.

    The span decides how few points the chart can afford; the spacing of the rows
    decides how fine a period is honest. Monthly rows bucketed by week would be
    three empty periods for every real one, so the coarser of the two wins.
    """
    if span_days <= MAX_TIMELINE_POINTS:
        by_span = "D"
    else:
        by_span = "W" if span_days <= MAX_TIMELINE_POINTS * 7 else "MS"
    by_spacing = "D" if gap_days <= 1 else "W" if gap_days <= 7 else "MS"
    return max(by_span, by_spacing, key=RULES.index)


def _typical_gap_days(timestamps: pd.Series) -> float:
    """The median distance between two consecutive readings."""
    moments = timestamps.drop_duplicates().sort_values()
    if len(moments) < 2:
        return 0.0
    return float(moments.diff().dropna().median().total_seconds() / 86400)


def _monotonicity(values: pd.Series) -> float | None:
    """Rank correlation between position and value: how steady the trend is.

    A series that doubles in one jump and a series that climbs every period have
    the same total change; only this separates them.
    """
    if len(values) < MIN_TIMELINE_POINTS or values.std() == 0:
        return None
    positions = pd.Series(range(len(values)))
    correlation = values.reset_index(drop=True).corr(positions, method="spearman")
    return float(correlation) if math.isfinite(correlation) else None


def _largest_change(values: pd.Series) -> TimelineChange | None:
    if len(values) < 2:
        return None

    deltas = values.diff().dropna()
    if deltas.empty:
        return None

    position = int(np.argmax(deltas.abs().to_numpy()))
    period = deltas.index[position]
    previous_position = values.index.get_loc(period) - 1
    previous_period = values.index[previous_position]
    previous_value = float(values.iloc[previous_position])
    delta = float(deltas.iloc[position])

    return TimelineChange(
        period=period.date().isoformat(),
        previous_period=previous_period.date().isoformat(),
        delta=delta,
        ratio=delta / abs(previous_value) if previous_value != 0 else None,
    )


def _seasonality(values: pd.Series, rule: str) -> Seasonality | None:
    """How much of the variation is explained by the position in the calendar cycle."""
    if len(values) < SEASONAL_MINIMUM_POINTS[rule]:
        return None

    keys = values.index.day_name() if rule == "D" else values.index.month_name()
    grouped = values.groupby(keys)
    if grouped.ngroups < 2:
        return None

    overall = values.mean()
    between = sum(len(group) * (group.mean() - overall) ** 2 for _, group in grouped)
    total = float(((values - overall) ** 2).sum())
    if total == 0 or not math.isfinite(total):
        return None

    cycle_means = grouped.mean()
    return Seasonality(
        cycle=CYCLE_LABELS[rule],
        strongest=str(cycle_means.idxmax()),
        weakest=str(cycle_means.idxmin()),
        strength=min(max(between / total, 0.0), 1.0),
    )


def analyze_timeline(
    frame: pd.DataFrame, time_column: str, value_column: str
) -> Timeline | None:
    """Describe how a numeric column moves over time."""
    timestamps = pd.to_datetime(frame[time_column], errors="coerce", format="mixed")
    values = numeric_values(frame[value_column])
    series = pd.DataFrame({"t": timestamps, "v": values}).dropna(subset=["t"])
    if series["v"].count() < MIN_TIMELINE_POINTS:
        return None

    span_days = (series["t"].max() - series["t"].min()).days
    rule = _resample_rule(span_days, _typical_gap_days(series["t"]))
    grouped = series.set_index("t").resample(rule)["v"].mean()

    # Periods with no rows stay in the chart as gaps, but they are not observations.
    observed = grouped.dropna()
    if len(observed) < MIN_TIMELINE_POINTS:
        return None

    # Comparing the first and last quarter of the timeline instead of the first and
    # last point, so one unusual period cannot decide the direction of the trend.
    window = max(1, len(observed) // 4)
    first_window_mean = float(observed.iloc[:window].mean())
    last_window_mean = float(observed.iloc[-window:].mean())
    change_ratio = (
        (last_window_mean - first_window_mean) / abs(first_window_mean)
        if first_window_mean != 0
        else None
    )

    slope = float(np.polyfit(range(len(observed)), observed.to_numpy(dtype=float), 1)[0])
    if change_ratio is None:
        trend = "rising" if slope > 0 else "falling" if slope < 0 else "flat"
    elif abs(change_ratio) < FLAT_CHANGE_RATIO:
        trend = "flat"
    else:
        trend = "rising" if change_ratio > 0 else "falling"

    return Timeline(
        time_column=time_column,
        value_column=value_column,
        aggregation=AGGREGATION_LABELS[rule],
        points=[
            TimelinePoint(
                period=period.date().isoformat(),
                value=None if pd.isna(value) else float(value),
            )
            for period, value in grouped.items()
        ],
        start=observed.index[0].date().isoformat(),
        end=observed.index[-1].date().isoformat(),
        sample_size=int(series["v"].count()),
        window_periods=window,
        first_window_mean=first_window_mean,
        last_window_mean=last_window_mean,
        change_ratio=change_ratio,
        trend=trend,
        slope_per_period=slope,
        monotonicity=_monotonicity(observed),
        largest_change=_largest_change(observed),
        seasonality=_seasonality(observed, rule),
    )


def build_timelines(
    frame: pd.DataFrame, time_columns: list[str], value_columns: list[str]
) -> list[Timeline]:
    """Track the numeric columns against the first datetime column, largest move first.

    Only the first datetime column: a file with created_at and updated_at would
    otherwise produce two near-identical timelines per numeric column.
    """
    if not time_columns:
        return []

    timelines = [
        timeline
        for value_column in value_columns[:MAX_TIMELINES]
        if (timeline := analyze_timeline(frame, time_columns[0], value_column)) is not None
    ]

    timelines.sort(key=lambda timeline: abs(timeline.change_ratio or 0.0), reverse=True)
    return timelines
