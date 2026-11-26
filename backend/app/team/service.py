"""Members, invitations and joining a workspace.

Invite tokens are random and stored only as a sha256 hash, like refresh tokens,
so a leaked database can't be used to join. The raw token is returned once.
"""
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import security
from app.config import get_settings
from app.db.activity import log_activity
from app.db.errors import flush_or_conflict
from app.db.models import Invitation, Membership, User, Workspace
from app.team.schemas import (
    InvitationCreated,
    InvitationOut,
    InviteIn,
    InvitePreview,
    InviteStatus,
    MemberOut,
)
from app.workspaces import service as workspaces_service
from app.workspaces.schemas import Role, WorkspaceOut

# The keep_one_owner trigger raises with this constraint name when the last owner
# would leave or be demoted.
LAST_OWNER = {"memberships_last_owner": "A workspace must keep at least one owner."}
ALREADY_MEMBER = "You are already a member of this workspace"


# ---------- members ----------

def _member_out(m: Membership, u: User) -> MemberOut:
    return MemberOut(user_id=u.id, full_name=u.full_name, email=u.email, avatar_url=u.avatar_url,
                     role=m.role, joined_at=m.joined_at)


def list_members(db: Session, ws_id: uuid.UUID) -> list[MemberOut]:
    rows = db.execute(
        select(Membership, User).join(User, User.id == Membership.user_id)
        .where(Membership.workspace_id == ws_id)
        .order_by(Membership.joined_at)
    ).all()
    return [_member_out(m, u) for m, u in rows]


def _membership_or_404(db: Session, ws_id: uuid.UUID, user_id: uuid.UUID) -> Membership:
    m = db.get(Membership, (ws_id, user_id))
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    return m


def change_role(db: Session, actor: User, ws_id: uuid.UUID, user_id: uuid.UUID, role: Role) -> MemberOut:
    m = _membership_or_404(db, ws_id, user_id)
    if m.role != role:
        old = m.role
        m.role = role
        flush_or_conflict(db, LAST_OWNER)
        log_activity(db, ws_id, actor, "membership", user_id, "updated", {"role": {"old": old, "new": role}})
    return _member_out(m, db.get(User, user_id))


def remove_member(db: Session, actor: User, ws_id: uuid.UUID, user_id: uuid.UUID) -> None:
    m = _membership_or_404(db, ws_id, user_id)
    role = m.role
    db.delete(m)
    flush_or_conflict(db, LAST_OWNER)
    # Tasks they owned become unassigned (tasks_owner_fkey is ON DELETE SET NULL).
    log_activity(db, ws_id, actor, "membership", user_id, "deleted", {"role": role})


# ---------- invitations (owner side) ----------

def _status(inv: Invitation, now: datetime) -> InviteStatus:
    if inv.accepted_at is not None:
        return "accepted"
    if inv.revoked_at is not None:
        return "revoked"
    if inv.expires_at <= now:
        return "expired"
    return "open"


def _inviter_names(db: Session, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {uid: name for uid, name in db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))}


def _to_out(inv: Invitation, inviter_name: str | None) -> InvitationOut:
    return InvitationOut(id=inv.id, email=inv.email, role=inv.role, invited_by_name=inviter_name,
                         created_at=inv.created_at, expires_at=inv.expires_at)


def list_invitations(db: Session, ws_id: uuid.UUID) -> list[InvitationOut]:
    """Invites not yet accepted or revoked, including expired ones (so they can be renewed)."""
    invs = list(db.scalars(
        select(Invitation)
        .where(Invitation.workspace_id == ws_id, Invitation.accepted_at.is_(None),
               Invitation.revoked_at.is_(None))
        .order_by(Invitation.created_at.desc())
    ))
    names = _inviter_names(db, {i.invited_by for i in invs})
    return [_to_out(i, names.get(i.invited_by)) for i in invs]


