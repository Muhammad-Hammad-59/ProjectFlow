"""Workspace routes: create and list workspaces, calendar settings, holidays.

Reads need any membership (AnyMember); settings and holidays are owner-only (Owner).
"""
import uuid

from fastapi import APIRouter, status

from app.auth.deps import CurrentUser
from app.db.models import Workspace
from app.db.session import Db
from app.workspaces import service
from app.workspaces.deps import AnyMember, Owner
from app.workspaces.schemas import (
    HolidayIn,
    HolidayOut,
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceUpdate,
)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.get("")
def list_workspaces(user: CurrentUser, db: Db) -> list[WorkspaceOut]:
    """Workspaces the caller belongs to, with their role in each."""
    return service.list_for_user(db, user)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_workspace(data: WorkspaceCreate, user: CurrentUser, db: Db) -> WorkspaceOut:
    """Any logged-in user may create a workspace; they become its owner."""
    out = service.create(db, user, data)
    db.commit()
    return out


@router.get("/{workspace_id}")
def get_workspace(membership: AnyMember, db: Db) -> WorkspaceOut:
    return service.to_out(db.get(Workspace, membership.workspace_id), membership.role)


@router.patch("/{workspace_id}")
def update_workspace(data: WorkspaceUpdate, owner: Owner, user: CurrentUser, db: Db) -> WorkspaceOut:
    out = service.update(db, user, db.get(Workspace, owner.workspace_id), data)
    db.commit()
    return out


@router.get("/{workspace_id}/holidays")
def list_holidays(membership: AnyMember, db: Db) -> list[HolidayOut]:
    return [HolidayOut.model_validate(h) for h in service.list_holidays(db, membership.workspace_id)]


@router.post("/{workspace_id}/holidays", status_code=status.HTTP_201_CREATED)
def add_holiday(data: HolidayIn, owner: Owner, user: CurrentUser, db: Db) -> HolidayOut:
    holiday = service.add_holiday(db, user, owner.workspace_id, data)
    db.commit()
    return HolidayOut.model_validate(holiday)


@router.delete("/{workspace_id}/holidays/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holiday(holiday_id: uuid.UUID, owner: Owner, user: CurrentUser, db: Db) -> None:
    service.delete_holiday(db, user, owner.workspace_id, holiday_id)
    db.commit()
