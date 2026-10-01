import base64
import hashlib
import hmac
import secrets

# scrypt from the standard library, at the cost OWASP suggests for it: about 16 MB
# and a few tens of milliseconds per hash, slow enough to make guessing expensive.
COST, BLOCK_SIZE, PARALLELISM = 2**14, 8, 1
KEY_BYTES = 32
SALT_BYTES = 16


def hash_password(password: str) -> str:
    """A salted hash that records its own parameters, so they can be raised later."""
    salt = secrets.token_bytes(SALT_BYTES)
    key = _derive(password, salt, COST, BLOCK_SIZE, PARALLELISM)
    return "$".join(
        ["scrypt", str(COST), str(BLOCK_SIZE), str(PARALLELISM), _encode(salt), _encode(key)]
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, cost, block_size, parallelism, salt, key = stored.split("$")
        if scheme != "scrypt":
            return False
        derived = _derive(
            password, _decode(salt), int(cost), int(block_size), int(parallelism)
        )
    except ValueError:
        return False
    return hmac.compare_digest(derived, _decode(key))


def _derive(password: str, salt: bytes, cost: int, block_size: int, parallelism: int) -> bytes:
    return hashlib.scrypt(
        password.encode(), salt=salt, n=cost, r=block_size, p=parallelism,
        maxmem=64 * 1024 * 1024, dklen=KEY_BYTES,
    )


def _encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def _decode(text: str) -> bytes:
    return base64.b64decode(text, validate=True)


# Checked against when a username does not exist, so a wrong username takes as
# long to refuse as a wrong password and the timing does not reveal which it was.
DECOY_HASH = hash_password(secrets.token_urlsafe(16))
