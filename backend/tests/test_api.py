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


def test_unknown_dataset_returns_404():
    assert client.get("/api/datasets/does-not-exist/profile").status_code == 404


def test_upload_rejects_unsupported_type():
    response = client.post("/api/upload", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]
