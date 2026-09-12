import uuid
from dataclasses import dataclass

import pandas as pd

from app.profiling.models import DatasetProfile


@dataclass(frozen=True)
class StoredDataset:
    dataset_id: str
    filename: str
    frame: pd.DataFrame
    profile: DatasetProfile


class DatasetStore:
    """Keeps uploaded datasets in memory so later analyses can reuse them by id."""

    def __init__(self) -> None:
        self._datasets: dict[str, StoredDataset] = {}

    def new_id(self) -> str:
        return uuid.uuid4().hex

    def add(self, dataset_id: str, filename: str, frame: pd.DataFrame, profile: DatasetProfile) -> StoredDataset:
        stored = StoredDataset(dataset_id=dataset_id, filename=filename, frame=frame, profile=profile)
        self._datasets[dataset_id] = stored
        return stored

    def get(self, dataset_id: str) -> StoredDataset | None:
        return self._datasets.get(dataset_id)


dataset_store = DatasetStore()
