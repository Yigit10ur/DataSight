"""What signing in with Google and with GitHub have in common.

Both are OAuth's authorization code flow: the browser is sent to the provider with
a state that ties the answer to this browser and a PKCE challenge that only this
server can redeem the code with, and the code is then traded for a token directly
with the provider, server to server.
"""

import base64
import hashlib
import json
import secrets
import urllib.error
import urllib.request
from dataclasses import dataclass


class SignInError(Exception):
    """A provider's answer could not be trusted or used. Never shown in detail."""


@dataclass(frozen=True)
class SignInStart:
    url: str
    state: str
    verifier: str
    # Checked inside Google's ID token; GitHub has no such token, and leaves it empty.
    nonce: str


@dataclass(frozen=True)
class ExternalIdentity:
    # The provider's own, permanent ID for the account. Names and addresses change.
    subject: str
    # What to base a new account's username on.
    name_hint: str


def new_state() -> str:
    return secrets.token_urlsafe(32)


def pkce_pair() -> tuple[str, str]:
    """A verifier kept here and the challenge, its hash, that goes to the provider."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge.rstrip(b"=").decode()


def fetch_json(url: str, *, data: bytes | None = None, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            answer = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        raise SignInError(f"{url} could not be reached or read: {error}") from error
    if not isinstance(answer, dict):
        raise SignInError(f"{url} answered with something other than an object.")
    return answer
