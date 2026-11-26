import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from app.db.models import ActivityLog, Invitation, Membership, User, Workspace
from app.db.session import SessionLocal
from app.main import app

PASSWORD = "correct-horse-battery"


@dataclass
class Person:
    id: str
    email: str
    headers: dict


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def person(client):
    """Make users; afterwards delete their workspaces first (last-owner trigger), then them."""
    made: list[str] = []

    def _make(name="Sara Khan", email=None) -> Person:
        email = email or f"team-{uuid.uuid4().hex[:10]}@acme-test.com"
        made.append(email)
        r = client.post("/api/auth/signup", json={"email": email, "password": PASSWORD, "full_name": name})
        assert r.status_code == 201
        body = r.json()
        return Person(body["user"]["id"], email, {"Authorization": f"Bearer {body['access_token']}"})

    yield _make
    with SessionLocal() as db:
        ids = list(db.scalars(select(User.id).where(User.email.in_(made))))
        db.execute(delete(Workspace).where(Workspace.created_by.in_(ids)))
        db.execute(delete(User).where(User.id.in_(ids)))
        db.commit()


@pytest.fixture
def team(client, person):
    """An owner with a workspace, plus a member and a viewer who joined by invite."""
    owner = person("Sara Owner")
    ws = client.post("/api/workspaces", json={"name": "Acme", "slug": f"acme-{uuid.uuid4().hex[:8]}"},
                     headers=owner.headers).json()
    people = {"owner": owner}
    for role in ("member", "viewer"):
        p = person(f"{role.title()} Person")
        token = invite(client, ws["id"], owner, p.email, role).json()["token"]
        assert client.post(f"/api/invitations/{token}/accept", headers=p.headers).status_code == 200
        people[role] = p
    return ws["id"], people


def invite(client, ws_id, by: Person, email, role="member"):
    return client.post(f"/api/workspaces/{ws_id}/invitations", json={"email": email, "role": role},
                       headers=by.headers)


# ---------- inviting and joining ----------

def test_invite_preview_and_accept(client, person, team):
    ws_id, p = team
    ali = person("Ali Raza")
    r = invite(client, ws_id, p["owner"], ali.email.upper(), "viewer")
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == ali.email and body["role"] == "viewer" and body["token"]
    assert body["invited_by_name"] == "Sara Owner"

    preview = client.get(f"/api/invitations/{body['token']}").json()  # no login needed
    assert preview["workspace_name"] == "Acme" and preview["inviter_name"] == "Sara Owner"
    assert preview["status"] == "open" and preview["role"] == "viewer"

    joined = client.post(f"/api/invitations/{body['token']}/accept", headers=ali.headers)
    assert joined.status_code == 200
    assert joined.json()["id"] == ws_id and joined.json()["role"] == "viewer"
    assert client.get(f"/api/invitations/{body['token']}").json()["status"] == "accepted"

    # A used link can't be used again.
    assert client.post(f"/api/invitations/{body['token']}/accept", headers=ali.headers).status_code == 410


def test_token_is_stored_hashed(client, person, team):
    ws_id, p = team
    token = invite(client, ws_id, p["owner"], "hash@acme-test.com").json()["token"]
    with SessionLocal() as db:
        stored = db.scalar(select(Invitation.token_hash).where(Invitation.email == "hash@acme-test.com",
                                                               Invitation.workspace_id == uuid.UUID(ws_id)))
    assert stored and stored != token


def test_accept_with_other_email_is_forbidden(client, person, team):
    ws_id, p = team
    token = invite(client, ws_id, p["owner"], "someone-else@acme-test.com").json()["token"]
    r = client.post(f"/api/invitations/{token}/accept", headers=person("Intruder").headers)
    assert r.status_code == 403
    assert r.json()["detail"] == "This invite is for someone-else@acme-test.com"


def test_accept_requires_login(client, team):
    ws_id, p = team
    token = invite(client, ws_id, p["owner"], "x@acme-test.com").json()["token"]
    assert client.post(f"/api/invitations/{token}/accept").status_code == 401


def test_bad_token(client, person):
    assert client.get("/api/invitations/nope").status_code == 404
    assert client.post("/api/invitations/nope/accept", headers=person().headers).status_code == 404


