import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.models import ActivityLog, Membership, User, Workspace
from app.db.session import SessionLocal
from app.main import app

PASSWORD = "correct-horse-battery"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user(client):
    """Sign up users; returns auth headers. Cleans up workspaces first (last-owner trigger), then users."""
    emails: list[str] = []

    def _make(name="Sara Khan"):
        email = f"ws-{uuid.uuid4().hex[:10]}@acme-test.com"
        emails.append(email)
        r = client.post("/api/auth/signup", json={"email": email, "password": PASSWORD, "full_name": name})
        assert r.status_code == 201
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    yield _make
    with SessionLocal() as db:
        user_ids = list(db.scalars(select(User.id).where(User.email.in_(emails))))
        db.execute(delete(Workspace).where(Workspace.created_by.in_(user_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def slug():
    return f"acme-{uuid.uuid4().hex[:8]}"


def create_ws(client, headers, **overrides):
    body = {"name": "Acme Studio", "slug": slug(), **overrides}
    return client.post("/api/workspaces", json=body, headers=headers)


def join(client, ws_id, role, make_user):
    """Add a new user to the workspace directly (invites are not built yet)."""
    headers = make_user("Other Person")
    me = client.get("/api/auth/me", headers=headers).json()
    with SessionLocal() as db:
        db.add(Membership(workspace_id=uuid.UUID(ws_id), user_id=uuid.UUID(me["id"]), role=role))
        db.commit()
    return headers


# ---------- create ----------

def test_create_makes_caller_owner_and_logs(client, make_user):
    h = make_user()
    r = create_ws(client, h, name="  Acme Studio ", working_days=[5, 1, 3, 3])
    assert r.status_code == 201
    ws = r.json()
    assert ws["name"] == "Acme Studio"
    assert ws["role"] == "owner"
    assert ws["working_days"] == [1, 3, 5]  # sorted, duplicates removed
    assert ws["hours_per_day"] == 8

    assert [w["id"] for w in client.get("/api/workspaces", headers=h).json()] == [ws["id"]]
    with SessionLocal() as db:
        log = db.scalar(select(ActivityLog).where(ActivityLog.entity_id == uuid.UUID(ws["id"])))
    assert log.action == "created" and log.entity_type == "workspace"


def test_create_defaults_to_monday_to_friday(client, make_user):
    assert create_ws(client, make_user()).json()["working_days"] == [1, 2, 3, 4, 5]


def test_create_duplicate_slug_conflicts(client, make_user):
    h = make_user()
    s = slug()
    assert create_ws(client, h, slug=s).status_code == 201
    r = create_ws(client, h, slug=s)
    assert r.status_code == 409
    assert r.json()["detail"] == "That workspace address is already taken"


@pytest.mark.parametrize("override", [
    {"name": "   "},
    {"slug": "Has Spaces"},
    {"slug": "-leading-dash"},
    {"working_days": []},
    {"working_days": [0]},
    {"working_days": [8]},
])
def test_create_invalid_input(client, make_user, override):
    assert create_ws(client, make_user(), **override).status_code == 422


def test_create_requires_login(client):
    assert client.post("/api/workspaces", json={"name": "A", "slug": slug()}).status_code == 401


# ---------- read ----------

def test_outsider_gets_404(client, make_user):
    ws = create_ws(client, make_user()).json()
    outsider = make_user("Outsider")
    assert client.get(f"/api/workspaces/{ws['id']}", headers=outsider).status_code == 404
    assert client.get(f"/api/workspaces/{ws['id']}/holidays", headers=outsider).status_code == 404
    assert client.get("/api/workspaces", headers=outsider).json() == []


def test_member_and_viewer_can_read(client, make_user):
    ws = create_ws(client, make_user()).json()
    for role in ("member", "viewer"):
        h = join(client, ws["id"], role, make_user)
        r = client.get(f"/api/workspaces/{ws['id']}", headers=h)
        assert r.status_code == 200 and r.json()["role"] == role
        assert client.get(f"/api/workspaces/{ws['id']}/holidays", headers=h).status_code == 200


# ---------- update settings ----------

def test_owner_updates_working_days_and_logs_change(client, make_user):
    h = make_user()
    ws = create_ws(client, h).json()
    r = client.patch(f"/api/workspaces/{ws['id']}", json={"working_days": [7, 1, 2, 3, 4]}, headers=h)
    assert r.status_code == 200
    assert r.json()["working_days"] == [1, 2, 3, 4, 7]
    with SessionLocal() as db:
        log = db.scalar(select(ActivityLog).where(
            ActivityLog.entity_id == uuid.UUID(ws["id"]), ActivityLog.action == "updated"))
    assert log.changes == {"working_days": {"old": [1, 2, 3, 4, 5], "new": [1, 2, 3, 4, 7]}}


def test_update_without_changes_writes_no_log(client, make_user):
    h = make_user()
    ws = create_ws(client, h).json()
    assert client.patch(f"/api/workspaces/{ws['id']}", json={"name": "Acme Studio"}, headers=h).status_code == 200
    with SessionLocal() as db:
        count = len(db.scalars(select(ActivityLog).where(
            ActivityLog.entity_id == uuid.UUID(ws["id"]), ActivityLog.action == "updated")).all())
    assert count == 0


def test_update_slug_conflict(client, make_user):
    h = make_user()
    taken = create_ws(client, h).json()["slug"]
    ws = create_ws(client, h).json()
    assert client.patch(f"/api/workspaces/{ws['id']}", json={"slug": taken}, headers=h).status_code == 409


def test_update_rejects_empty_working_days(client, make_user):
    h = make_user()
    ws = create_ws(client, h).json()
    assert client.patch(f"/api/workspaces/{ws['id']}", json={"working_days": []}, headers=h).status_code == 422


@pytest.mark.parametrize("role", ["member", "viewer"])
def test_non_owners_cannot_change_settings(client, make_user, role):
    ws = create_ws(client, make_user()).json()
    h = join(client, ws["id"], role, make_user)
    url = f"/api/workspaces/{ws['id']}"
    assert client.patch(url, json={"working_days": [1]}, headers=h).status_code == 403
    assert client.post(f"{url}/holidays", json={"date": "2026-12-25", "name": "Christmas"},
                       headers=h).status_code == 403


# ---------- holidays ----------

def test_holiday_add_list_delete(client, make_user):
    h = make_user()
    ws = create_ws(client, h).json()
    url = f"/api/workspaces/{ws['id']}/holidays"

    xmas = client.post(url, json={"date": "2026-12-25", "name": "Christmas"}, headers=h)
    assert xmas.status_code == 201
    client.post(url, json={"date": "2026-01-01", "name": "New Year"}, headers=h)

    listed = client.get(url, headers=h).json()
    assert [(x["date"], x["name"]) for x in listed] == [("2026-01-01", "New Year"), ("2026-12-25", "Christmas")]

    assert client.delete(f"{url}/{xmas.json()['id']}", headers=h).status_code == 204
    assert [x["name"] for x in client.get(url, headers=h).json()] == ["New Year"]

    with SessionLocal() as db:
        actions = list(db.scalars(select(ActivityLog.action).where(
            ActivityLog.entity_id == uuid.UUID(xmas.json()["id"])).order_by(ActivityLog.id)))
    assert actions == ["created", "deleted"]


def test_holiday_same_day_conflicts(client, make_user):
    h = make_user()
    ws = create_ws(client, h).json()
    url = f"/api/workspaces/{ws['id']}/holidays"
    client.post(url, json={"date": "2026-12-25", "name": "Christmas"}, headers=h)
    r = client.post(url, json={"date": "2026-12-25", "name": "Again"}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"] == "There is already a holiday on 2026-12-25"


def test_holiday_invalid_input(client, make_user):
    h = make_user()
    ws = create_ws(client, h).json()
    url = f"/api/workspaces/{ws['id']}/holidays"
    assert client.post(url, json={"date": "not-a-date", "name": "X"}, headers=h).status_code == 422
    assert client.post(url, json={"date": "2026-12-25", "name": " "}, headers=h).status_code == 422


def test_cannot_delete_holiday_of_another_workspace(client, make_user):
    h = make_user()
    a = create_ws(client, h).json()
    b = create_ws(client, h).json()
    hol = client.post(f"/api/workspaces/{a['id']}/holidays",
                      json={"date": "2026-12-25", "name": "Christmas"}, headers=h).json()
    assert client.delete(f"/api/workspaces/{b['id']}/holidays/{hol['id']}", headers=h).status_code == 404
