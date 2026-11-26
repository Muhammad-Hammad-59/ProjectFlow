import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.auth.router import REFRESH_COOKIE
from app.auth.security import ALGORITHM, hash_token
from app.config import get_settings
from app.db.models import RefreshToken, User
from app.db.session import SessionLocal
from app.main import app

PASSWORD = "correct-horse-battery"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def email():
    addr = f"user-{uuid.uuid4().hex[:10]}@acme-test.com"
    yield addr
    with SessionLocal() as db:
        db.query(User).filter(User.email == addr).delete()
        db.commit()


def signup(client, email, password=PASSWORD, name="Sara Khan"):
    return client.post("/api/auth/signup", json={"email": email, "password": password, "full_name": name})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def use_cookie(client, raw):
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, raw)


def token_row(raw):
    with SessionLocal() as db:
        return db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))


# ---------- signup ----------

def test_signup_logs_in_and_hashes_with_argon2(client, email):
    r = signup(client, email)
    assert r.status_code == 201
    body = r.json()
    assert body["token_type"] == "bearer" and body["access_token"]
    assert body["user"]["email"] == email and body["user"]["full_name"] == "Sara Khan"
    assert "password_hash" not in body["user"]

    set_cookie = r.headers["set-cookie"]
    assert f"{REFRESH_COOKIE}=" in set_cookie and "HttpOnly" in set_cookie and "Path=/" in set_cookie
    with SessionLocal() as db:
        stored = db.scalar(select(User.password_hash).where(User.email == email))
    assert stored.startswith("$argon2id$")


def test_signup_duplicate_email_any_case(client, email):
    assert signup(client, email).status_code == 201
    r = signup(client, email.upper())
    assert r.status_code == 409
    assert r.json()["detail"] == "Email already registered"


@pytest.mark.parametrize("payload", [
    {"email": "a@acme-test.com", "password": "short", "full_name": "A"},
    {"email": "not-an-email", "password": PASSWORD, "full_name": "A"},
    {"email": "a@acme-test.com", "password": PASSWORD, "full_name": "   "},
])
def test_signup_invalid_input(client, payload):
    assert client.post("/api/auth/signup", json=payload).status_code == 422


# ---------- login ----------

def test_login_ok(client, email):
    signup(client, email)
    client.cookies.clear()
    r = client.post("/api/auth/login", json={"email": email.upper(), "password": PASSWORD})
    assert r.status_code == 200
    assert client.cookies.get(REFRESH_COOKIE)
    assert client.get("/api/auth/me", headers=bearer(r.json()["access_token"])).json()["email"] == email


def test_login_wrong_password_and_unknown_email_look_the_same(client, email):
    signup(client, email)
    wrong = client.post("/api/auth/login", json={"email": email, "password": "wrong-password"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@acme-test.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Invalid email or password"}


# ---------- me ----------

def test_me_requires_valid_token(client, email):
    token = signup(client, email).json()["access_token"]
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=bearer("garbage")).status_code == 401

    user_id = jwt.decode(token, options={"verify_signature": False})["sub"]
    past = datetime.now(UTC) - timedelta(minutes=1)
    expired = jwt.encode({"sub": user_id, "type": "access", "iat": past, "exp": past},
                         get_settings().jwt_secret, algorithm=ALGORITHM)
    r = client.get("/api/auth/me", headers=bearer(expired))
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


# ---------- refresh ----------

def test_refresh_rotates(client, email):
    signup(client, email)
    old = client.cookies.get(REFRESH_COOKIE)
    r = client.post("/api/auth/refresh")
    assert r.status_code == 200
    new = client.cookies.get(REFRESH_COOKIE)
    assert new and new != old
    assert client.get("/api/auth/me", headers=bearer(r.json()["access_token"])).status_code == 200

    old_row, new_row = token_row(old), token_row(new)
    assert old_row.revoked_at is not None and old_row.replaced_by == new_row.id
    assert new_row.family_id == old_row.family_id and new_row.revoked_at is None


def test_refresh_without_cookie(client):
    assert client.post("/api/auth/refresh").status_code == 401


def test_reused_token_within_grace_does_not_revoke_family(client, email):
    """Two tabs refreshing at once: the slower one gets 409 and must NOT clear the cookie,
    or it would delete the new cookie the faster tab just received."""
    signup(client, email)
    old = client.cookies.get(REFRESH_COOKIE)
    client.post("/api/auth/refresh")
    new = client.cookies.get(REFRESH_COOKIE)

    use_cookie(client, old)
    r = client.post("/api/auth/refresh")
    assert r.status_code == 409
    assert "set-cookie" not in r.headers
    assert token_row(new).revoked_at is None


def test_reused_token_after_grace_revokes_family(client, email):
    signup(client, email)
    old = client.cookies.get(REFRESH_COOKIE)
    client.post("/api/auth/refresh")
    new = client.cookies.get(REFRESH_COOKIE)
    with SessionLocal() as db:
        db.execute(update(RefreshToken).where(RefreshToken.token_hash == hash_token(old))
                   .values(revoked_at=datetime.now(UTC) - timedelta(minutes=5)))
        db.commit()

    use_cookie(client, old)
    r = client.post("/api/auth/refresh")
    assert r.status_code == 401
    assert f'{REFRESH_COOKIE}=""' in r.headers["set-cookie"]  # cookie cleared
    assert token_row(new).revoked_at is not None

    use_cookie(client, new)
    assert client.post("/api/auth/refresh").status_code == 401


def test_expired_refresh_token_rejected(client, email):
    signup(client, email)
    raw = client.cookies.get(REFRESH_COOKIE)
    with SessionLocal() as db:
        db.execute(update(RefreshToken).where(RefreshToken.token_hash == hash_token(raw))
                   .values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        db.commit()
    assert client.post("/api/auth/refresh").status_code == 401


# ---------- logout ----------

def test_logout_revokes_refresh(client, email):
    access = signup(client, email).json()["access_token"]
    raw = client.cookies.get(REFRESH_COOKIE)
    r = client.post("/api/auth/logout")
    assert r.status_code == 204
    assert f'{REFRESH_COOKIE}=""' in r.headers["set-cookie"]
    assert token_row(raw).revoked_at is not None

    use_cookie(client, raw)
    assert client.post("/api/auth/refresh").status_code == 401
    # The short-lived access token keeps working until it expires.
    assert client.get("/api/auth/me", headers=bearer(access)).status_code == 200


def test_logout_without_cookie_is_fine(client):
    assert client.post("/api/auth/logout").status_code == 204
