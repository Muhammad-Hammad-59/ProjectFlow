"""One way to write the activity log, so every feature records changes the same way."""
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ActivityLog, User


def log_activity(
    db: Session, workspace_id: uuid.UUID, actor: User, entity: str, entity_id: uuid.UUID,
    action: str, changes: dict[str, Any],
) -> None:
    """Add an append-only row in the caller's transaction (the router commits)."""
    db.add(ActivityLog(workspace_id=workspace_id, actor_id=actor.id, entity_type=entity,
                       entity_id=entity_id, action=action, changes=changes))
