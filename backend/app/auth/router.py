"""Auth routes: sign up, log in, refresh, log out, and "who am I".

The access token goes back in the JSON body (the client keeps it in memory);
the refresh token only ever travels in the httpOnly `pf_refresh` cookie.
"""
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.deps import CurrentUser
from app.auth.schemas import LoginIn, SignupIn, TokenOut, UserOut
from app.auth.security import create_access_token
from app.config import get_settings
from app.db.models import User
from app.db.session import Db

REFRESH_COOKIE = "pf_refresh"

router = APIRouter(prefix="/api/auth", tags=["auth"])

RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _set_refresh_cookie(response: Response, raw: str) -> None:
    s = get_settings()
    response.set_cookie(
        REFRESH_COOKIE, raw,
        max_age=s.refresh_token_days * 24 * 3600,
        httponly=True, secure=s.cookie_secure, samesite="lax", path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(REFRESH_COOKIE, httponly=True, secure=s.cookie_secure, samesite="lax", path="/")


def _client(request: Request) -> dict:
    return {"user_agent": request.headers.get("user-agent"), "ip": request.client.host if request.client else None}


def _token_out(user: User) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user.id),
        expires_in=get_settings().access_token_minutes * 60,
        user=UserOut.model_validate(user),
    )


def _start_session(db: Session, user: User, request: Request, response: Response) -> TokenOut:
    _, raw = service.issue_refresh(db, user.id, **_client(request))
    db.commit()
    _set_refresh_cookie(response, raw)
    return _token_out(user)


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(data: SignupIn, request: Request, response: Response, db: Db) -> TokenOut:
    user = service.signup(db, data)
    return _start_session(db, user, request, response)


@router.post("/login")
def login(data: LoginIn, request: Request, response: Response, db: Db) -> TokenOut:
    user = service.authenticate(db, data)
    return _start_session(db, user, request, response)


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Db, pf_refresh: RefreshCookie = None) -> TokenOut:
    try:
        user, raw = service.rotate_refresh(db, pf_refresh, **_client(request))
    except service.RefreshRaced:
        # Another tab just rotated this token and its response carries the new cookie.
        # Don't clear the cookie here, or this response would delete that new one.
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Refresh already in progress") from None
    except service.RefreshRejected:
        db.rollback()
        clear = Response()
        _clear_refresh_cookie(clear)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Session expired",
            headers={"set-cookie": clear.headers["set-cookie"]},
        ) from None
    db.commit()
    _set_refresh_cookie(response, raw)
    return _token_out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, db: Db, pf_refresh: RefreshCookie = None) -> None:
    service.logout(db, pf_refresh)
    db.commit()
    _clear_refresh_cookie(response)


@router.get("/me")
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
