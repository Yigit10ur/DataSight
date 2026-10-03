from collections import OrderedDict
from dataclasses import dataclass, field
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


@dataclass(eq=False)
class _Slot:
    """The lock that lets one request compute a dataset's dashboard while others
    wait, and how many requests are holding or waiting on it."""

    lock: Lock = field(default_factory=Lock)
    users: int = 0


class DashboardCache:
    """A bounded, concurrent LRU of computed dashboard results.

    Stored datasets never change in place, so their ID is a complete cache key.
    The frame is used during computation but is deliberately absent from the result.
    """

    def __init__(self) -> None:
        self._entries: OrderedDict[str, DashboardAnalysis] = OrderedDict()
        # A slot is kept while a request uses it or its result is cached, so a
        # computation that fails or is discarded leaves nothing behind.
        self._locks: dict[str, _Slot] = {}
        self._guard = RLock()

    def get_or_compute(
        self,
        dataset_id: str,
        frame: pd.DataFrame,
        profile: DatasetProfile,
        provenance: Provenance,
        retain: Callable[[], bool],
    ) -> DashboardAnalysis:
        slot = self._enter(dataset_id)
        try:
            with slot.lock:
                return self._cached_or_computed(
                    dataset_id, frame, profile, provenance, retain, slot
                )
        finally:
            self._leave(dataset_id, slot)

    def _cached_or_computed(
        self,
        dataset_id: str,
        frame: pd.DataFrame,
        profile: DatasetProfile,
        provenance: Provenance,
        retain: Callable[[], bool],
        slot: _Slot,
    ) -> DashboardAnalysis:
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
                if self._locks.get(dataset_id) is slot:
                    self._entries[dataset_id] = computed
                    self._entries.move_to_end(dataset_id)
                    while len(self._entries) > settings.dashboard_cache_size:
                        evicted, _ = self._entries.popitem(last=False)
                        # A slot still in use is dropped when its last user leaves.
                        evicted_slot = self._locks.get(evicted)
                        if evicted_slot is not None and evicted_slot.users == 0:
                            del self._locks[evicted]
        return computed

    def remove(self, dataset_id: str) -> None:
        with self._guard:
            self._entries.pop(dataset_id, None)
            self._locks.pop(dataset_id, None)

    def clear(self) -> None:
        with self._guard:
            self._entries.clear()
            self._locks.clear()

    def _enter(self, dataset_id: str) -> _Slot:
        with self._guard:
            slot = self._locks.setdefault(dataset_id, _Slot())
            slot.users += 1
            return slot

    def _leave(self, dataset_id: str, slot: _Slot) -> None:
        with self._guard:
            slot.users -= 1
            # remove() may already have dropped it, and a new slot taken its place.
            if (
                slot.users == 0
                and dataset_id not in self._entries
                and self._locks.get(dataset_id) is slot
            ):
                del self._locks[dataset_id]


dashboard_cache = DashboardCache()


def clear_dashboard_cache(dataset_id: str) -> None:
    dashboard_cache.remove(dataset_id)
