import base64
import hashlib
import json
import sqlite3
import time
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.accounts import AccountStore, SignInError, google
from app.api.auth import SESSION_COOKIE, state_cookie
from app.config import settings
from app.main import app

pytestmark = pytest.mark.accounts

CLIENT_ID = "client-123.apps.googleusercontent.com"


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
    monkeypatch.setattr(settings, "google_client_secret", "shh")
    monkeypatch.setattr(settings, "app_url", "http://localhost:3000")


def id_token(**claims) -> str:
    def part(value) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'RS256'})}.{part(claims)}.signature"


def google_answers(monkeypatch, sub="google-1", email="ada.lovelace@gmail.com", **extra):
    """Stand in for Google's token endpoint, echoing the nonce it was sent with."""
    exchanged = []

    def exchange(code, verifier, client_id, client_secret, redirect_uri):
        exchanged.append({"code": code, "verifier": verifier, "secret": client_secret})
        claims = {
            "iss": "https://accounts.google.com", "aud": client_id, "sub": sub,
            "email": email, "email_verified": True, "exp": time.time() + 300,
            "nonce": google_answers.nonce,
        }
        claims.update(extra)
        return id_token(**claims)

    monkeypatch.setattr(google, "exchange_code", exchange)
    return exchanged


def leave_for_google(client: TestClient) -> dict[str, str]:
    response = client.get("/api/auth/google/start", follow_redirects=False)
    assert response.status_code == 302
    location = urlparse(response.headers["location"])
    query = {key: values[0] for key, values in parse_qs(location.query).items()}
    google_answers.nonce = query["nonce"]
    return query


def come_back(client: TestClient, **query):
    return client.get("/api/auth/google/callback", params=query, follow_redirects=False)


def test_google_is_not_offered_until_configured():
    client = TestClient(app)
    assert client.get("/api/auth/options").json() == {"google": False, "github": False}
    assert client.get("/api/auth/google/start", follow_redirects=False).status_code == 404


def test_starting_sends_the_browser_to_google_with_one_time_values(configured):
    client = TestClient(app)
    assert client.get("/api/auth/options").json() == {"google": True, "github": False}
    query = leave_for_google(client)
    assert query["client_id"] == CLIENT_ID
    assert query["redirect_uri"] == settings.google_redirect_uri
    assert query["scope"] == "openid email"
    assert query["code_challenge_method"] == "S256"
    assert client.cookies[state_cookie("google")] == query["state"]
    assert leave_for_google(client)["state"] != query["state"]


def test_coming_back_from_google_signs_in(configured, monkeypatch):
    exchanged = google_answers(monkeypatch)
    client = TestClient(app)
    query = leave_for_google(client)
    response = come_back(client, code="the-code", state=query["state"])

    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:3000/"
    assert SESSION_COOKIE in response.cookies
    assert client.get("/api/auth/me").json() == {"username": "ada.lovelace"}
    assert exchanged == [{"code": "the-code", "verifier": exchanged[0]["verifier"], "secret": "shh"}]
    # The verifier is the one whose hash went to Google.
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(exchanged[0]["verifier"].encode()).digest()
    ).rstrip(b"=").decode()
    assert challenge == query["code_challenge"]


def test_the_same_google_account_comes_back_to_the_same_account(configured, monkeypatch):
    google_answers(monkeypatch)
    first, second = TestClient(app), TestClient(app)
    come_back(first, code="a", state=leave_for_google(first)["state"])
    come_back(second, code="b", state=leave_for_google(second)["state"])
    assert second.get("/api/auth/me").json() == {"username": "ada.lovelace"}


def test_a_taken_username_gets_a_number(configured, monkeypatch):
    TestClient(app).post(
        "/api/auth/signup", json={"username": "ada.lovelace", "password": "a password here"}
    )
    google_answers(monkeypatch)
    client = TestClient(app)
    come_back(client, code="c", state=leave_for_google(client)["state"])
    assert client.get("/api/auth/me").json() == {"username": "ada.lovelace-2"}


