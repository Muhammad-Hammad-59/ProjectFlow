"""Turn database constraint errors into clear HTTP errors.

Business rules live in the database (unique slugs, one owner minimum, no loops).
Services flush through `flush_or_conflict` so a broken rule becomes a 409 with a
readable message instead of a 500.
"""
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def flush_or_conflict(db: Session, conflicts: dict[str, str]) -> None:
    """Flush pending changes. If a constraint named in `conflicts` fails, roll back
    and raise 409 with its message. Any other database error is re-raised as is.
    """
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        diag = getattr(e.orig, "diag", None)
        message = conflicts.get(getattr(diag, "constraint_name", None) or "")
        if message is None:
            raise
        raise HTTPException(status.HTTP_409_CONFLICT, message) from None
