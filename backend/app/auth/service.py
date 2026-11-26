"""Sign-up, login and refresh-token rotation."""
import ipaddress
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import security
from app.auth.schemas import LoginIn, SignupIn
from app.config import get_settings
from app.db.errors import flush_or_conflict
from app.db.models import RefreshToken, User

INVALID_LOGIN = "Invalid email or password"


class RefreshRejected(Exception):
    """The refresh cookie is missing, unknown, expired or revoked. The router clears it."""


class RefreshRaced(Exception):
    """The token was rotated a moment ago by another tab. The cookie is still good: keep it."""


def _clean_ip(ip: str | None) -> str | None:
    try:
        return str(ipaddress.ip_address(ip)) if ip else None
    except ValueError:
        return None


# ---------- sign-up and login ----------

def signup(db: Session, data: SignupIn) -> User:
    user = User(email=data.email, full_name=data.full_name, password_hash=security.hash_password(data.password))
    db.add(user)
    flush_or_conflict(db, {"users_email_key": "Email already registered"})
    return user


def authenticate(db: Session, data: LoginIn) -> User:
    user = db.scalar(select(User).where(User.email == data.email))
    if user is None:
        security.verify_password(data.password, security.DUMMY_HASH)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_LOGIN)
    valid, new_hash = security.verify_password(data.password, user.password_hash)
    if not valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_LOGIN)
    if new_hash:
        user.password_hash = new_hash
    user.last_login_at = datetime.now(UTC)
    return user


# ---------- refresh tokens ----------

def issue_refresh(
    db: Session, user_id: uuid.UUID, *, family_id: uuid.UUID | None = None,
    user_agent: str | None = None, ip: str | None = None,
) -> tuple[RefreshToken, str]:
    """Create a refresh-token row. Returns (row, raw token for the cookie)."""
    raw, token_hash = security.new_secret_token()
    row = RefreshToken(
        user_id=user_id,
        family_id=family_id or uuid.uuid4(),
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_days),
        user_agent=(user_agent or None) and user_agent[:500],
        ip_address=_clean_ip(ip),
    )
    db.add(row)
    db.flush()
    return row, raw


def revoke_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


def rotate_refresh(
    db: Session, raw: str | None, *, user_agent: str | None = None, ip: str | None = None,
) -> tuple[User, str]:
    """Swap a valid refresh token for a new one in the same family. Returns (user, new raw token).

    A revoked token presented again is treated as stolen and revokes the whole family.
    The exception is a token rotated within the grace window: that is another tab
    refreshing at the same moment, so raise RefreshRaced and leave everything alone.
    """
    if not raw:
        raise RefreshRejected
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == security.hash_token(raw)).with_for_update()
    )
    if row is None:
        raise RefreshRejected
    now = datetime.now(UTC)
    if row.revoked_at is not None:
        grace = timedelta(seconds=get_settings().refresh_reuse_grace_seconds)
        if row.replaced_by is not None and now - row.revoked_at < grace:
            raise RefreshRaced
        revoke_family(db, row.family_id)
        # Commit here (not in the router) because the router rolls back on RefreshRejected,
        # and the revocation must stick.
        db.commit()
        raise RefreshRejected
    if row.expires_at <= now:
        raise RefreshRejected
    user = db.get(User, row.user_id)
    if user is None:
        raise RefreshRejected

    new_row, new_raw = issue_refresh(db, user.id, family_id=row.family_id, user_agent=user_agent, ip=ip)
    row.revoked_at = now
    row.replaced_by = new_row.id
    return user, new_raw


def logout(db: Session, raw: str | None) -> None:
    if not raw:
        return
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == security.hash_token(raw)))
    if row is not None:
        revoke_family(db, row.family_id)
