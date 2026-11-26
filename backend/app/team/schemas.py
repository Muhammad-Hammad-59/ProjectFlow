"""Request and response models for members and invitations."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.auth.schemas import Email
from app.workspaces.schemas import Role

InviteStatus = Literal["open", "expired", "revoked", "accepted"]


class MemberOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    avatar_url: str | None
    role: Role
    joined_at: datetime


class RoleIn(BaseModel):
    role: Role


class InviteIn(BaseModel):
    email: Email
    role: Role = "member"


class InvitationOut(BaseModel):
    id: uuid.UUID
    email: str
    role: Role
    invited_by_name: str | None
    created_at: datetime
    expires_at: datetime


class InvitationCreated(InvitationOut):
    """Returned only when a link is made. The raw token is never stored, so it can't be shown again."""

    token: str


class InvitePreview(BaseModel):
    """What the public /invite/{token} page shows before anyone logs in."""

    workspace_id: uuid.UUID
    workspace_name: str
    inviter_name: str | None
    email: str
    role: Role
    status: InviteStatus
    expires_at: datetime