def _revoke_open_for_email(db: Session, ws_id: uuid.UUID, email: str) -> None:
    db.execute(
        update(Invitation)
        .where(Invitation.workspace_id == ws_id, Invitation.email == email,
               Invitation.accepted_at.is_(None), Invitation.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


def _issue(db: Session, actor: User, ws_id: uuid.UUID, email: str, role: str) -> InvitationCreated:
    raw, token_hash = security.new_secret_token()
    inv = Invitation(
        workspace_id=ws_id, email=email, role=role, token_hash=token_hash, invited_by=actor.id,
        expires_at=datetime.now(UTC) + timedelta(days=get_settings().invite_days),
    )
    db.add(inv)
    db.flush()
    db.refresh(inv)
    log_activity(db, ws_id, actor, "invitation", inv.id, "created", {"email": email, "role": role})
    return InvitationCreated(**_to_out(inv, actor.full_name).model_dump(), token=raw)


def create_invitation(db: Session, actor: User, ws_id: uuid.UUID, data: InviteIn) -> InvitationCreated:
    """Make a new link. An older open link for the same email stops working."""
    existing = db.execute(
        select(User.full_name).join(Membership, Membership.user_id == User.id)
        .where(Membership.workspace_id == ws_id, User.email == data.email)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{existing} is already a member.")
    _revoke_open_for_email(db, ws_id, data.email)
    return _issue(db, actor, ws_id, data.email, data.role)


def _pending_or_404(db: Session, ws_id: uuid.UUID, inv_id: uuid.UUID) -> Invitation:
    inv = db.get(Invitation, inv_id)
    if inv is None or inv.workspace_id != ws_id or inv.accepted_at or inv.revoked_at:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    return inv


def renew_invitation(db: Session, actor: User, ws_id: uuid.UUID, inv_id: uuid.UUID) -> InvitationCreated:
    """Replace a lost or expired link: the old one is revoked, a new one is issued."""
    inv = _pending_or_404(db, ws_id, inv_id)
    inv.revoked_at = datetime.now(UTC)
    log_activity(db, ws_id, actor, "invitation", inv.id, "deleted", {"reason": "renewed"})
    db.flush()
    return _issue(db, actor, ws_id, inv.email, inv.role)


def revoke_invitation(db: Session, actor: User, ws_id: uuid.UUID, inv_id: uuid.UUID) -> None:
    inv = _pending_or_404(db, ws_id, inv_id)
    inv.revoked_at = datetime.now(UTC)
    log_activity(db, ws_id, actor, "invitation", inv.id, "deleted", {"reason": "revoked", "email": inv.email})


# ---------- joining (invitee side) ----------

def _by_token(db: Session, token: str, *, lock: bool = False) -> Invitation:
    query = select(Invitation).where(Invitation.token_hash == security.hash_token(token))
    inv = db.scalar(query.with_for_update() if lock else query)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This invite link is not valid")
    return inv


def preview(db: Session, token: str) -> InvitePreview:
    inv = _by_token(db, token)
    ws = db.get(Workspace, inv.workspace_id)
    inviter = db.get(User, inv.invited_by) if inv.invited_by else None
    return InvitePreview(
        workspace_id=ws.id, workspace_name=ws.name, inviter_name=inviter.full_name if inviter else None,
        email=inv.email, role=inv.role, status=_status(inv, datetime.now(UTC)), expires_at=inv.expires_at,
    )


def accept(db: Session, user: User, token: str) -> WorkspaceOut:
    inv = _by_token(db, token, lock=True)
    now = datetime.now(UTC)
    match _status(inv, now):
        case "expired":
            raise HTTPException(status.HTTP_410_GONE, "This invite link has expired")
        case "revoked" | "accepted":
            raise HTTPException(status.HTTP_410_GONE, "This invite link is no longer valid")
    if user.email.lower() != inv.email.lower():
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"This invite is for {inv.email}")
    if db.get(Membership, (inv.workspace_id, user.id)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, ALREADY_MEMBER)

    db.add(Membership(workspace_id=inv.workspace_id, user_id=user.id, role=inv.role))
    inv.accepted_at = now
    inv.accepted_by = user.id
    log_activity(db, inv.workspace_id, user, "membership", user.id, "created",
                 {"role": inv.role, "invitation_id": str(inv.id)})
    # The check above can lose a race with a second invite accepted at the same moment.
    flush_or_conflict(db, {"memberships_pkey": ALREADY_MEMBER})
    return workspaces_service.to_out(db.get(Workspace, inv.workspace_id), inv.role)
