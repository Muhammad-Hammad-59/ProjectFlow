"""FastAPI app: wires every feature router together. Run with `uv run fastapi dev app/main.py`.

Every router uses an `/api/...` prefix because the Next.js proxy forwards `/api/*` unchanged.
"""
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.auth.router import router as auth_router
from app.db.session import get_engine
from app.team.router import public as invitations_router
from app.team.router import router as team_router
from app.workspaces.router import router as workspaces_router

app = FastAPI(title="ProjectFlow")
app.include_router(auth_router)
app.include_router(workspaces_router)
app.include_router(team_router)
app.include_router(invitations_router)


@app.get("/health")
def health(engine: Annotated[Engine, Depends(get_engine)]):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "error", "database": "unreachable"})
    return {"status": "ok", "database": "ok"}
