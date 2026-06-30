from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from migrations_engine.app import app, _validate_runtime_settings
from migrations_engine.auth.jwt import create_access_token, decode_access_token, encode_access_token
from migrations_engine.config import get_settings
from migrations_engine.db.models import User
from migrations_engine.db.session import SessionLocal

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def test_bootstrap_status_reports_not_required() -> None:
    response = client.get("/auth/bootstrap/status")
    assert response.status_code == 200
    assert response.json() == {"bootstrap_required": False}


def test_login_and_session_round_trip() -> None:
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")

    login = client.post(
        "/auth/login",
        json={
            "email": settings.bootstrap_admin_email,
            "password": settings.bootstrap_admin_password,
        },
    )
    assert login.status_code == 200, login.text
    body = login.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "central_team"
    token = body["access_token"]

    session = client.get("/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert session.status_code == 200
    assert session.json()["email"] == settings.bootstrap_admin_email.lower()


def test_invalid_login_is_rejected() -> None:
    response = client.post(
        "/auth/login",
        json={"email": "missing@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_logout_revokes_session() -> None:
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")

    login = client.post(
        "/auth/login",
        json={
            "email": settings.bootstrap_admin_email,
            "password": settings.bootstrap_admin_password,
        },
    )
    token = login.json()["access_token"]
    logout = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout.status_code == 204

    session = client.get("/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert session.status_code == 401
    assert session.json()["error"]["code"] == "session_revoked"


def test_soft_deleted_user_is_rejected() -> None:
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")

    login = client.post(
        "/auth/login",
        json={
            "email": settings.bootstrap_admin_email,
            "password": settings.bootstrap_admin_password,
        },
    )
    token = login.json()["access_token"]

    with SessionLocal() as db:
        user = db.scalar(
            select(User).where(User.email == settings.bootstrap_admin_email.strip().lower())
        )
        assert user is not None
        user.soft_deleted_at = datetime.now(UTC)
        db.commit()

    try:
        session = client.get("/auth/session", headers={"Authorization": f"Bearer {token}"})
        assert session.status_code == 403
        assert session.json()["error"]["code"] == "account_deleted"
    finally:
        with SessionLocal() as db:
            user = db.scalar(
                select(User).where(User.email == settings.bootstrap_admin_email.strip().lower())
            )
            assert user is not None
            user.soft_deleted_at = None
            db.commit()


def test_production_jwt_secret_guard_blocks_dev_default(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setenv("KATANA_ENV", "production")

    with pytest.raises(RuntimeError, match="Production JWT secret"):
        _validate_runtime_settings(settings)


def test_access_token_round_trip_preserves_jti() -> None:
    settings = get_settings()
    claims = create_access_token(
        settings=settings,
        user_id="user-123",
        email="user@example.com",
        role="central_team",
        session_version=3,
    )
    token = encode_access_token(settings=settings, claims=claims)
    decoded = decode_access_token(settings=settings, token=token)

    assert decoded.jti == claims.jti
    assert decoded.user_id == "user-123"
