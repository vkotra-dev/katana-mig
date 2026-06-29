from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import PasswordResetToken, User
from migrations_engine.db.session import SessionLocal

client = TestClient(app)
KNOWN_RESET_TOKEN = "test-reset-token-value"


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _cleanup_password_reset_tokens() -> None:
    settings = get_settings()
    email = settings.bootstrap_admin_email.strip().lower()
    if email:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == email))
            if user is not None:
                for token in db.scalars(
                    select(PasswordResetToken).where(
                        PasswordResetToken.user_id == user.user_id
                    )
                ):
                    db.delete(token)
                db.commit()
    yield


def test_password_reset_request_always_accepts() -> None:
    response = client.post(
        "/auth/password-reset/request",
        json={"email": "missing@example.com"},
    )
    assert response.status_code == 202
    assert response.json() == {"accepted": True}


@patch("migrations_engine.auth.service.generate_reset_token", return_value=KNOWN_RESET_TOKEN)
def test_password_reset_confirm_rotates_password_and_revokes_sessions(_mock_token: object) -> None:
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")

    original_password = settings.bootstrap_admin_password
    new_password = f"{original_password}-rotated"

    login_before = client.post(
        "/auth/login",
        json={
            "email": settings.bootstrap_admin_email,
            "password": original_password,
        },
    )
    assert login_before.status_code == 200
    old_token = login_before.json()["access_token"]
    original_role = login_before.json()["user"]["role"]

    request = client.post(
        "/auth/password-reset/request",
        json={"email": settings.bootstrap_admin_email},
    )
    assert request.status_code == 202

    confirm = client.post(
        "/auth/password-reset/confirm",
        json={"reset_token": KNOWN_RESET_TOKEN, "new_password": new_password},
    )
    assert confirm.status_code == 204, confirm.text

    old_login = client.post(
        "/auth/login",
        json={"email": settings.bootstrap_admin_email, "password": original_password},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/auth/login",
        json={"email": settings.bootstrap_admin_email, "password": new_password},
    )
    assert new_login.status_code == 200
    assert new_login.json()["user"]["role"] == original_role

    session = client.get("/auth/session", headers={"Authorization": f"Bearer {old_token}"})
    assert session.status_code == 401
    assert session.json()["error"]["code"] == "session_revoked"

    reuse = client.post(
        "/auth/password-reset/confirm",
        json={"reset_token": KNOWN_RESET_TOKEN, "new_password": f"{new_password}-again"},
    )
    assert reuse.status_code == 400
    assert reuse.json()["error"]["code"] == "reset_token_invalid"

    with SessionLocal() as db:
        user = db.scalar(
            select(User).where(User.email == settings.bootstrap_admin_email.strip().lower())
        )
        assert user is not None
        user.password_hash = hash_password(original_password)
        db.commit()


@patch("migrations_engine.auth.service.generate_reset_token", return_value=KNOWN_RESET_TOKEN)
def test_password_reset_rejects_short_password(_mock_token: object) -> None:
    settings = get_settings()
    if not settings.bootstrap_admin_email:
        pytest.skip("bootstrap credentials not configured")

    client.post(
        "/auth/password-reset/request",
        json={"email": settings.bootstrap_admin_email},
    )
    response = client.post(
        "/auth/password-reset/confirm",
        json={"reset_token": KNOWN_RESET_TOKEN, "new_password": "short"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
