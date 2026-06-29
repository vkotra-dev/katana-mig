from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ..auth.jwt import SessionClaims
from ..auth.service import (
    bootstrap_status,
    confirm_password_reset,
    login_user,
    logout_user,
    request_password_reset,
    session_for_user,
)
from ..config import Settings, get_settings
from ..db.models import User
from ..api.deps import get_current_user, get_db, get_session_claims
from ..api.schemas import (
    BootstrapStatusResponse,
    LoginRequest,
    LoginResponse,
    PasswordResetAccepted,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    SessionResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/bootstrap/status", response_model=BootstrapStatusResponse)
def get_bootstrap_status(db: Session = Depends(get_db)) -> BootstrapStatusResponse:
    return BootstrapStatusResponse(bootstrap_required=bootstrap_status(db))


@router.post("/login", response_model=LoginResponse)
def post_login(
    body: LoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    return login_user(
        db,
        settings=settings,
        email=str(body.email),
        password=body.password,
    )


@router.get("/session", response_model=SessionResponse)
def get_session(
    user: User = Depends(get_current_user),
    claims: SessionClaims = Depends(get_session_claims),
) -> SessionResponse:
    return session_for_user(user, claims)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def post_logout(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    logout_user(db, user=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/password-reset/request",
    response_model=PasswordResetAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_password_reset_request(
    body: PasswordResetRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PasswordResetAccepted:
    return request_password_reset(db, settings=settings, email=str(body.email))


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def post_password_reset_confirm(
    body: PasswordResetConfirmRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    confirm_password_reset(
        db,
        settings=settings,
        reset_token=body.reset_token,
        new_password=body.new_password,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
