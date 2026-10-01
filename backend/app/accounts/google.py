"""Signing in with a Google account, through OpenID Connect.

On top of the shared flow, Google is sent a nonce that must come back inside the
ID token, which ties the token to this sign-in.
"""

import base64
import json
import secrets
import time
import urllib.parse

from app.accounts.oauth import (
    ExternalIdentity,
    SignInError,
    SignInStart,
    fetch_json,
    new_state,
    pkce_pair,
)

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = {"https://accounts.google.com", "accounts.google.com"}


def begin(client_id: str, redirect_uri: str) -> SignInStart:
    state, nonce = new_state(), new_state()
    verifier, challenge = pkce_pair()
    query = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        # Lets someone signed in to several Google accounts choose which.
        "prompt": "select_account",
    })
    return SignInStart(f"{AUTHORIZE_URL}?{query}", state, verifier, nonce)


def finish(
    code: str, verifier: str, nonce: str, client_id: str, client_secret: str, redirect_uri: str
) -> ExternalIdentity:
    token = exchange_code(code, verifier, client_id, client_secret, redirect_uri)
    return read_identity(token, client_id, nonce)


def exchange_code(
    code: str, verifier: str, client_id: str, client_secret: str, redirect_uri: str
) -> str:
    """Trade the code from the callback for an ID token."""
    answer = fetch_json(
        TOKEN_URL,
        data=urllib.parse.urlencode({
            "code": code,
            "code_verifier": verifier,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = answer.get("id_token")
    if not isinstance(token, str):
        raise SignInError("Google's answer held no ID token.")
    return token


def read_identity(
    id_token: str, client_id: str, nonce: str, now: float | None = None
) -> ExternalIdentity:
    """Check the token's claims and return whom it names.

    The signature is not checked, which OpenID Connect allows for a token received
    straight from the token endpoint over TLS (Core 1.0, section 3.1.3.7): the
    HTTPS connection to Google is what vouches for it, not a key.
    """
    try:
        payload = id_token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError) as error:
        raise SignInError("The ID token could not be read.") from error

    now = time.time() if now is None else now
    if claims.get("iss") not in ISSUERS:
        raise SignInError("The ID token was not issued by Google.")
    audience = claims.get("aud")
    if audience != client_id and not (isinstance(audience, list) and client_id in audience):
        raise SignInError("The ID token was issued for another application.")
    if not isinstance(claims.get("exp"), (int, float)) or claims["exp"] <= now:
        raise SignInError("The ID token has expired.")
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise SignInError("The ID token answers a different sign-in.")
    if not claims.get("sub") or not claims.get("email") or claims.get("email_verified") is not True:
        raise SignInError("The Google account has no verified email address.")
    return ExternalIdentity(
        subject=str(claims["sub"]), name_hint=str(claims["email"]).split("@")[0]
    )
