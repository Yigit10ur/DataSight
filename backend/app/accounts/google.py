"""Signing in with a Google account, as OpenID Connect's authorization code flow.

The browser is sent to Google with three one-time values: a state that ties the
answer to this browser, a PKCE verifier that only this server can redeem the code
with, and a nonce that must come back inside the ID token. The code is then traded
for that token directly with Google, server to server.
"""

import base64
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = {"https://accounts.google.com", "accounts.google.com"}


class GoogleSignInError(Exception):
    """Google's answer could not be trusted or used. Never shown in detail to a reader."""


@dataclass(frozen=True)
class SignInStart:
    url: str
    state: str
    verifier: str
    nonce: str


@dataclass(frozen=True)
class GoogleIdentity:
    # Google's stable ID for the account; an email address can change.
    subject: str
    email: str


def begin(client_id: str, redirect_uri: str) -> SignInStart:
    state, verifier, nonce = (secrets.token_urlsafe(32) for _ in range(3))
    challenge = _base64url(hashlib.sha256(verifier.encode()).digest())
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


def exchange_code(
    code: str, verifier: str, client_id: str, client_secret: str, redirect_uri: str
) -> str:
    """Trade the code from the callback for an ID token."""
    body = urllib.parse.urlencode({
        "code": code,
        "code_verifier": verifier,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).encode()
    request = urllib.request.Request(
        TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            answer = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        raise GoogleSignInError(f"The code exchange failed: {error}") from error
    token = answer.get("id_token")
    if not isinstance(token, str):
        raise GoogleSignInError("Google's answer held no ID token.")
    return token


def read_identity(
    id_token: str, client_id: str, nonce: str, now: float | None = None
) -> GoogleIdentity:
    """Check the token's claims and return whom it names.

    The signature is not checked, which OpenID Connect allows for a token received
    straight from the token endpoint over TLS (Core 1.0, section 3.1.3.7): the
    HTTPS connection to Google is what vouches for it, not a key.
    """
    try:
        payload = id_token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError) as error:
        raise GoogleSignInError("The ID token could not be read.") from error

    now = time.time() if now is None else now
    if claims.get("iss") not in ISSUERS:
        raise GoogleSignInError("The ID token was not issued by Google.")
    audience = claims.get("aud")
    if audience != client_id and not (isinstance(audience, list) and client_id in audience):
        raise GoogleSignInError("The ID token was issued for another application.")
    if not isinstance(claims.get("exp"), (int, float)) or claims["exp"] <= now:
        raise GoogleSignInError("The ID token has expired.")
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise GoogleSignInError("The ID token answers a different sign-in.")
    if not claims.get("sub") or not claims.get("email") or claims.get("email_verified") is not True:
        raise GoogleSignInError("The Google account has no verified email address.")
    return GoogleIdentity(subject=str(claims["sub"]), email=str(claims["email"]))


def _base64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
