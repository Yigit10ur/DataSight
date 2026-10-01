import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.accounts import Account, AccountError, UsernameTaken, account_store, google
from app.config import settings

SESSION_COOKIE = "datasight_session"
# Holds the state of a Google sign-in between leaving for Google and coming back,
# which ties the answer to the browser that asked for it.
GOOGLE_STATE_COOKIE = "datasight_google_state"
GOOGLE_PATHS = "/api/auth/google"

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
    """Which ways of signing in this server offers."""
    return Options(google=_google_configured())


@router.get("/google/start")
def google_start() -> RedirectResponse:
    if not _google_configured():
        raise HTTPException(status_code=404, detail="Signing in with Google is not set up.")
    start = google.begin(settings.google_client_id, settings.google_redirect_uri)
    account_store.begin_sign_in(start.state, start.verifier, start.nonce)
    response = RedirectResponse(start.url, status_code=302)
    response.set_cookie(
        GOOGLE_STATE_COOKIE,
        start.state,
        max_age=600,
        path=GOOGLE_PATHS,
        secure=settings.secure_cookies,
        httponly=True,
        # Lax still sends it on Google's redirect back, a top-level navigation.
        samesite="lax",
    )
    return response


@router.get("/google/callback")
def google_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    expected_state: str | None = Cookie(default=None, alias=GOOGLE_STATE_COOKIE),
) -> RedirectResponse:
    """Finish a Google sign-in and send the browser back to the app, signed in or not.

    Whatever goes wrong, the reader lands on the app with a short reason in the
    address, never on a page of JSON from the API.
    """
    if error == "access_denied":
        return _back_to_app("cancelled")
    if not (_google_configured() and code and state and expected_state):
        return _back_to_app("failed")
    # The state must be the one this browser was given, and still be on record.
    if not secrets.compare_digest(state, expected_state):
        return _back_to_app("failed")
    attempt = account_store.finish_sign_in(state)
    if attempt is None:
        return _back_to_app("failed")
    verifier, nonce = attempt

    try:
        token = google.exchange_code(
            code, verifier, settings.google_client_id, settings.google_client_secret,
            settings.google_redirect_uri,
        )
        identity = google.read_identity(token, settings.google_client_id, nonce)
        account = account_store.account_for_google(identity.subject, identity.email)
    except (google.GoogleSignInError, AccountError):
        return _back_to_app("failed")

    response = _back_to_app(None)
    _start_session(response, account)
    return response


@router.get("/me", response_model=Me)
def me(account: Account = Depends(current_account)) -> Me:
    return Me(username=account.username)


def _google_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def _back_to_app(problem: str | None) -> RedirectResponse:
    url = settings.app_url + (f"/?{urlencode({'signin': problem})}" if problem else "/")
    response = RedirectResponse(url, status_code=302)
    response.delete_cookie(
        GOOGLE_STATE_COOKIE, path=GOOGLE_PATHS, secure=settings.secure_cookies,
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