def test_a_google_account_has_no_password_to_guess(configured, monkeypatch):
    google_answers(monkeypatch)
    client = TestClient(app)
    come_back(client, code="c", state=leave_for_google(client)["state"])
    for password in ("", "anything at all"):
        response = TestClient(app).post(
            "/api/auth/login", json={"username": "ada.lovelace", "password": password}
        )
        assert response.status_code == 401


def test_a_state_from_another_browser_is_refused(configured, monkeypatch):
    exchanged = google_answers(monkeypatch)
    attacker, victim = TestClient(app), TestClient(app)
    attacker_state = leave_for_google(attacker)["state"]
    leave_for_google(victim)
    response = come_back(victim, code="attackers-code", state=attacker_state)
    assert response.headers["location"] == "http://localhost:3000/?signin=failed&with=google"
    assert victim.get("/api/auth/me").status_code == 401
    assert exchanged == []


def test_a_callback_cannot_be_replayed(configured, monkeypatch):
    google_answers(monkeypatch)
    client = TestClient(app)
    state = leave_for_google(client)["state"]
    assert come_back(client, code="c", state=state).headers["location"].endswith("/")
    client.cookies.set(state_cookie("google"), state, path="/api/auth/google")
    replay = come_back(client, code="c", state=state)
    assert replay.headers["location"].endswith("?signin=failed&with=google")


def test_cancelling_at_google_says_so(configured):
    client = TestClient(app)
    leave_for_google(client)
    response = come_back(client, error="access_denied")
    assert response.headers["location"] == "http://localhost:3000/?signin=cancelled&with=google"


@pytest.mark.parametrize(
    "claims",
    [
        {"aud": "someone-elses-client"},
        {"iss": "https://evil.example"},
        {"exp": 1},
        {"nonce": "another sign-in"},
        {"email_verified": False},
    ],
)
def test_an_untrustworthy_token_does_not_sign_in(configured, monkeypatch, claims):
    google_answers(monkeypatch, **claims)
    client = TestClient(app)
    response = come_back(client, code="c", state=leave_for_google(client)["state"])
    assert response.headers["location"].endswith("?signin=failed&with=google")
    assert client.get("/api/auth/me").status_code == 401


def test_a_failed_exchange_does_not_sign_in(configured, monkeypatch):
    def broken(*args):
        raise SignInError("Google is down")

    monkeypatch.setattr(google, "exchange_code", broken)
    client = TestClient(app)
    response = come_back(client, code="c", state=leave_for_google(client)["state"])
    assert response.headers["location"].endswith("?signin=failed&with=google")


def test_a_sign_in_left_too_long_expires(tmp_path):
    now = [1000.0]
    store = AccountStore(lambda: tmp_path / "a.db", lambda: 60, clock=lambda: now[0])
    store.begin_sign_in("google", "state", "verifier", "nonce")
    now[0] += 601
    assert store.finish_sign_in("google", "state") is None


@pytest.mark.parametrize(
    "hint,username",
    [("ada", "ada"), ("a", "user-a"), ("+++", "user"), ("x" * 40, "x" * 28),
     ("Ada-Lovelace", "Ada-Lovelace")],
)
def test_usernames_from_providers_follow_the_rules(hint, username):
    from app.accounts.store import USERNAME, username_from

    assert username_from(hint) == username
    assert USERNAME.fullmatch(username)


def test_a_database_from_before_outside_sign_ins_gains_them(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            "CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE "
            "COLLATE NOCASE, password_hash TEXT NOT NULL, created_at REAL NOT NULL);"
        )
    AccountStore(lambda: path, lambda: 60).sign_up("grace", "an old password")

    store = AccountStore(lambda: path, lambda: 60)
    assert store.log_in("grace", "an old password").username == "grace"
    assert store.account_for_identity("google", "g-1", "grace").username == "grace-2"
