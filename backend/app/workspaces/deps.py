"""Who may touch a workspace. Every workspace route goes through one of these.

    AnyMember  read routes: any member, any role
    Editor     write routes: owners and members; viewers get 403
    Owner      settings and team routes: owners only
"""
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.auth.deps import CurrentUser
from app.db.models import Membership
from app.db.session import Db

EDIT_ROLES = frozenset({"owner", "member"})


def get_membership(workspace_id: uuid.UUID, user: CurrentUser, db: Db) -> Membership:
    """The caller's membership. 404 (not 403) for outsiders, so ids don't leak."""
    membership = db.get(Membership, (workspace_id, user.id))
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    return membership


def require_editor(membership: Annotated[Membership, Depends(get_membership)]) -> Membership:
    """Viewers can never change anything; this is the server-side check that enforces it."""
    if membership.role not in EDIT_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Viewers can't make changes")
    return membership


def require_owner(membership: Annotated[Membership, Depends(get_membership)]) -> Membership:
    if membership.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only workspace owners can change these settings")
    return membership


AnyMember = Annotated[Membership, Depends(get_membership)]
Editor = Annotated[Membership, Depends(require_editor)]
Owner = Annotated[Membership, Depends(require_owner)]
