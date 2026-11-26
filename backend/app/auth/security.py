"""Password hashing, access tokens (JWT) and refresh tokens (opaque, hashed at rest)."""
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.config import get_settings

ALGORITHM = "HS256"

_hasher = PasswordHash((Argon2Hasher(),))

# Checked when the email is unknown, so a missing user costs the same time as a wrong password.
DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> tuple[bool, str | None]:
    """Return (valid, new_hash). new_hash is set when the stored hash should be upgraded."""
    return _hasher.verify_and_update(password, password_hash)


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=get_settings().access_token_minutes),
    }
    return jwt.encode(claims, get_settings().jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID | None:
    """Return the user id, or None if the token is invalid, expired or not an access token."""
    try:
        claims = jwt.decode(
            token, get_settings().jwt_secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]}
        )
        if claims.get("type") != "access":
            return None
        return uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None


# ---------- opaque secret tokens (refresh cookies, invite links) ----------
# Only the sha256 hash is stored, so a leaked database can't be replayed. sha256
# (not argon2) is enough because the token itself is 256 random bits.

def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_secret_token() -> tuple[str, str]:
    """Return (raw token to hand out once, hash to store)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)
