from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db.models import User
from ..db.session import SessionLocal
from ..auth.jwt import SessionClaims, TokenValidationError, decode_access_token


class AuthApiError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def get_bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise AuthApiError("unauthenticated", "Authentication is required.", 401)
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthApiError("unauthenticated", "Authentication is required.", 401)
    return token


def get_session_claims(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> SessionClaims:
    token = get_bearer_token(authorization)
    try:
        return decode_access_token(settings=settings, token=token)
    except TokenValidationError as exc:
        raise AuthApiError(exc.code, exc.message, 401) from exc


def get_current_user(
    claims: SessionClaims = Depends(get_session_claims),
    db: Session = Depends(get_db),
) -> User:
    user = db.scalar(select(User).where(User.user_id == claims.user_id))
    if user is None:
        raise AuthApiError("unauthenticated", "Authentication is required.", 401)
    if user.soft_deleted_at is not None:
        raise AuthApiError("account_deleted", "This account has been disabled.", 403)
    if user.status != "active":
        raise AuthApiError("account_disabled", "This account has been disabled.", 403)
    if user.session_version != claims.session_version:
        raise AuthApiError("session_revoked", "Session has been revoked.", 401)
    return user


def get_central_team_user(user: User = Depends(get_current_user)) -> User:
    from ..management.access import require_central_team

    require_central_team(user)
    return user
