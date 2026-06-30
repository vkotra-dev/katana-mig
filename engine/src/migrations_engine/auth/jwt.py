from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from ..config import Settings


@dataclass(frozen=True)
class SessionClaims:
    jti: str
    user_id: str
    email: str
    role: str
    session_version: int
    expires_at: datetime
    issued_at: datetime


def create_access_token(
    *,
    settings: Settings,
    user_id: str,
    email: str,
    role: str,
    session_version: int,
) -> SessionClaims:
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(hours=settings.jwt_access_token_hours)
    return SessionClaims(
        jti=uuid4().hex,
        user_id=user_id,
        email=email,
        role=role,
        session_version=session_version,
        expires_at=expires_at,
        issued_at=issued_at,
    )


def encode_access_token(*, settings: Settings, claims: SessionClaims) -> str:
    payload = {
        "sub": claims.user_id,
        "jti": claims.jti,
        "email": claims.email,
        "role": claims.role,
        "sv": claims.session_version,
        "iat": int(claims.issued_at.timestamp()),
        "exp": int(claims.expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(*, settings: Settings, token: str) -> SessionClaims:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise TokenValidationError("session_expired", "Session has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenValidationError("unauthenticated", "Authentication is required.") from exc

    sub = payload.get("sub")
    jti = payload.get("jti")
    email = payload.get("email")
    role = payload.get("role")
    session_version = payload.get("sv")
    if not (
        isinstance(sub, str)
        and isinstance(jti, str)
        and isinstance(email, str)
        and isinstance(role, str)
    ):
        raise TokenValidationError("unauthenticated", "Authentication is required.")
    if not isinstance(session_version, int):
        raise TokenValidationError("unauthenticated", "Authentication is required.")

    exp = payload.get("exp")
    iat = payload.get("iat")
    if not isinstance(exp, (int, float)) or not isinstance(iat, (int, float)):
        raise TokenValidationError("unauthenticated", "Authentication is required.")

    return SessionClaims(
        jti=jti,
        user_id=sub,
        email=email,
        role=role,
        session_version=session_version,
        expires_at=datetime.fromtimestamp(exp, tz=UTC),
        issued_at=datetime.fromtimestamp(iat, tz=UTC),
    )


class TokenValidationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
