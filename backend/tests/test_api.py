from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

CSV = b"name,age,city\nAda,36,Ankara\nGrace,45,Izmir\nAlan,41,Ankara\n"


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_returns_profile():
    response = client.post("/api/upload", files={"file": ("people.csv", CSV, "text/csv")})
    assert response.status_code == 200

    body = response.json()
    assert body["rows"] == 3
    assert body["columns"] == 3
    assert body["filename"] == "people.csv"
    assert body["duplicate_rows"] == 0
    assert len(body["column_schemas"]) == 3


def test_uploaded_profile_can_be_fetched_by_id():
    dataset_id = client.post("/api/upload", files={"file": ("people.csv", CSV, "text/csv")}).json()["dataset_id"]

    response = client.get(f"/api/datasets/{dataset_id}/profile")
    assert response.status_code == 200
    assert response.json()["dataset_id"] == dataset_id


def test_preview_returns_rows_with_missing_values_as_null():
    csv = b"name,age\nAda,36\nGrace,\n"
    dataset_id = client.post("/api/upload", files={"file": ("people.csv", csv, "text/csv")}).json()["dataset_id"]

    body = client.get(f"/api/datasets/{dataset_id}/preview").json()
    assert body["columns"] == ["name", "age"]
    assert body["total_rows"] == 2
    assert body["rows"][0] == {"name": "Ada", "age": 36}
    assert body["rows"][1]["age"] is None


def test_preview_respects_limit():
    dataset_id = client.post("/api/upload", files={"file": ("people.csv", CSV, "text/csv")}).json()["dataset_id"]

    body = client.get(f"/api/datasets/{dataset_id}/preview?limit=2").json()
    assert len(body["rows"]) == 2
    assert body["total_rows"] == 3


def test_unknown_dataset_returns_404():
    assert client.get("/api/datasets/does-not-exist/profile").status_code == 404
    assert client.get("/api/datasets/does-not-exist/preview").status_code == 404


def test_upload_rejects_unsupported_type():
    response = client.post("/api/upload", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


STRUCTURED_CSV = b"segment,revenue\n" + b"".join(
    (f"enterprise,{200 + index}\n".encode() for index in range(40))
) + b"".join((f"smb,{50 + index}\n".encode() for index in range(40)))


def test_insights_endpoint_returns_structured_findings():
    dataset_id = client.post(
        "/api/upload", files={"file": ("segments.csv", STRUCTURED_CSV, "text/csv")}
    ).json()["dataset_id"]

    body = client.get(f"/api/datasets/{dataset_id}/insights").json()
    insight = next(
        item for item in body["insights"] if item["insight_type"] == "group_difference"
    )

    assert body["dataset_id"] == dataset_id
    assert insight["columns"] == ["segment", "revenue"]
    assert insight["metrics"]["highest_group"] == "enterprise"
    assert 0 <= insight["strength"] <= 1


def test_insights_for_an_unknown_dataset_return_404():
    assert client.get("/api/datasets/does-not-exist/insights").status_code == 404


def test_explanations_endpoint_degrades_without_a_key():
    dataset_id = client.post(
        "/api/upload", files={"file": ("segments.csv", STRUCTURED_CSV, "text/csv")}
    ).json()["dataset_id"]

    body = client.get(f"/api/datasets/{dataset_id}/explanations").json()

    assert body["available"] is False
    assert body["explanations"] == []
    assert "key" in body["reason"]


def test_explanations_for_an_unknown_dataset_return_404():
    assert client.get("/api/datasets/does-not-exist/explanations").status_code == 404
