import asyncio
import io
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.ai import insight_explainer
from app.api import routes
from app.config import Settings, settings
from app.main import app
from app.profiling import profile_dataset
from app.quality import check_dataset_quality
from app.recipes import LimitRows, Recipe
from app.store import DatasetLimit, DatasetNotFound, DatasetStore

CSV = b"name,value\nalpha,10\nbeta,20\n"


@pytest.fixture
def retained(monkeypatch):
    now = [100.0]
    store = DatasetStore(clock=lambda: now[0])
    monkeypatch.setattr(settings, "dataset_ttl_seconds", 10)
    monkeypatch.setattr(settings, "max_datasets", 100)
    monkeypatch.setattr(routes, "dataset_store", store)
    return store, now, TestClient(app)


def upload(client):
    return client.post("/api/upload", files={"file": ("demo.csv", CSV, "text/csv")})


def add(store):
    frame = pd.DataFrame({"value": [10, 20, 30]})
    dataset_id = store.new_id()
    return store.add(dataset_id, "demo.csv", frame, profile_dataset(dataset_id, "demo.csv", frame))


def derive(store, parent):
    frame = store.frame_of(parent).head(2)
    dataset_id = store.new_id()
    return store.add_derived(
        dataset_id, parent, Recipe(steps=[LimitRows(count=2)]), frame,
        profile_dataset(dataset_id, "derived.csv", frame),
    )


@pytest.mark.parametrize("offset,expected", [(1, 200), (0, 200), (-1, 413)])
def test_upload_limit_boundaries(retained, monkeypatch, offset, expected):
    store, _, client = retained
    monkeypatch.setattr(settings, "max_upload_bytes", len(CSV) + offset)
    response = upload(client)
    assert response.status_code == expected
    assert len(store._datasets) == (1 if expected == 200 else 0)
    if expected == 413:
        assert "bytes" in response.json()["detail"]
        assert not store._uploaded


def test_oversize_read_stops_at_limit_plus_one_and_closes_file(retained, monkeypatch):
    store, _, _ = retained
    limit = 70_000
    monkeypatch.setattr(settings, "max_upload_bytes", limit)
    stream = io.BytesIO(b"x" * (limit * 5))
    file = UploadFile(filename="huge.csv", file=stream)
    consumed = []
    original_read = file.read

    async def read(size=-1):
        assert 0 < size <= 64 * 1024
        chunk = await original_read(size)
        consumed.append(len(chunk))
        return chunk

    monkeypatch.setattr(file, "read", read)
    with patch.object(routes, "load_dataset") as loader:
        with pytest.raises(HTTPException) as error:
            asyncio.run(routes.upload(file))
        assert error.value.status_code == 413
        loader.assert_not_called()
    assert sum(consumed) == limit + 1
    assert stream.closed
    assert not store._datasets


def test_invalid_uploads_still_validate_and_are_not_stored(retained):
    store, _, client = retained
    for name, content in [("bad.txt", CSV), ("empty.csv", b""), ("headers.csv", b"a,b\n")]:
        assert client.post("/api/upload", files={"file": (name, content)}).status_code == 400
    assert not store._datasets


def test_xlsx_upload_still_works(retained):
    _, _, client = retained
    content = io.BytesIO()
    pd.DataFrame({"a": [1, 2]}).to_excel(content, index=False)
    response = client.post("/api/upload", files={"file": ("demo.xlsx", content.getvalue())})
    assert response.status_code == 200
    assert response.json()["rows"] == 2


def test_repeated_uploads_refuse_at_capacity_then_reclaim_expired_space(retained, monkeypatch):
    store, now, client = retained
    monkeypatch.setattr(settings, "max_datasets", 2)
    ids = [upload(client).json()["dataset_id"] for _ in range(2)]
    for _ in range(3):
        response = upload(client)
        assert response.status_code == 409
        assert "store is full" in response.json()["detail"]
        assert len(store._uploaded) == 2
    assert all(store.get(dataset_id) for dataset_id in ids)
    now[0] += 10
    assert upload(client).status_code == 200
    assert len(store._datasets) == 1
    assert all(store.get(dataset_id) is None for dataset_id in ids)


def test_derived_entries_count_toward_capacity(retained, monkeypatch):
    store, _, client = retained
    monkeypatch.setattr(settings, "max_datasets", 2)
    root = add(store)
    child = derive(store, root)
    response = client.post(f"/api/datasets/{child.dataset_id}/recipe/apply",
                           json={"steps": [{"op": "limit_rows", "count": 1}]})
    assert response.status_code == 409
    assert len(store._datasets) == 2
    assert [item.dataset_id for item in store.lineage(child)] == [root.dataset_id, child.dataset_id]


def test_expiration_is_fixed_and_descendants_share_root_deadline(retained):
    store, now, _ = retained
    root = add(store)
    now[0] += 5
    child = derive(store, root)
    grandchild = derive(store, child)
    other = add(store)
    assert root.expires_at == child.expires_at == grandchild.expires_at
    now[0] = 109.99
    assert store.get(grandchild.dataset_id) is grandchild
    now[0] = 110
    store.expire()
    assert set(store._datasets) == {other.dataset_id}
    assert set(store._uploaded) == {other.dataset_id}
    assert not store._derived
    for item in (root, child, grandchild):
        assert store.get(item.dataset_id) is None
        with pytest.raises(DatasetNotFound):
            store.frame_of(item)
        with pytest.raises(DatasetNotFound):
            store.lineage(item)
    with pytest.raises(DatasetNotFound):
        derive(store, child)


