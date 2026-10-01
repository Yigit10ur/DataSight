"""Signing in with a GitHub account, through a GitHub OAuth app.

No scopes are asked for: the token can read only the public profile, which holds
everything needed, the account's permanent ID and its username. GitHub has no ID
token, so whom the token belongs to is asked of its API.
"""

import urllib.parse

from app.accounts.oauth import (
    ExternalIdentity,
    SignInError,
    SignInStart,
    fetch_json,
    new_state,
    pkce_pair,
)

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_URL = "https://api.github.com/user"


def begin(client_id: str, redirect_uri: str) -> SignInStart:
    state = new_state()
    verifier, challenge = pkce_pair()
    query = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return SignInStart(f"{AUTHORIZE_URL}?{query}", state, verifier, nonce="")


def finish(
    code: str, verifier: str, nonce: str, client_id: str, client_secret: str, redirect_uri: str
) -> ExternalIdentity:
    token = exchange_code(code, verifier, client_id, client_secret, redirect_uri)
    return fetch_identity(token)


def exchange_code(
    code: str, verifier: str, client_id: str, client_secret: str, redirect_uri: str
) -> str:
    """Trade the code from the callback for an access token."""
    answer = fetch_json(
        TOKEN_URL,
        data=urllib.parse.urlencode({
            "code": code,
            "code_verifier": verifier,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }).encode(),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            # Otherwise GitHub answers in form encoding.
            "Accept": "application/json",
        },
    )
    token = answer.get("access_token")
    if not isinstance(token, str):
        # GitHub reports a bad code with a 200 and an "error" field, not a status.
        raise SignInError(f"GitHub gave no access token: {answer.get('error', 'no reason')}.")
    return token


def fetch_identity(token: str) -> ExternalIdentity:
    profile = fetch_json(
        USER_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            # GitHub's API refuses requests without one.
            "User-Agent": "DataSight",
        },
    )
    subject, login = profile.get("id"), profile.get("login")
    if not isinstance(subject, int) or not isinstance(login, str) or not login:
        raise SignInError("GitHub's profile answer held no account ID or username.")
    return ExternalIdentity(subject=str(subject), name_hint=login)
