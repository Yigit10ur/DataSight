import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.accounts import AccountError, AccountStore
from app.api.auth import SESSION_COOKIE
from app.config import settings
from app.main import app

pytestmark = pytest.mark.accounts

CSV = b"name,value\nalpha,10\nbeta,20\ngamma,30\n"
PASSWORD = "correct horse battery"


def signed_up(username: str) -> TestClient:
    client = TestClient(app)
    response = client.post("/api/auth/signup", json={"username": username, "password": PASSWORD})
    assert response.status_code == 201
    return client


def upload(client: TestClient):
    return client.post("/api/upload", files={"file": ("demo.csv", CSV, "text/csv")})


def test_signing_up_signs_in():
    client = TestClient(app)
    response = client.post("/api/auth/signup", json={"username": "ada", "password": PASSWORD})
    assert response.status_code == 201
    assert response.json() == {"username": "ada"}
    assert client.get("/api/auth/me").json() == {"username": "ada"}

    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_a_username_is_taken_whatever_its_case():
    signed_up("ada")
    response = TestClient(app).post(
        "/api/auth/signup", json={"username": "ADA", "password": PASSWORD}
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "That username is taken."


@pytest.mark.parametrize(
    "username,password,message",
    [
        ("ab", PASSWORD, "3 to 32 characters"),
        ("has space", PASSWORD, "3 to 32 characters"),
        ("ada", "short", "at least 8"),
        ("ada", "x" * 257, "at most 256"),
    ],
)
def test_sign_up_rules_are_explained(username, password, message):
    response = TestClient(app).post(
        "/api/auth/signup", json={"username": username, "password": password}
    )
    assert response.status_code == 400
    assert message in response.json()["detail"]


def test_logging_in_checks_the_password():
    signed_up("ada")
    client = TestClient(app)
    for username, password in [("ada", "wrong password"), ("nobody", PASSWORD)]:
        response = client.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
        # The same answer either way, so a guess cannot tell names from passwords.
        assert response.status_code == 401
        assert response.json()["detail"] == "Wrong username or password."
    assert client.get("/api/auth/me").status_code == 401

    response = client.post("/api/auth/login", json={"username": "Ada", "password": PASSWORD})
    assert response.status_code == 200
    assert response.json() == {"username": "ada"}
    assert client.get("/api/auth/me").status_code == 200


def test_logging_out_ends_the_session_for_good():
    client = signed_up("ada")
    token = client.cookies[SESSION_COOKIE]
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401

    replay = TestClient(app, cookies={SESSION_COOKIE: token})
    assert replay.get("/api/auth/me").status_code == 401


def test_neither_passwords_nor_session_tokens_are_stored_as_given():
    client = signed_up("ada")
    token = client.cookies[SESSION_COOKIE]
    with sqlite3.connect(settings.database_path) as connection:
        stored = [str(value) for row in connection.execute(
            "SELECT * FROM users UNION ALL SELECT token_hash, user_id, expires_at, NULL "
            "FROM sessions"
        ) for value in row]
    assert not any(PASSWORD in value or token in value for value in stored)


def test_sessions_expire(tmp_path):
    now = [1000.0]
    store = AccountStore(lambda: tmp_path / "a.db", lambda: 60, clock=lambda: now[0])
    token = store.start_session(store.sign_up("ada", PASSWORD))
    now[0] += 59
    assert store.account_for(token).username == "ada"
    now[0] += 1
    assert store.account_for(token) is None
    store.purge_expired_sessions()
    with sqlite3.connect(tmp_path / "a.db") as connection:
        assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone() == (0,)


def test_accounts_outlive_the_store_object(tmp_path):
    path = tmp_path / "a.db"
    AccountStore(lambda: path, lambda: 60).sign_up("ada", PASSWORD)
    assert AccountStore(lambda: path, lambda: 60).log_in("ada", PASSWORD).username == "ada"
    with pytest.raises(AccountError):
        AccountStore(lambda: path, lambda: 60).log_in("ada", "not it at all")


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/upload"),
        ("get", "/api/datasets/anything/profile"),
        ("get", "/api/datasets/anything/charts"),
        ("post", "/api/datasets/anything/recipe/preview"),
        ("get", "/api/datasets/anything/lineage"),
    ],
)
def test_datasets_need_an_account(method, path):
    response = getattr(TestClient(app), method)(path)
    assert response.status_code == 401
    assert response.json()["detail"] == "Log in to continue."


def test_the_health_check_needs_no_account():
    assert TestClient(app).get("/api/health").status_code == 200


def test_a_dataset_is_visible_only_to_its_owner():
    ada, grace = signed_up("ada"), signed_up("grace")
    dataset_id = upload(ada).json()["dataset_id"]
    recipe = {"steps": [{"op": "limit_rows", "count": 1}]}

    for path in ("profile", "preview", "analysis", "charts", "quality", "insights", "lineage"):
        assert ada.get(f"/api/datasets/{dataset_id}/{path}").status_code == 200
        response = grace.get(f"/api/datasets/{dataset_id}/{path}")
        assert response.status_code == 404
        assert response.json() == {"detail": "Dataset not found."}
    for path in ("preview", "apply", "export"):
        assert grace.post(f"/api/datasets/{dataset_id}/recipe/{path}", json=recipe).status_code == 404

    derived = ada.post(f"/api/datasets/{dataset_id}/recipe/apply", json=recipe)
    assert derived.status_code == 200
    assert grace.get(f"/api/datasets/{derived.json()['dataset_id']}/profile").status_code == 404


def test_one_account_cannot_take_every_dataset_slot(monkeypatch):
    monkeypatch.setattr(settings, "max_datasets_per_user", 2)
    ada, grace = signed_up("ada"), signed_up("grace")
    assert [upload(ada).status_code for _ in range(2)] == [200, 200]
    refused = upload(ada)
    assert refused.status_code == 409
    assert "one account can hold" in refused.json()["detail"]
    assert upload(grace).status_code == 200


def test_one_account_cannot_take_all_the_memory(monkeypatch):
    ada, grace = signed_up("ada"), signed_up("grace")
    first = upload(ada)
    monkeypatch.setattr(settings, "max_user_store_bytes", 1)
    refused = upload(grace)
    assert refused.status_code == 409
    assert "one account can use" in refused.json()["detail"]
    assert first.status_code == 200


def test_writes_started_by_another_site_are_refused():
    client = TestClient(app)
    response = client.post(
        "/api/auth/login",
        json={"username": "ada", "password": PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403

    allowed = client.post(
        "/api/auth/signup",
        json={"username": "ada", "password": PASSWORD},
        headers={"Origin": "http://localhost:3000"},
    )
    assert allowed.status_code == 201