@pytest.mark.parametrize("endpoint", ["profile", "preview", "analysis", "charts", "quality", "insights", "explanations", "lineage"])
def test_expired_ids_receive_existing_not_found_response(retained, endpoint):
    store, now, client = retained
    root = add(store)
    child = derive(store, root)
    now[0] += 10
    for item in (root, child):
        response = client.get(f"/api/datasets/{item.dataset_id}/{endpoint}")
        assert response.status_code == 404
        assert response.json() == {"detail": "Dataset not found."}


@pytest.mark.parametrize("endpoint", ["preview", "apply", "export"])
def test_recipes_on_expired_ids_are_not_found(retained, endpoint):
    store, now, client = retained
    root = add(store)
    now[0] += 10
    response = client.post(f"/api/datasets/{root.dataset_id}/recipe/{endpoint}",
                           json={"steps": [{"op": "limit_rows", "count": 1}]})
    assert response.status_code == 404


def test_removing_a_branch_keeps_ancestors_and_siblings(retained):
    store, _, _ = retained
    root = add(store)
    child = derive(store, root)
    grandchild = derive(store, child)
    sibling = derive(store, root)
    store.remove(child.dataset_id)
    assert store.get(grandchild.dataset_id) is None
    assert [item.dataset_id for item in store.lineage(sibling)] == [root.dataset_id, sibling.dataset_id]
    assert set(store._derived) == {sibling.dataset_id}


def test_expiration_removes_explanation_cache_and_locks(retained):
    store, now, _ = retained
    root = add(store)
    child = derive(store, root)
    keys = [(root.dataset_id,), (child.dataset_id,)]
    for key in keys:
        insight_explainer._cache[key] = (None, [])
        insight_explainer._lock_for(key)
    now[0] += 10
    store.expire()
    assert all(key not in insight_explainer._cache for key in keys)
    assert all(key not in insight_explainer._locks for key in keys)


def test_model_response_cannot_restore_expired_cache(retained):
    store, now, _ = retained
    root = add(store)
    score = check_dataset_quality(store.frame_of(root), root.profile).score

    class ExpiringClient:
        def complete(self, system, user):
            now[0] += 10
            store.expire()
            return '{"summary": "A small dataset.", "explanations": {}}'

    insight_explainer.explain_insights(root.profile, score, [], client=ExpiringClient())
    assert (root.dataset_id,) not in insight_explainer._cache
    assert (root.dataset_id,) not in insight_explainer._locks


def test_late_explanation_request_returns_404_and_clears_cache(retained, monkeypatch):
    store, now, client = retained
    root = add(store)

    class FakeClient:
        def complete(self, system, user):
            return '{"summary": "A small dataset.", "explanations": {}}'

    def late_explanation(profile, score, insights):
        now[0] += 10
        store.expire()
        return insight_explainer.explain_insights(profile, score, insights, client=FakeClient())

    monkeypatch.setattr(routes, "explain_insights", late_explanation)
    response = client.get(f"/api/datasets/{root.dataset_id}/explanations")
    assert response.status_code == 404
    assert not any(key[0] == root.dataset_id for key in insight_explainer._cache)
    assert not any(key[0] == root.dataset_id for key in insight_explainer._locks)


def test_rebuild_crossing_deadline_does_not_restore_derived_frame(retained, monkeypatch):
    import app.store as storage
    store, now, _ = retained
    root = add(store)
    child = derive(store, root)
    store._derived.clear()
    original = storage.run_recipe

    def slow_recipe(*args, **kwargs):
        result = original(*args, **kwargs)
        now[0] += 10
        return result

    monkeypatch.setattr(storage, "run_recipe", slow_recipe)
    with pytest.raises(DatasetNotFound):
        store.frame_of(child)
    assert not store._derived
    assert not store._datasets


def test_concurrent_adds_cannot_exceed_capacity(retained, monkeypatch):
    store, _, _ = retained
    monkeypatch.setattr(settings, "max_datasets", 2)
    def attempt(_):
        try:
            add(store)
            return True
        except DatasetLimit:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(16))) == 2
    assert len(store._datasets) == len(store._uploaded) == 2


@pytest.mark.parametrize(
    "setting",
    ["max_upload_bytes", "max_datasets", "dataset_ttl_seconds", "dashboard_cache_size"],
)
@pytest.mark.parametrize("value", [0, -1])
def test_storage_settings_must_be_positive(setting, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{setting: value})


def test_idle_sweeper_expires_data(retained, monkeypatch):
    import app.main as main
    store, now, _ = retained
    root = add(store)
    monkeypatch.setattr(main, "dataset_store", store)
    calls = 0

    async def tick(_):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise asyncio.CancelledError
        now[0] += 10

    with patch.object(main.asyncio, "sleep", AsyncMock(side_effect=tick)):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(main.expire_datasets())
    assert root.dataset_id not in store._datasets
