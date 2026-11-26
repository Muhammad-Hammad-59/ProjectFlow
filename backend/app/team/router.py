"""Team routes. Workspace routes check the role via app.workspaces.deps;
the public preview only answers to a secret invite token."""
import uuid

from fastapi import APIRouter, status

from app.auth.deps import CurrentUser
from app.db.session import Db
from app.team import service
from app.team.schemas import (
    InvitationCreated,
    InvitationOut,
    InviteIn,
    InvitePreview,
    MemberOut,
    RoleIn,
)
from app.workspaces.deps import AnyMember, Owner
from app.workspaces.schemas import WorkspaceOut

router = APIRouter(prefix="/api/workspaces/{workspace_id}", tags=["team"])
public = APIRouter(prefix="/api/invitations", tags=["team"])


@router.get("/members")
def list_members(membership: AnyMember, db: Db) -> list[MemberOut]:
    return service.list_members(db, membership.workspace_id)


@router.patch("/members/{user_id}")
def change_role(user_id: uuid.UUID, data: RoleIn, owner: Owner, user: CurrentUser, db: Db) -> MemberOut:
    out = service.change_role(db, user, owner.workspace_id, user_id, data.role)
    db.commit()
    return out


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(user_id: uuid.UUID, owner: Owner, user: CurrentUser, db: Db) -> None:
    service.remove_member(db, user, owner.workspace_id, user_id)
    db.commit()


@router.get("/invitations")
def list_invitations(owner: Owner, db: Db) -> list[InvitationOut]:
    return service.list_invitations(db, owner.workspace_id)


@router.post("/invitations", status_code=status.HTTP_201_CREATED)
def create_invitation(data: InviteIn, owner: Owner, user: CurrentUser, db: Db) -> InvitationCreated:
    out = service.create_invitation(db, user, owner.workspace_id, data)
    db.commit()
    return out


@router.post("/invitations/{invitation_id}/renew", status_code=status.HTTP_201_CREATED)
def renew_invitation(invitation_id: uuid.UUID, owner: Owner, user: CurrentUser, db: Db) -> InvitationCreated:
    out = service.renew_invitation(db, user, owner.workspace_id, invitation_id)
    db.commit()
    return out


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(invitation_id: uuid.UUID, owner: Owner, user: CurrentUser, db: Db) -> None:
    service.revoke_invitation(db, user, owner.workspace_id, invitation_id)
    db.commit()


@public.get("/{token}")
def preview_invitation(token: str, db: Db) -> InvitePreview:
    """Public on purpose: the person opening the link may not have an account yet."""
    return service.preview(db, token)


@public.post("/{token}/accept")
def accept_invitation(token: str, user: CurrentUser, db: Db) -> WorkspaceOut:
    out = service.accept(db, user, token)
    db.commit()
    return out
