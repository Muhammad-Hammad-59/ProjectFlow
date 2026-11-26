"""Database engine and session dependencies."""
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine)


def get_engine() -> Engine:
    return engine


def get_db() -> Iterator[Session]:
    """One session per request. Closing it rolls back anything not committed."""
    with SessionLocal() as session:
        yield session


# Use in route signatures: `def route(db: Db): ...`
Db = Annotated[Session, Depends(get_db)]
