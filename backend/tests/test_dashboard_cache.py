from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.dashboard as dashboard
from app.config import settings
from app.dashboard import DashboardAnalysis, dashboard_cache
from app.main import app
from app.profiling import profile_dataset
from app.store import DatasetStore


client = TestClient(app)
REPRESENTATIVE_CSV = b"segment,revenue,cost\n" + b"".join(
    f"{'enterprise' if index % 2 else 'smb'},{100 + index * 3},{40 + index}\n".encode()
    for index in range(200)
)


@pytest.fixture(autouse=True)
def empty_dashboard_cache():
    dashboard_cache.clear()
    yield
    dashboard_cache.clear()


def upload(content=REPRESENTATIVE_CSV, filename="sales.csv") -> str:
    response = client.post("/api/upload", files={"file": (filename, content, "text/csv")})
    assert response.status_code == 200, response.text
    return response.json()["dataset_id"]


def counting_pipeline(monkeypatch):
    counts = {"analysis": 0, "quality": 0, "charts": 0, "insights": 0}
    targets = {
        "analysis": "analyze_dataset",
        "quality": "check_dataset_quality",
        "charts": "build_charts",
        "insights": "build_insights",
    }
    for label, name in targets.items():
        original = getattr(dashboard, name)

        def counted(*args, _label=label, _original=original, **kwargs):
            counts[_label] += 1
            return _original(*args, **kwargs)

        monkeypatch.setattr(dashboard, name, counted)
    return counts


def test_normal_dashboard_load_computes_each_stage_once(monkeypatch):
    dataset_id = upload()
    counts = counting_pipeline(monkeypatch)

    # These are the three concurrent requests made by the frontend after upload.
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses = list(
            pool.map(
                client.get,
                [
                    f"/api/datasets/{dataset_id}/charts",
                    f"/api/datasets/{dataset_id}/quality",
                    f"/api/datasets/{dataset_id}/insights",
                ],
            )
        )

    assert all(response.status_code == 200 for response in responses)
    assert counts == {"analysis": 1, "quality": 1, "charts": 1, "insights": 1}

    # The compatibility endpoint reuses the same deterministic result.
    assert client.get(f"/api/datasets/{dataset_id}/analysis").status_code == 200
    assert counts == {"analysis": 1, "quality": 1, "charts": 1, "insights": 1}


def test_cached_endpoints_return_the_same_results_as_direct_computation():
    dataset_id = upload()
    from app.api import routes

    stored = routes.dataset_store.get(dataset_id)
    frame = routes.dataset_store.frame_of(stored)
    provenance = routes.dataset_store.provenance(stored)
    analysis = dashboard.analyze_dataset(frame, stored.profile)
    quality = dashboard.check_dataset_quality(frame, stored.profile, provenance)
    charts = dashboard.build_charts(frame, stored.profile, analysis)
    insights = dashboard.build_insights(
        stored.profile, analysis, quality, charts.charts, provenance
    )

    expected = {
        "analysis": analysis,
        "quality": quality,
        "charts": charts,
        "insights": insights,
    }
    for endpoint, model in expected.items():
        response = client.get(f"/api/datasets/{dataset_id}/{endpoint}")
        assert response.status_code == 200
        assert response.json() == model.model_dump(mode="json")


def test_cache_entries_are_isolated_for_uploaded_and_derived_datasets(monkeypatch):
    root_id = upload()
    derived = client.post(
        f"/api/datasets/{root_id}/recipe/apply",
        json={"steps": [{"op": "limit_rows", "count": 20}]},
    )
    assert derived.status_code == 200
    derived_id = derived.json()["dataset_id"]
    counts = counting_pipeline(monkeypatch)

    root = client.get(f"/api/datasets/{root_id}/analysis")
    child = client.get(f"/api/datasets/{derived_id}/analysis")
    assert root.status_code == child.status_code == 200
    assert root.json()["dataset_id"] == root_id
    assert child.json()["dataset_id"] == derived_id
    assert root.json()["numeric"][0]["count"] == 200
    assert child.json()["numeric"][0]["count"] == 20
    assert counts == {"analysis": 2, "quality": 2, "charts": 2, "insights": 2}
    assert set(dashboard_cache._entries) == {root_id, derived_id}


def test_cache_is_bounded_and_does_not_retain_dataframes(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_cache_size", 2)
    ids = [upload(filename=f"sales-{index}.csv") for index in range(3)]
    for dataset_id in ids:
        assert client.get(f"/api/datasets/{dataset_id}/charts").status_code == 200

    assert list(dashboard_cache._entries) == ids[-2:]
    assert all(isinstance(value, DashboardAnalysis) for value in dashboard_cache._entries.values())
    assert all(
        not isinstance(field, pd.DataFrame)
        for value in dashboard_cache._entries.values()
        for field in vars(value).values()
    )


def test_delete_and_expiration_remove_cached_results(monkeypatch):
    now = [100.0]
    store = DatasetStore(clock=lambda: now[0])
    monkeypatch.setattr(settings, "dataset_ttl_seconds", 10)
    frame = pd.DataFrame({"value": [1, 2, 3]})

    first_id = store.new_id()
    first = store.add(
        first_id, "first.csv", frame,
        profile_dataset(first_id, "first.csv", frame),
    )
    dashboard_cache.get_or_compute(
        first_id, frame, first.profile, store.provenance(first), retain=lambda: True
    )
    assert first_id in dashboard_cache._entries
    store.remove(first_id)
    assert first_id not in dashboard_cache._entries

    second_id = store.new_id()
    second = store.add(
        second_id, "second.csv", frame,
        profile_dataset(second_id, "second.csv", frame),
    )
    dashboard_cache.get_or_compute(
        second_id, frame, second.profile, store.provenance(second), retain=lambda: True
    )
    now[0] += 10
    store.expire()
    assert second_id not in dashboard_cache._entries


def test_result_finishing_after_expiration_is_not_cached(monkeypatch):
    now = [100.0]
    store = DatasetStore(clock=lambda: now[0])
    monkeypatch.setattr(settings, "dataset_ttl_seconds", 10)
    frame = pd.DataFrame({"value": [1, 2, 3]})
    dataset_id = store.new_id()
    stored = store.add(
        dataset_id, "late.csv", frame,
        profile_dataset(dataset_id, "late.csv", frame),
    )
    original = dashboard.build_insights

    def expire_after_compute(*args, **kwargs):
        result = original(*args, **kwargs)
        now[0] += 10
        store.expire()
        return result

    monkeypatch.setattr(dashboard, "build_insights", expire_after_compute)
    dashboard_cache.get_or_compute(
        dataset_id,
        frame,
        stored.profile,
        store.provenance(stored),
        retain=lambda: store.get(dataset_id) is stored,
    )
    assert dataset_id not in dashboard_cache._entries
    assert dataset_id not in dashboard_cache._locks
