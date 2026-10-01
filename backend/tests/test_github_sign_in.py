import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.accounts import account_store, github, google
from app.api.auth import SESSION_COOKIE, state_cookie
from app.config import settings
from app.main import app

pytestmark = pytest.mark.accounts


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "github_client_id", "gh-client")
    monkeypatch.setattr(settings, "github_client_secret", "gh-secret")
    monkeypatch.setattr(settings, "app_url", "http://localhost:3000")


class FakeGitHub:
    """Answers the two requests the sign-in makes, as GitHub's endpoints would."""

    def __init__(self, user_id=583231, login="octocat", token_answer=None):
        self.profile = {"id": user_id, "login": login}
        self.token_answer = token_answer or {"access_token": "gho_token", "token_type": "bearer"}
        self.requests = []

    def __call__(self, url, *, data=None, headers):
        self.requests.append({"url": url, "data": data, "headers": headers})
        if url == github.TOKEN_URL:
            return self.token_answer
        if url == github.USER_URL:
            return self.profile
        raise AssertionError(f"Unexpected request to {url}")


@pytest.fixture
def fake_github(monkeypatch):
    fake = FakeGitHub()
    monkeypatch.setattr(github, "fetch_json", fake)
    return fake


def leave_for_github(client: TestClient) -> dict[str, str]:
    response = client.get("/api/auth/github/start", follow_redirects=False)
    assert response.status_code == 302
    location = urlparse(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == github.AUTHORIZE_URL
    return {key: values[0] for key, values in parse_qs(location.query).items()}


def come_back(client: TestClient, provider="github", **query):
    return client.get(f"/api/auth/{provider}/callback", params=query, follow_redirects=False)


def test_github_is_not_offered_until_configured():
    client = TestClient(app)
    assert client.get("/api/auth/options").json() == {"google": False, "github": False}
    assert client.get("/api/auth/github/start", follow_redirects=False).status_code == 404


def test_starting_asks_github_for_nothing_but_the_public_profile(configured):
    client = TestClient(app)
    assert client.get("/api/auth/options").json()["github"] is True
    query = leave_for_github(client)
    assert query["client_id"] == "gh-client"
    assert query["redirect_uri"] == settings.github_redirect_uri
    assert query["code_challenge_method"] == "S256"
    assert "scope" not in query
    assert client.cookies[state_cookie("github")] == query["state"]


def test_coming_back_from_github_signs_in(configured, fake_github):
    client = TestClient(app)
    query = leave_for_github(client)
    response = come_back(client, code="the-code", state=query["state"])

    assert response.headers["location"] == "http://localhost:3000/"
    assert SESSION_COOKIE in response.cookies
    assert client.get("/api/auth/me").json() == {"username": "octocat"}

    exchange, profile = fake_github.requests
    sent = {key: values[0] for key, values in parse_qs(exchange["data"].decode()).items()}
    assert sent["code"] == "the-code" and sent["client_secret"] == "gh-secret"
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(sent["code_verifier"].encode()).digest()
    ).rstrip(b"=").decode()
    assert challenge == query["code_challenge"]
    assert exchange["headers"]["Accept"] == "application/json"
    assert profile["headers"]["Authorization"] == "Bearer gho_token"
    assert profile["headers"]["User-Agent"] == "DataSight"


def test_a_renamed_github_account_keeps_its_datasight_account(configured, fake_github):
    first = TestClient(app)
    come_back(first, code="a", state=leave_for_github(first)["state"])
    fake_github.profile["login"] = "octocat-renamed"
    second = TestClient(app)
    come_back(second, code="b", state=leave_for_github(second)["state"])
    assert second.get("/api/auth/me").json() == {"username": "octocat"}


def test_the_same_id_at_google_and_github_are_different_people(configured, fake_github):
    github_client = TestClient(app)
    come_back(github_client, code="a", state=leave_for_github(github_client)["state"])

    other = account_store.account_for_identity("google", "583231", "octocat")
    assert other.username == "octocat-2"
    assert github_client.get("/api/auth/me").json() == {"username": "octocat"}


def test_a_bad_code_does_not_sign_in(configured, monkeypatch):
    fake = FakeGitHub(token_answer={"error": "bad_verification_code"})
    monkeypatch.setattr(github, "fetch_json", fake)
    client = TestClient(app)
    response = come_back(client, code="stale", state=leave_for_github(client)["state"])
    assert response.headers["location"] == "http://localhost:3000/?signin=failed&with=github"
    assert client.get("/api/auth/me").status_code == 401
    assert [request["url"] for request in fake.requests] == [github.TOKEN_URL]


def test_a_profile_without_an_id_does_not_sign_in(configured, monkeypatch):
    fake = FakeGitHub(user_id=None)
    monkeypatch.setattr(github, "fetch_json", fake)
    client = TestClient(app)
    response = come_back(client, code="c", state=leave_for_github(client)["state"])
    assert response.headers["location"].endswith("?signin=failed&with=github")


def test_cancelling_at_github_says_so(configured):
    client = TestClient(app)
    leave_for_github(client)
    response = come_back(client, error="access_denied")
    assert response.headers["location"] == "http://localhost:3000/?signin=cancelled&with=github"


def test_a_google_sign_in_cannot_be_finished_at_github(configured, fake_github, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "google-client")
    monkeypatch.setattr(settings, "google_client_secret", "google-secret")
    client = TestClient(app)
    started = client.get("/api/auth/google/start", follow_redirects=False)
    google_state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
    client.cookies.set(state_cookie("github"), google_state, path="/api/auth/github")

    response = come_back(client, code="c", state=google_state)
    assert response.headers["location"].endswith("?signin=failed&with=github")
    assert fake_github.requests == []
    assert google.AUTHORIZE_URL in started.headers["location"]


def test_an_unknown_provider_is_not_found():
    client = TestClient(app)
    assert client.get("/api/auth/myspace/start", follow_redirects=False).status_code == 404
    response = come_back(client, provider="myspace", code="c", state="s")
    assert response.headers["location"] == "http://localhost:3000/?signin=failed"
