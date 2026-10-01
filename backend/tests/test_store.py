import pandas as pd

from app.profiling import profile_dataset
from app.recipes import (
    Aggregation,
    Aggregate,
    LimitRows,
    Recipe,
    SelectColumns,
    planned_columns,
    run_recipe,
)
from app.store import (
    DERIVED_CACHE_SIZE,
    MAX_DERIVED_PER_PARENT,
    MAX_LINEAGE_DEPTH,
    DatasetLimit,
    DatasetStore,
)
from tests.conftest import TEST_ACCOUNT


def orders() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "city": ["Ankara", "Izmir", "Bursa", "Izmir"] * 10,
            "revenue": [100.0 + index * 37 for index in range(40)],
            "cost": [50.0 + index * 11 for index in range(40)],
        }
    )


def uploaded() -> tuple[DatasetStore, object]:
    store = DatasetStore()
    frame = orders()
    dataset_id = store.new_id()
    profile = profile_dataset(dataset_id, "orders.csv", frame)
    store.add(dataset_id, TEST_ACCOUNT.id, "orders.csv", frame, profile)
    return store, store.get(dataset_id)


def derive(store: DatasetStore, parent, recipe: Recipe):
    """Do what the apply endpoint does, without the endpoint."""
    run = run_recipe(
        store.frame_of(parent), planned_columns(parent.profile.column_schemas), recipe
    )
    assert run.refusal is None, run.refusal
    dataset_id = store.new_id()
    profile = profile_dataset(
        dataset_id, store.derived_name(parent, len(recipe.steps)), run.frame
    )
    return store.add_derived(dataset_id, parent, recipe, run.frame, profile), run.frame


def test_a_derived_dataset_is_kept_as_its_recipe_and_not_as_a_second_copy():
    store, root = uploaded()
    recipe = Recipe(steps=[SelectColumns(columns=["city", "revenue"])])

    derived, _ = derive(store, root, recipe)

    assert derived.parent_id == root.dataset_id
    assert derived.recipe == recipe
    assert derived.is_derived
    assert not root.is_derived


def test_a_derived_frame_survives_falling_out_of_the_cache():
    """The claim the whole storage decision rests on.

    Derived data is held as a recipe, so a frame the cache lets go of has to come
    back identical when it is asked for again. If it did not, the cache would be
    deciding what the data is.
    """
    store, root = uploaded()
    first, at_apply_time = derive(
        store,
        root,
        Recipe(
            steps=[
                Aggregate(
                    group_by=["city"],
                    aggregations=[Aggregation(function="sum", column="revenue")],
                )
            ]
        ),
    )

    # Push it out by deriving more than the cache holds.
    for count in range(DERIVED_CACHE_SIZE + 1):
        derive(store, root, Recipe(steps=[LimitRows(count=count + 1)]))

    pd.testing.assert_frame_equal(store.frame_of(first), at_apply_time)


def test_deriving_never_touches_the_uploaded_frame():
    store, root = uploaded()
    before = store.frame_of(root).copy()

    derive(store, root, Recipe(steps=[LimitRows(count=5)]))

    pd.testing.assert_frame_equal(store.frame_of(root), before)


def test_lineage_runs_from_the_uploaded_file_down_to_here():
    store, root = uploaded()
    first, _ = derive(store, root, Recipe(steps=[SelectColumns(columns=["city", "revenue"])]))
    second, _ = derive(store, first, Recipe(steps=[LimitRows(count=10)]))

    chain = store.lineage(second)

    assert [dataset.dataset_id for dataset in chain] == [
        root.dataset_id,
        first.dataset_id,
        second.dataset_id,
    ]
    assert chain[0].recipe is None


def test_a_derived_name_counts_every_step_back_to_the_file():
    store, root = uploaded()
    first, _ = derive(store, root, Recipe(steps=[SelectColumns(columns=["city", "revenue"])]))
    second, _ = derive(store, first, Recipe(steps=[LimitRows(count=10)]))

    assert first.filename == "orders.csv (1 step)"
    assert second.filename == "orders.csv (2 steps)"


def test_a_chain_that_goes_too_deep_is_refused():
    store, parent = uploaded()
    for _ in range(MAX_LINEAGE_DEPTH - 1):
        parent, _ = derive(store, parent, Recipe(steps=[LimitRows(count=40)]))

    try:
        derive(store, parent, Recipe(steps=[LimitRows(count=40)]))
    except DatasetLimit as limit:
        assert str(MAX_LINEAGE_DEPTH) in str(limit)
    else:  # pragma: no cover
        raise AssertionError("a chain past the cap was accepted")


def test_too_many_datasets_shaped_from_one_is_refused():
    store, root = uploaded()
    for count in range(MAX_DERIVED_PER_PARENT):
        derive(store, root, Recipe(steps=[LimitRows(count=count + 1)]))

    try:
        derive(store, root, Recipe(steps=[LimitRows(count=1)]))
    except DatasetLimit as limit:
        assert str(MAX_DERIVED_PER_PARENT) in str(limit)
    else:  # pragma: no cover
        raise AssertionError("a dataset past the cap was accepted")
