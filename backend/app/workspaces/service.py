"""Workspace creation, calendar settings and holidays.

Every change writes an activity_log row in the same transaction; the router commits.
"""
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.activity import log_activity
from app.db.errors import flush_or_conflict
from app.db.models import Holiday, Membership, User, Workspace
from app.workspaces.schemas import HolidayIn, WorkspaceCreate, WorkspaceOut, WorkspaceUpdate

SLUG_TAKEN = {"workspaces_slug_key": "That workspace address is already taken"}


# ---------- workspaces ----------

def to_out(ws: Workspace, role: str) -> WorkspaceOut:
    return WorkspaceOut(id=ws.id, name=ws.name, slug=ws.slug, working_days=list(ws.working_days),
                        hours_per_day=float(ws.hours_per_day), role=role)


def list_for_user(db: Session, user: User) -> list[WorkspaceOut]:
    rows = db.execute(
        select(Workspace, Membership.role)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user.id)
        .order_by(Membership.joined_at)
    ).all()
    return [to_out(ws, role) for ws, role in rows]


def create(db: Session, user: User, data: WorkspaceCreate) -> WorkspaceOut:
    """Create a workspace; the creator becomes its owner."""
    ws = Workspace(name=data.name, slug=data.slug, working_days=data.working_days, created_by=user.id)
    db.add(ws)
    flush_or_conflict(db, SLUG_TAKEN)
    db.add(Membership(workspace_id=ws.id, user_id=user.id, role="owner"))
    log_activity(db, ws.id, user, "workspace", ws.id, "created",
         {"name": ws.name, "slug": ws.slug, "working_days": ws.working_days})
    db.flush()
    return to_out(ws, "owner")


def update(db: Session, user: User, ws: Workspace, data: WorkspaceUpdate) -> WorkspaceOut:
    changes: dict[str, Any] = {}
    for field, new in data.model_dump(exclude_unset=True, exclude_none=True).items():
        old = getattr(ws, field)
        if field == "working_days":
            old = list(old)
        if old != new:
            setattr(ws, field, new)
            changes[field] = {"old": old, "new": new}
    if changes:
        flush_or_conflict(db, SLUG_TAKEN)
        log_activity(db, ws.id, user, "workspace", ws.id, "updated", changes)
        # TODO(scheduling): when projects have calculated dates, recalculate every
        # project in this workspace here if working_days changed.
    return to_out(ws, "owner")


# ---------- holidays ----------

def list_holidays(db: Session, ws_id: uuid.UUID) -> list[Holiday]:
    return list(db.scalars(select(Holiday).where(Holiday.workspace_id == ws_id).order_by(Holiday.holiday_date)))


def add_holiday(db: Session, user: User, ws_id: uuid.UUID, data: HolidayIn) -> Holiday:
    holiday = Holiday(workspace_id=ws_id, holiday_date=data.date, name=data.name)
    db.add(holiday)
    flush_or_conflict(db, {"holidays_one_per_day": f"There is already a holiday on {data.date.isoformat()}"})
    log_activity(db, ws_id, user, "holiday", holiday.id, "created",
         {"date": data.date.isoformat(), "name": data.name})
    # TODO(scheduling): recalculate project dates in this workspace.
    return holiday


def delete_holiday(db: Session, user: User, ws_id: uuid.UUID, holiday_id: uuid.UUID) -> None:
    holiday = db.get(Holiday, holiday_id)
    if holiday is None or holiday.workspace_id != ws_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Holiday not found")
    log_activity(db, ws_id, user, "holiday", holiday.id, "deleted",
         {"date": holiday.holiday_date.isoformat(), "name": holiday.name})
    db.delete(holiday)
    db.flush()
    # TODO(scheduling): recalculate project dates in this workspace.