def test_expired_invite(client, person, team):
    ws_id, p = team
    ali = person("Ali")
    body = invite(client, ws_id, p["owner"], ali.email).json()
    with SessionLocal() as db:
        db.execute(update(Invitation).where(Invitation.id == uuid.UUID(body["id"]))
                   .values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        db.commit()
    assert client.get(f"/api/invitations/{body['token']}").json()["status"] == "expired"
    r = client.post(f"/api/invitations/{body['token']}/accept", headers=ali.headers)
    assert r.status_code == 410 and r.json()["detail"] == "This invite link has expired"


def test_reinvite_replaces_old_link(client, person, team):
    ws_id, p = team
    ali = person("Ali")
    old = invite(client, ws_id, p["owner"], ali.email).json()["token"]
    new = invite(client, ws_id, p["owner"], ali.email, "viewer").json()["token"]
    assert client.get(f"/api/invitations/{old}").json()["status"] == "revoked"
    assert client.post(f"/api/invitations/{old}/accept", headers=ali.headers).status_code == 410
    pending = client.get(f"/api/workspaces/{ws_id}/invitations", headers=p["owner"].headers).json()
    assert [i["email"] for i in pending].count(ali.email) == 1
    assert client.post(f"/api/invitations/{new}/accept", headers=ali.headers).json()["role"] == "viewer"


def test_renew_and_revoke(client, person, team):
    ws_id, p = team
    ali = person("Ali")
    first = invite(client, ws_id, p["owner"], ali.email).json()
    renewed = client.post(f"/api/workspaces/{ws_id}/invitations/{first['id']}/renew", headers=p["owner"].headers)
    assert renewed.status_code == 201 and renewed.json()["token"] != first["token"]
    assert client.get(f"/api/invitations/{first['token']}").json()["status"] == "revoked"

    r = client.delete(f"/api/workspaces/{ws_id}/invitations/{renewed.json()['id']}", headers=p["owner"].headers)
    assert r.status_code == 204
    assert client.post(f"/api/invitations/{renewed.json()['token']}/accept", headers=ali.headers).status_code == 410
    assert client.get(f"/api/workspaces/{ws_id}/invitations", headers=p["owner"].headers).json() == []


def test_cannot_invite_existing_member(client, team):
    ws_id, p = team
    r = invite(client, ws_id, p["owner"], p["member"].email)
    assert r.status_code == 409 and r.json()["detail"] == "Member Person is already a member."


@pytest.mark.parametrize("email", ["not-an-email", ""])
def test_invite_invalid_email(client, team, email):
    ws_id, p = team
    assert invite(client, ws_id, p["owner"], email).status_code == 422


# ---------- members ----------

@pytest.mark.parametrize("role", ["owner", "member", "viewer"])
def test_every_member_can_list_members(client, team, role):
    ws_id, p = team
    r = client.get(f"/api/workspaces/{ws_id}/members", headers=p[role].headers)
    assert r.status_code == 200
    assert {m["role"] for m in r.json()} == {"owner", "member", "viewer"}


def test_owner_changes_role_and_it_is_logged(client, team):
    ws_id, p = team
    r = client.patch(f"/api/workspaces/{ws_id}/members/{p['viewer'].id}", json={"role": "member"},
                     headers=p["owner"].headers)
    assert r.status_code == 200 and r.json()["role"] == "member"
    with SessionLocal() as db:
        log = db.scalar(select(ActivityLog).where(ActivityLog.entity_id == uuid.UUID(p["viewer"].id),
                                                  ActivityLog.action == "updated"))
    assert log.changes == {"role": {"old": "viewer", "new": "member"}}


def test_owner_removes_member(client, team):
    ws_id, p = team
    url = f"/api/workspaces/{ws_id}/members/{p['member'].id}"
    assert client.delete(url, headers=p["owner"].headers).status_code == 204
    assert client.get(f"/api/workspaces/{ws_id}", headers=p["member"].headers).status_code == 404


def test_last_owner_cannot_leave_or_be_demoted(client, team):
    ws_id, p = team
    url = f"/api/workspaces/{ws_id}/members/{p['owner'].id}"
    for r in (client.patch(url, json={"role": "member"}, headers=p["owner"].headers),
              client.delete(url, headers=p["owner"].headers)):
        assert r.status_code == 409
        assert r.json()["detail"] == "A workspace must keep at least one owner."
    with SessionLocal() as db:
        assert db.get(Membership, (uuid.UUID(ws_id), uuid.UUID(p["owner"].id))).role == "owner"


def test_owner_can_step_down_when_another_owner_exists(client, team):
    ws_id, p = team
    h = p["owner"].headers
    client.patch(f"/api/workspaces/{ws_id}/members/{p['member'].id}", json={"role": "owner"}, headers=h)
    r = client.patch(f"/api/workspaces/{ws_id}/members/{p['owner'].id}", json={"role": "member"}, headers=h)
    assert r.status_code == 200 and r.json()["role"] == "member"


def test_unknown_member(client, team):
    ws_id, p = team
    url = f"/api/workspaces/{ws_id}/members/{uuid.uuid4()}"
    assert client.patch(url, json={"role": "member"}, headers=p["owner"].headers).status_code == 404


# ---------- role checks on every route ----------

def owner_only_calls(ws_id, target_id, inv_id):
    base = f"/api/workspaces/{ws_id}"
    return [
        ("PATCH", f"{base}/members/{target_id}", {"role": "viewer"}),
        ("DELETE", f"{base}/members/{target_id}", None),
        ("GET", f"{base}/invitations", None),
        ("POST", f"{base}/invitations", {"email": "new@acme-test.com", "role": "member"}),
        ("POST", f"{base}/invitations/{inv_id}/renew", None),
        ("DELETE", f"{base}/invitations/{inv_id}", None),
    ]


@pytest.mark.parametrize("role", ["member", "viewer"])
def test_non_owners_get_403_on_every_owner_route(client, team, role):
    ws_id, p = team
    inv_id = invite(client, ws_id, p["owner"], "pending@acme-test.com").json()["id"]
    for method, url, body in owner_only_calls(ws_id, p["member"].id, inv_id):
        r = client.request(method, url, json=body, headers=p[role].headers)
        assert r.status_code == 403, (method, url, r.status_code)


def test_outsiders_get_404_on_every_workspace_route(client, person, team):
    ws_id, p = team
    outsider = person("Outsider")
    inv_id = invite(client, ws_id, p["owner"], "pending@acme-test.com").json()["id"]
    calls = owner_only_calls(ws_id, p["member"].id, inv_id) + [("GET", f"/api/workspaces/{ws_id}/members", None)]
    for method, url, body in calls:
        r = client.request(method, url, json=body, headers=outsider.headers)
        assert r.status_code == 404, (method, url, r.status_code)


def test_routes_require_login(client, team):
    ws_id, _ = team
    assert client.get(f"/api/workspaces/{ws_id}/members").status_code == 401
    assert client.post(f"/api/workspaces/{ws_id}/invitations", json={"email": "a@b.co"}).status_code == 401
