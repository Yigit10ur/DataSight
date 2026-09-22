from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock, RLock
from typing import Callable

import pandas as pd

from app.analysis import DatasetAnalysis, analyze_dataset
from app.config import settings
from app.insights import InsightCollection, build_insights
from app.profiling import DatasetProfile
from app.provenance import Provenance
from app.quality import QualityReport, check_dataset_quality
from app.visualization import ChartCollection, build_charts


@dataclass(frozen=True)
class DashboardAnalysis:
    """Every deterministic result shown for one immutable stored dataset."""

    analysis: DatasetAnalysis
    quality: QualityReport
    charts: ChartCollection
    insights: InsightCollection


class DashboardCache:
    """A bounded, concurrent LRU of computed dashboard results.

    Stored datasets never change in place, so their ID is a complete cache key.
    The frame is used during computation but is deliberately absent from the result.
    """

    def __init__(self) -> None:
        self._entries: OrderedDict[str, DashboardAnalysis] = OrderedDict()
        self._locks: dict[str, Lock] = {}
        self._guard = RLock()

    def get_or_compute(
        self,
        dataset_id: str,
        frame: pd.DataFrame,
        profile: DatasetProfile,
        provenance: Provenance,
        retain: Callable[[], bool],
    ) -> DashboardAnalysis:
        lock = self._lock_for(dataset_id)
        with lock:
            with self._guard:
                cached = self._entries.get(dataset_id)
                if cached is not None:
                    self._entries.move_to_end(dataset_id)
                    return cached

            analysis = analyze_dataset(frame, profile)
            quality = check_dataset_quality(frame, profile, provenance)
            charts = build_charts(frame, profile, analysis)
            insights = build_insights(
                profile, analysis, quality, charts.charts, provenance
            )
            computed = DashboardAnalysis(
                analysis=analysis,
                quality=quality,
                charts=charts,
                insights=insights,
            )

            # Expiration can happen while calculation is in progress. The caller
            # may discard this result, and the cache must not resurrect it.
            if retain():
                with self._guard:
                    if self._locks.get(dataset_id) is lock:
                        self._entries[dataset_id] = computed
                        self._entries.move_to_end(dataset_id)
                        while len(self._entries) > settings.dashboard_cache_size:
                            evicted, _ = self._entries.popitem(last=False)
                            self._locks.pop(evicted, None)
            return computed

    def remove(self, dataset_id: str) -> None:
        with self._guard:
            self._entries.pop(dataset_id, None)
            self._locks.pop(dataset_id, None)

    def clear(self) -> None:
        with self._guard:
            self._entries.clear()
            self._locks.clear()

    def _lock_for(self, dataset_id: str) -> Lock:
        with self._guard:
            return self._locks.setdefault(dataset_id, Lock())


dashboard_cache = DashboardCache()


def clear_dashboard_cache(dataset_id: str) -> None:
    dashboard_cache.remove(dataset_id)
