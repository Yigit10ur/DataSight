import hashlib
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Callable, Iterator

from app.accounts.passwords import DECOY_HASH, hash_password, verify_password

USERNAME = re.compile(r"[A-Za-z0-9_.-]{3,32}")
MIN_PASSWORD = 8
# Long enough for any passphrase, short enough that hashing one is not a burden.
MAX_PASSWORD = 256

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_by_expiry ON sessions(expires_at);
CREATE TABLE IF NOT EXISTS sign_in_attempts (
    state_hash TEXT PRIMARY KEY,
    verifier TEXT NOT NULL,
    nonce TEXT NOT NULL,
    expires_at REAL NOT NULL
);
"""

# How long someone has to finish signing in at Google once they have left for it.
SIGN_IN_ATTEMPT_SECONDS = 600


class AccountError(Exception):
    """A sign-up or log-in that cannot go ahead, worded for the person trying."""


class UsernameTaken(AccountError):
    pass


@dataclass(frozen=True)
class Account:
    id: str
    username: str


class AccountStore:
    """Accounts and their sessions, kept in SQLite so they outlive a restart.

    A session token is handed to the browser once and only its hash is stored, so
    a copy of the database does not let anyone sign in as anyone.
    """

    def __init__(
        self,
        path: Callable[[], Path],
        session_ttl: Callable[[], float],
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        # Read on use rather than at construction, so tests and settings can point
        # the store elsewhere without rebuilding it.
        self._path = path
        self._session_ttl = session_ttl
        self._clock = clock
        self._ready: set[Path] = set()
        self._schema_lock = Lock()

    def sign_up(self, username: str, password: str) -> Account:
        if not USERNAME.fullmatch(username):
            raise AccountError(
                "Usernames are 3 to 32 characters: letters, digits, and . _ - only."
            )
        if len(password) < MIN_PASSWORD:
            raise AccountError(f"Passwords need at least {MIN_PASSWORD} characters.")
        if len(password) > MAX_PASSWORD:
            raise AccountError(f"Passwords can be at most {MAX_PASSWORD} characters.")

        account = Account(id=uuid.uuid4().hex, username=username)
        try:
            with self._connection() as connection:
                connection.execute(
                    "INSERT INTO users (id, username, password_hash, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (account.id, username, hash_password(password), self._clock()),
                )
        except sqlite3.IntegrityError as error:
            raise UsernameTaken("That username is taken.") from error
        return account

    def log_in(self, username: str, password: str) -> Account:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        stored = row["password_hash"] if row else DECOY_HASH
        matches = len(password) <= MAX_PASSWORD and verify_password(password, stored)
        if row is None or not matches:
            raise AccountError("Wrong username or password.")
        return Account(id=row["id"], username=row["username"])

    def start_session(self, account: Account) -> str:
        token = secrets.token_urlsafe(32)
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                (_digest(token), account.id, self._clock() + self._session_ttl()),
            )
        return token

    def account_for(self, token: str) -> Account | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT users.id, users.username FROM sessions "
                "JOIN users ON users.id = sessions.user_id "
                "WHERE sessions.token_hash = ? AND sessions.expires_at > ?",
                (_digest(token), self._clock()),
            ).fetchone()
        return Account(id=row["id"], username=row["username"]) if row else None

    def end_session(self, token: str) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (_digest(token),))

    def purge_expired_sessions(self) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (self._clock(),))
            connection.execute(
                "DELETE FROM sign_in_attempts WHERE expires_at <= ?", (self._clock(),)
            )

    def begin_sign_in(self, state: str, verifier: str, nonce: str) -> None:
        """Remember a Google sign-in in progress until its callback arrives."""
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO sign_in_attempts (state_hash, verifier, nonce, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (_digest(state), verifier, nonce, self._clock() + SIGN_IN_ATTEMPT_SECONDS),
            )

    def finish_sign_in(self, state: str) -> tuple[str, str] | None:
        """The verifier and nonce for a sign-in, usable once and only before it expires."""
        with self._connection() as connection:
            row = connection.execute(
                "DELETE FROM sign_in_attempts WHERE state_hash = ? RETURNING verifier, nonce, "
                "expires_at",
                (_digest(state),),
            ).fetchone()
        if row is None or row["expires_at"] <= self._clock():
            return None
        return row["verifier"], row["nonce"]

    def account_for_google(self, subject: str, email: str) -> Account:
        """The account for this Google identity, created on its first sign-in.

        A Google identity is matched by Google's own ID for it, never by email: an
        address can change hands, and a password account has no address to match.
        Its username comes from the address and gets a number if already taken.
        """
        existing = self._google_account(subject)
        if existing is not None:
            return existing
        base = google_username(email)
        for attempt in range(1, 100):
            username = base if attempt == 1 else f"{base}-{attempt}"
            account = Account(id=uuid.uuid4().hex, username=username)
            try:
                with self._connection() as connection:
                    # No password: password_hash is empty, which no password matches.
                    connection.execute(
                        "INSERT INTO users (id, username, password_hash, created_at, google_sub) "
                        "VALUES (?, ?, '', ?, ?)",
                        (account.id, username, self._clock(), subject),
                    )
                return account
            except sqlite3.IntegrityError:
                # Either the name is taken, or this same identity signed in twice at
                # once and the other attempt created the account first.
                existing = self._google_account(subject)
                if existing is not None:
                    return existing
        raise AccountError("No username could be found for this Google account.")

    def _google_account(self, subject: str) -> Account | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT id, username FROM users WHERE google_sub = ?", (subject,)
            ).fetchone()
        return Account(id=row["id"], username=row["username"]) if row else None

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """One connection per call, committed on success. SQLite opens in microseconds."""
        path = self._path()
        with closing(sqlite3.connect(path, timeout=10)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            self._ensure_schema(path, connection)
            with connection:
                yield connection

    def _ensure_schema(self, path: Path, connection: sqlite3.Connection) -> None:
        with self._schema_lock:
            if path not in self._ready:
                connection.executescript(SCHEMA)
                # Added after the first release: a database made before it gains the
                # column here rather than needing to be recreated.
                columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
                if "google_sub" not in columns:
                    connection.execute("ALTER TABLE users ADD COLUMN google_sub TEXT")
                connection.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS users_by_google ON users(google_sub)"
                )
                self._ready.add(path)


def google_username(email: str) -> str:
    """A username from the part of an address before the @, made to fit the rules."""
    name = re.sub(r"[^A-Za-z0-9_.-]", "", email.split("@")[0])[:28]
    return name if len(name) >= 3 else f"user-{name}" if name else "user"


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
