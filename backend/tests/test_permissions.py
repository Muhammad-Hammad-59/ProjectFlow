"""The role dependencies in app/workspaces/deps.py, checked directly (no database needed)."""
import uuid

import pytest
from fastapi import HTTPException

from app.db.models import Membership
from app.workspaces.deps import require_editor, require_owner


def membership(role: str) -> Membership:
    return Membership(workspace_id=uuid.uuid4(), user_id=uuid.uuid4(), role=role)


@pytest.mark.parametrize("role", ["owner", "member"])
def test_editor_allows_owners_and_members(role):
    m = membership(role)
    assert require_editor(m) is m


def test_editor_refuses_viewers():
    with pytest.raises(HTTPException) as e:
        require_editor(membership("viewer"))
    assert e.value.status_code == 403


@pytest.mark.parametrize("role", ["member", "viewer"])
def test_owner_refuses_everyone_else(role):
    with pytest.raises(HTTPException) as e:
        require_owner(membership(role))
    assert e.value.status_code == 403
