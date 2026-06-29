from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.jwt import SessionClaims, create_access_token, encode_access_token
from ..auth.passwords import hash_password, verify_password
from ..auth.reset_tokens import generate_reset_token, hash_reset_token
from ..config import Settings
from ..db.models import AuthSession, PasswordResetToken, User, new_id
from ..api.deps import AuthApiError
from ..api.schemas import (
    AuthenticatedUserResponse,
    LoginResponse,
    PasswordResetAccepted,
    SessionResponse,
)


def users_exist(db: Session) -> bool:
    return db.scalar(select(User.user_id).limit(1)) is not None


def bootstrap_status(db: Session) -> bool:
    return not users_exist(db)


def user_to_authenticated_response(user: User) -> AuthenticatedUserResponse:
    return AuthenticatedUserResponse(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,  # type: ignore[arg-type]
        status=user.status,  # type: ignore[arg-type]
    )


def login_user(
    db: Session,
    *,
    settings: Settings,
    email: str,
    password: str,
) -> LoginResponse:
    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthApiError("invalid_credentials", "Invalid email or password.", 401)
    if user.soft_deleted_at is not None:
        raise AuthApiError("account_deleted", "This account has been disabled.", 403)
    if user.status != "active":
        raise AuthApiError("account_disabled", "This account has been disabled.", 403)

    claims = create_access_token(
        settings=settings,
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        session_version=user.session_version,
    )
    access_token = encode_access_token(settings=settings, claims=claims)
    _record_auth_session(db, user=user, claims=claims, token_identifier=new_id())
    db.commit()

    return LoginResponse(
        access_token=access_token,
        expires_at=claims.expires_at,
        session_version=user.session_version,
        user=user_to_authenticated_response(user),
    )


def session_for_user(user: User, claims: SessionClaims) -> SessionResponse:
    return SessionResponse(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,  # type: ignore[arg-type]
        status=user.status,  # type: ignore[arg-type]
        expires_at=claims.expires_at,
        session_version=user.session_version,
    )


def logout_user(db: Session, *, user: User) -> None:
    _revoke_user_sessions(db, user=user)
    db.commit()


def request_password_reset(db: Session, *, settings: Settings, email: str) -> PasswordResetAccepted:
    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is not None and _user_may_reset_password(user):
        _issue_password_reset_token(db, settings=settings, user=user, requested_email=normalized_email)
        db.commit()
    return PasswordResetAccepted()


def confirm_password_reset(
    db: Session,
    *,
    settings: Settings,
    reset_token: str,
    new_password: str,
) -> None:
    if len(new_password) < settings.password_min_length:
        raise AuthApiError(
            "validation_error",
            f"Password must be at least {settings.password_min_length} characters.",
            422,
        )

    token_hash = hash_reset_token(reset_token)
    record = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    if record is None:
        raise AuthApiError("reset_token_invalid", "Reset token is invalid.", 400)

    now = datetime.now(UTC)
    if record.used_at is not None:
        raise AuthApiError("reset_token_invalid", "Reset token is invalid.", 400)
    if _as_utc(record.expires_at) <= now:
        raise AuthApiError("reset_token_expired", "Reset token has expired.", 400)

    user = db.scalar(select(User).where(User.user_id == record.user_id))
    if user is None or not _user_may_reset_password(user):
        raise AuthApiError("reset_token_invalid", "Reset token is invalid.", 400)

    original_role = user.role
    user.password_hash = hash_password(new_password)
    _revoke_user_sessions(db, user=user)
    record.used_at = now
    db.commit()

    if user.role != original_role:
        raise RuntimeError("password reset must not change user role")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _user_may_reset_password(user: User) -> bool:
    return user.soft_deleted_at is None and user.status == "active"


def _issue_password_reset_token(
    db: Session,
    *,
    settings: Settings,
    user: User,
    requested_email: str,
) -> str:
    now = datetime.now(UTC)
    for existing in db.scalars(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.user_id,
            PasswordResetToken.used_at.is_(None),
        )
    ):
        existing.used_at = now

    plain_token = generate_reset_token()
    db.add(
        PasswordResetToken(
            user_id=user.user_id,
            token_hash=hash_reset_token(plain_token),
            requested_at=now,
            expires_at=now + timedelta(hours=settings.password_reset_token_hours),
            requested_email=requested_email,
        )
    )
    return plain_token


def _revoke_user_sessions(db: Session, *, user: User) -> None:
    user.session_version += 1
    now = datetime.now(UTC)
    for session in user.sessions:
        if session.revoked_at is None:
            session.revoked_at = now


def _record_auth_session(
    db: Session,
    *,
    user: User,
    claims: SessionClaims,
    token_identifier: str,
) -> None:
    db.add(
        AuthSession(
            user_id=user.user_id,
            role=user.role,
            token_identifier=token_identifier,
            issued_at=claims.issued_at,
            expires_at=claims.expires_at,
            revocation_version=user.session_version,
            principal_kind="human",
        )
    )
