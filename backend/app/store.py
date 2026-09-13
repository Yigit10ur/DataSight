import uuid
from collections import OrderedDict
from dataclasses import dataclass

import pandas as pd
from pydantic import BaseModel

from app.profiling.models import DatasetProfile
from app.provenance import Provenance
from app.recipes import Recipe, planned_columns, provenance_of, run_recipe

# How many derived frames are held in memory at once. Derived data is kept as its
# recipe, so a frame that falls out of here is rebuilt on the next request rather
# than lost: the cache is speed, never correctness.
DERIVED_CACHE_SIZE = 4

# Each link in a chain is a full re-run of everything above it, and nothing a reader
# builds by hand comes near this.
MAX_LINEAGE_DEPTH = 10

# One dataset can only be shaped so many ways before the store is holding recipes
# nobody will open again.
MAX_DERIVED_PER_PARENT = 20


class DatasetLimit(Exception):
    """Raised when a dataset cannot be derived because a cap is in the way."""


def steps_phrase(count: int) -> str:
    """How far a dataset has come from its file, in words. One place, two readers."""
    return f"{count} step" if count == 1 else f"{count} steps"


@dataclass(frozen=True)
class StoredDataset:
    dataset_id: str
    filename: str
    profile: DatasetProfile
    # An uploaded dataset is its own root and its frame is held. A derived one holds
    # the recipe that makes it, and is rebuilt from its parent when asked for.
    parent_id: str | None = None
    recipe: Recipe | None = None

    @property
    def is_derived(self) -> bool:
        return self.parent_id is not None


class LineageEntry(BaseModel):
    dataset_id: str
    filename: str
    rows: int
    columns: int
    # How this dataset was made from the one before it. Absent on the uploaded file,
    # which was not made from anything.
    recipe: Recipe | None


class Lineage(BaseModel):
    dataset_id: str
    # The uploaded file first, this dataset last.
    chain: list[LineageEntry]


class DatasetStore:
    """Keeps uploaded datasets in memory so later analyses can reuse them by id.

    A derived dataset is kept as its parent's id and the recipe between them, not as
    a second copy of the data. Recipes are deterministic and an uploaded frame is
    never modified, so rebuilding one always gives what it gave the first time — that
    is what lets a reader try a dozen shapes without a dozen copies of their file.
    """

    def __init__(self) -> None:
        self._datasets: dict[str, StoredDataset] = {}
        self._uploaded: dict[str, pd.DataFrame] = {}
        self._derived: OrderedDict[str, pd.DataFrame] = OrderedDict()

    def new_id(self) -> str:
        return uuid.uuid4().hex

    def add(
        self, dataset_id: str, filename: str, frame: pd.DataFrame, profile: DatasetProfile
    ) -> StoredDataset:
        stored = StoredDataset(dataset_id=dataset_id, filename=filename, profile=profile)
        self._datasets[dataset_id] = stored
        self._uploaded[dataset_id] = frame
        return stored

    def add_derived(
        self,
        dataset_id: str,
        parent: StoredDataset,
        recipe: Recipe,
        frame: pd.DataFrame,
        profile: DatasetProfile,
    ) -> StoredDataset:
        """Register the result of a recipe as a dataset in its own right."""
        if len(self.lineage(parent)) >= MAX_LINEAGE_DEPTH:
            raise DatasetLimit(
                f"This dataset is already {MAX_LINEAGE_DEPTH} steps from the file it came "
                "from. Save the result and start again from it."
            )
        if self._child_count(parent.dataset_id) >= MAX_DERIVED_PER_PARENT:
            raise DatasetLimit(
                f"There are already {MAX_DERIVED_PER_PARENT} datasets shaped from this one."
            )

        stored = StoredDataset(
            dataset_id=dataset_id,
            filename=profile.filename,
            profile=profile,
            parent_id=parent.dataset_id,
            recipe=recipe,
        )
        self._datasets[dataset_id] = stored
        # The frame was just computed to build the profile; keeping it spares the
        # reader a rebuild on the request that always follows.
        self._remember(dataset_id, frame)
        return stored

    def get(self, dataset_id: str) -> StoredDataset | None:
        return self._datasets.get(dataset_id)

    def frame_of(self, stored: StoredDataset) -> pd.DataFrame:
        """The data itself, rebuilt from its recipe if it is not being held."""
        if not stored.is_derived:
            return self._uploaded[stored.dataset_id]

        cached = self._derived.get(stored.dataset_id)
        if cached is not None:
            self._derived.move_to_end(stored.dataset_id)
            return cached

        frame = self._rebuild(stored)
        self._remember(stored.dataset_id, frame)
        return frame

    def lineage(self, stored: StoredDataset) -> list[StoredDataset]:
        """Every dataset between the uploaded file and this one, the file first."""
        chain = [stored]
        while chain[0].parent_id is not None:
            parent = self._datasets.get(chain[0].parent_id)
            if parent is None:  # pragma: no cover - a parent is never removed
                break
            chain.insert(0, parent)
        return chain

    def derived_name(self, parent: StoredDataset, step_count: int) -> str:
        """Name a derived dataset after the file it came from and how far it has come."""
        chain = self.lineage(parent)
        total = step_count + sum(
            len(dataset.recipe.steps) for dataset in chain if dataset.recipe is not None
        )
        return f"{chain[0].filename} ({steps_phrase(total)})"

    def provenance(self, stored: StoredDataset) -> Provenance:
        """What every recipe between the uploaded file and this dataset did to it."""
        return provenance_of(
            dataset.recipe
            for dataset in self.lineage(stored)
            if dataset.recipe is not None
        )

    def total_steps(self, stored: StoredDataset, extra: int = 0) -> int:
        """How many steps separate this dataset from the file it came from."""
        return extra + sum(
            len(dataset.recipe.steps)
            for dataset in self.lineage(stored)
            if dataset.recipe is not None
        )

    def _child_count(self, parent_id: str) -> int:
        return sum(1 for stored in self._datasets.values() if stored.parent_id == parent_id)

    def _rebuild(self, stored: StoredDataset) -> pd.DataFrame:
        parent = self._datasets[stored.parent_id or ""]
        run = run_recipe(
            self.frame_of(parent),
            planned_columns(parent.profile.column_schemas),
            stored.recipe or Recipe(),
        )
        if run.refusal is not None:  # pragma: no cover - the recipe was accepted once
            raise RuntimeError(f"A stored recipe stopped working: {run.refusal.reason}")
        return run.frame

    def _remember(self, dataset_id: str, frame: pd.DataFrame) -> None:
        self._derived[dataset_id] = frame
        self._derived.move_to_end(dataset_id)
        while len(self._derived) > DERIVED_CACHE_SIZE:
            self._derived.popitem(last=False)


dataset_store = DatasetStore()
