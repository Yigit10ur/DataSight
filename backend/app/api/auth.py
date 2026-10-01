import secrets
from dataclasses import dataclass
from types import ModuleType
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.accounts import (
    Account,
    AccountError,
    SignInError,
    UsernameTaken,
    account_store,
    github,
    google,
)
from app.config import settings

SESSION_COOKIE = "datasight_session"

router = APIRouter()


class Credentials(BaseModel):
    # Generous bounds that only stop absurd input; the account rules are checked
    # by the store, which can say what is wrong in words.
    username: str = Field(max_length=64)
    password: str = Field(max_length=1024)


class Me(BaseModel):
    username: str


class Options(BaseModel):
    google: bool
    github: bool


@dataclass(frozen=True)
class Provider:
    name: str
    # The module that speaks to it, with begin() and finish().
    flow: ModuleType
    client_id: str
    client_secret: str
    redirect_uri: str


def provider(name: str) -> Provider | None:
    """A provider that can be signed in with, or None if unknown or not set up."""
    if name == "google":
        found = Provider(
            "google", google, settings.google_client_id, settings.google_client_secret,
            settings.google_redirect_uri,
        )
    elif name == "github":
        found = Provider(
            "github", github, settings.github_client_id, settings.github_client_secret,
            settings.github_redirect_uri,
        )
    else:
        return None
    return found if found.client_id and found.client_secret else None


def state_cookie(name: str) -> str:
    """Holds a sign-in's state between leaving for the provider and coming back,
    which ties the answer to the browser that asked for it."""
    return f"datasight_{name}_state"


def current_account(
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> Account:
    account = account_store.account_for(session) if session else None
    if account is None:
        raise HTTPException(status_code=401, detail="Log in to continue.")
    return account


@router.post("/signup", response_model=Me, status_code=201)
def sign_up(credentials: Credentials, response: Response) -> Me:
    try:
        account = account_store.sign_up(credentials.username, credentials.password)
    except UsernameTaken as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except AccountError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    _start_session(response, account)
    return Me(username=account.username)


@router.post("/login", response_model=Me)
def log_in(credentials: Credentials, response: Response) -> Me:
    try:
        account = account_store.log_in(credentials.username, credentials.password)
    except AccountError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    _start_session(response, account)
    return Me(username=account.username)


@router.post("/logout", status_code=204)
def log_out(
    response: Response,
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> None:
    if session:
        account_store.end_session(session)
    response.delete_cookie(
        SESSION_COOKIE, path="/", secure=settings.secure_cookies, httponly=True, samesite="lax"
    )


@router.get("/options", response_model=Options)
def options() -> Options:
    """Which ways of signing in this server offers, besides a username and password."""
    return Options(google=provider("google") is not None, github=provider("github") is not None)


@router.get("/{name}/start")
def external_start(name: str) -> RedirectResponse:
    """Send the browser to Google or GitHub to sign in."""
    found = provider(name)
    if found is None:
        raise HTTPException(status_code=404, detail="That way of signing in is not set up.")
    start = found.flow.begin(found.client_id, found.redirect_uri)
    account_store.begin_sign_in(found.name, start.state, start.verifier, start.nonce)
    response = RedirectResponse(start.url, status_code=302)
    response.set_cookie(
        state_cookie(found.name),
        start.state,
        max_age=600,
        path=f"/api/auth/{found.name}",
        secure=settings.secure_cookies,
        httponly=True,
        # Lax still sends it on the provider's redirect back, a top-level navigation.
        samesite="lax",
    )
    return response


@router.get("/{name}/callback")
def external_callback(
    name: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Finish signing in and send the browser back to the app, signed in or not.

    Whatever goes wrong, the reader lands on the app with a short reason in the
    address, never on a page of JSON from the API.
    """
    found = provider(name)
    if found is None:
        return _back_to_app(None, "failed")
    if error == "access_denied":
        return _back_to_app(found.name, "cancelled")
    expected_state = request.cookies.get(state_cookie(found.name))
    if not (code and state and expected_state):
        return _back_to_app(found.name, "failed")
    # The state must be the one this browser was given, and still be on record
    # for this same provider.
    if not secrets.compare_digest(state, expected_state):
        return _back_to_app(found.name, "failed")
    attempt = account_store.finish_sign_in(found.name, state)
    if attempt is None:
        return _back_to_app(found.name, "failed")
    verifier, nonce = attempt

    try:
        identity = found.flow.finish(
            code, verifier, nonce, found.client_id, found.client_secret, found.redirect_uri
        )
        account = account_store.account_for_identity(
            found.name, identity.subject, identity.name_hint
        )
    except (SignInError, AccountError):
        return _back_to_app(found.name, "failed")

    response = _back_to_app(found.name, None)
    _start_session(response, account)
    return response


@router.get("/me", response_model=Me)
def me(account: Account = Depends(current_account)) -> Me:
    return Me(username=account.username)


def _back_to_app(name: str | None, problem: str | None) -> RedirectResponse:
    """The app's page, with what went wrong and with which provider, if anything did."""
    query = {"signin": problem, **({"with": name} if name else {})}
    url = settings.app_url + (f"/?{urlencode(query)}" if problem else "/")
    response = RedirectResponse(url, status_code=302)
    if name:
        response.delete_cookie(
            state_cookie(name), path=f"/api/auth/{name}", secure=settings.secure_cookies,
            httponly=True, samesite="lax",
        )
    return response


def _start_session(response: Response, account: Account) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        account_store.start_session(account),
        max_age=settings.session_ttl_seconds,
        path="/",
        secure=settings.secure_cookies,
        # Out of reach of page scripts, and not sent on requests other sites start.
        httponly=True,
        samesite="lax",
    )
