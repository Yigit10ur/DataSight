from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.accounts import Account, AccountError, UsernameTaken, account_store
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


@router.get("/me", response_model=Me)
def me(account: Account = Depends(current_account)) -> Me:
    return Me(username=account.username)


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
