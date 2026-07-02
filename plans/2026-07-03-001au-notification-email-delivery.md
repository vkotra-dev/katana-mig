# Notification Email Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Task:** [`tasks/001au-notification-email-delivery.md`](../tasks/001au-notification-email-delivery.md)  
**Domain:** [`docs/domain/ui.md`](../docs/domain/ui.md), [`docs/domain/security.md`](../docs/domain/security.md)

**Goal:** Replace the `send_notification_email` logging stub with real SMTP delivery while keeping notification persistence authoritative and email delivery best-effort.

**Architecture:** `send_notification_email` is upgraded in-place in `management/notifications.py` — it reads SMTP config from `get_settings()`, builds a plain-text `EmailMessage`, and sends via stdlib `smtplib.SMTP`. An empty `smtp_host` skips sending silently (dev default). All SMTP exceptions are caught and logged without re-raising so notification writes in `create_notification` are never blocked. Config gains six new `KATANA_SMTP_*` env vars following the existing `pydantic_settings` + `KATANA_` prefix pattern. `smtp_password` is added to the existing URL-decode validator.

**Tech Stack:** Python stdlib `smtplib` + `email.message.EmailMessage`; `pydantic_settings.BaseSettings`; `pytest` + `unittest.mock.patch` for tests

## Global Constraints

- Keep the `Notification` model, routes, and `create_notification` signature from `001at-notifications` unchanged
- Do not add a queue, provider abstraction, HTML templates, or retry logic
- Do not add email preferences or unsubscribe support
- SMTP credentials must never appear in logs, exceptions, or API responses
- Email delivery remains best-effort — any exception in `send_notification_email` must not block the notification row write
- 001at must be complete before executing this plan (`management/notifications.py` must already exist with the logging stub)

---

## File Changes

| Action | Path |
|--------|------|
| Modify | `engine/src/migrations_engine/config.py` |
| Modify | `engine/src/migrations_engine/management/notifications.py` |
| Create | `engine/tests/test_notifications_email.py` |
| Modify | `docs/domain/ui.md` |
| Modify | `docs/domain/security.md` |

---

## Task 1: Extend config with SMTP settings

**Files:**
- Modify: `engine/src/migrations_engine/config.py`

**Interfaces:**
- Produces: `Settings.smtp_host: str`, `Settings.smtp_port: int`, `Settings.smtp_username: str`, `Settings.smtp_password: str`, `Settings.smtp_from_address: str`, `Settings.smtp_use_tls: bool`

- [ ] **Step 1: Read the current config file**

Read `engine/src/migrations_engine/config.py` to confirm the exact current content before editing.

- [ ] **Step 2: Add SMTP fields and extend the password validator**

In `engine/src/migrations_engine/config.py`, add six new fields after `cors_origins` and add `"smtp_password"` to the existing `decode_password` field_validator:

```python
# After cors_origins line:
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = ""
    smtp_use_tls: bool = True
```

Change the validator decorator from:
```python
    @field_validator("mysql_password", "bootstrap_admin_password", mode="before")
```
to:
```python
    @field_validator("mysql_password", "bootstrap_admin_password", "smtp_password", mode="before")
```

- [ ] **Step 3: Verify import still works**

Run: `cd engine && python -c "from src.migrations_engine.config import get_settings; s = get_settings(); print(s.smtp_host)"`
Expected: prints an empty string (no error)

- [ ] **Step 4: Commit**

```bash
git add engine/src/migrations_engine/config.py
git commit -m "feat(001au): add smtp settings to engine config"
```

---

## Task 2: Replace the email stub with real SMTP delivery

**Files:**
- Modify: `engine/src/migrations_engine/management/notifications.py`

**Interfaces:**
- Consumes: `Settings.smtp_host`, `Settings.smtp_port`, `Settings.smtp_username`, `Settings.smtp_password`, `Settings.smtp_from_address`, `Settings.smtp_use_tls` (from Task 1)
- Produces: `send_notification_email(user_email: str, event_type: str, deep_link: str | None) -> None` — unchanged signature, real SMTP behaviour

- [ ] **Step 1: Read the current notifications.py**

Read `engine/src/migrations_engine/management/notifications.py` to confirm the current stub content.

- [ ] **Step 2: Replace `send_notification_email` with SMTP implementation**

Replace the stub body entirely. The new imports needed at top of file (add alongside existing imports):

```python
import smtplib
from email.message import EmailMessage

from ..config import get_settings
```

Replace the `send_notification_email` function body:

```python
def send_notification_email(user_email: str, event_type: str, deep_link: str | None) -> None:
    s = get_settings()
    if not s.smtp_host:
        logger.debug(
            "SMTP not configured; skipping notification email to %s for event %s",
            user_email,
            event_type,
        )
        return

    msg = EmailMessage()
    msg["Subject"] = f"[Katana] {event_type.replace('_', ' ').title()}"
    msg["From"] = s.smtp_from_address
    msg["To"] = user_email
    body_lines = [f"Event: {event_type}"]
    if deep_link:
        body_lines.append(f"View: {deep_link}")
    msg.set_content("\n".join(body_lines))

    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port) as smtp:
            if s.smtp_use_tls:
                smtp.starttls()
            if s.smtp_username:
                smtp.login(s.smtp_username, s.smtp_password)
            smtp.send_message(msg)
        logger.info(
            "Notification email sent: to=%s event_type=%s",
            user_email,
            event_type,
        )
    except Exception:
        logger.exception(
            "Failed to send notification email to %s for event %s",
            user_email,
            event_type,
        )
```

Note: `logger.exception` logs the traceback but not the SMTP credentials — they never appear in the log call.

- [ ] **Step 3: Verify the module imports cleanly**

Run: `cd engine && python -c "from src.migrations_engine.management.notifications import send_notification_email; print('ok')"`
Expected: prints `ok` with no error

- [ ] **Step 4: Commit**

```bash
git add engine/src/migrations_engine/management/notifications.py
git commit -m "feat(001au): replace email stub with smtp delivery"
```

---

## Task 3: Tests for SMTP send path

**Files:**
- Create: `engine/tests/test_notifications_email.py`

**Interfaces:**
- Consumes: `send_notification_email` (Task 2), `create_notification` (from 001at), `Settings` (Task 1), inline SQLite test pattern used by other engine test files

- [ ] **Step 1: Write the test file**

Create `engine/tests/test_notifications_email.py`:

```python
from __future__ import annotations

import smtplib
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Patch db_session before importing app modules
from migrations_engine.db import session as db_session

_sqlite_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
db_session.engine = _sqlite_engine
db_session.SessionLocal = sessionmaker(bind=_sqlite_engine, autocommit=False, autoflush=False)

from migrations_engine.db.models import Base, User  # noqa: E402
from migrations_engine.management.notifications import (  # noqa: E402
    create_notification,
    send_notification_email,
)
from migrations_engine.config import Settings  # noqa: E402
import migrations_engine.management.notifications as notif_module  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _setup_sqlite_db():
    Base.metadata.create_all(bind=_sqlite_engine)
    db = db_session.SessionLocal()
    db.add(User(
        user_id="user-alpha",
        email="alpha@example.com",
        display_name="Alpha",
        hashed_password="x",
        role="central_team",
        disabled=False,
    ))
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=_sqlite_engine)


def _smtp_settings() -> Settings:
    return Settings(
        smtp_host="mail.example.com",
        smtp_port=587,
        smtp_username="smtpuser",
        smtp_password="smtppass",
        smtp_from_address="no-reply@example.com",
        smtp_use_tls=True,
        mysql_host="127.0.0.1",
        mysql_password="",
        bootstrap_admin_email="",
        bootstrap_admin_password="",
        jwt_secret="test-secret",
    )


def _no_smtp_settings() -> Settings:
    return Settings(
        smtp_host="",
        mysql_host="127.0.0.1",
        mysql_password="",
        bootstrap_admin_email="",
        bootstrap_admin_password="",
        jwt_secret="test-secret",
    )


# --- send_notification_email unit tests ---

def test_smtp_configured_sends_message():
    mock_smtp_instance = MagicMock()
    with patch.object(notif_module, "get_settings", return_value=_smtp_settings()), \
         patch("smtplib.SMTP") as MockSMTP:
        MockSMTP.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
        MockSMTP.return_value.__exit__ = MagicMock(return_value=False)
        send_notification_email("alpha@example.com", "gate_1_waiting", "https://app.example.com/project/1")

    MockSMTP.assert_called_once_with("mail.example.com", 587)
    mock_smtp_instance.starttls.assert_called_once()
    mock_smtp_instance.login.assert_called_once_with("smtpuser", "smtppass")
    mock_smtp_instance.send_message.assert_called_once()
    sent_msg = mock_smtp_instance.send_message.call_args[0][0]
    assert sent_msg["To"] == "alpha@example.com"
    assert sent_msg["From"] == "no-reply@example.com"
    assert "gate 1 waiting" in sent_msg["Subject"].lower()
    assert "gate_1_waiting" in sent_msg.get_content()
    assert "https://app.example.com/project/1" in sent_msg.get_content()


def test_smtp_no_deep_link_omits_view_line():
    mock_smtp_instance = MagicMock()
    with patch.object(notif_module, "get_settings", return_value=_smtp_settings()), \
         patch("smtplib.SMTP") as MockSMTP:
        MockSMTP.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
        MockSMTP.return_value.__exit__ = MagicMock(return_value=False)
        send_notification_email("alpha@example.com", "execution_complete", None)

    sent_msg = mock_smtp_instance.send_message.call_args[0][0]
    assert "View:" not in sent_msg.get_content()


def test_smtp_failure_does_not_raise():
    with patch.object(notif_module, "get_settings", return_value=_smtp_settings()), \
         patch("smtplib.SMTP", side_effect=smtplib.SMTPException("connection refused")):
        # Must not raise
        send_notification_email("alpha@example.com", "gate_1_waiting", None)


def test_smtp_not_configured_skips_connection():
    with patch.object(notif_module, "get_settings", return_value=_no_smtp_settings()), \
         patch("smtplib.SMTP") as MockSMTP:
        send_notification_email("alpha@example.com", "gate_1_waiting", None)
    MockSMTP.assert_not_called()


# --- create_notification integration: email failure does not block write ---

def test_create_notification_persists_despite_smtp_failure():
    db = db_session.SessionLocal()
    try:
        with patch.object(notif_module, "get_settings", return_value=_smtp_settings()), \
             patch("smtplib.SMTP", side_effect=smtplib.SMTPException("down")):
            rows = create_notification(
                db,
                project_id="proj-1",
                event_type="gate_1_waiting",
                deep_link=None,
                payload=None,
                recipient_user_ids=["user-alpha"],
            )
        assert len(rows) == 1
        assert rows[0].event_type == "gate_1_waiting"
        assert rows[0].notification_id is not None
    finally:
        db.close()
```

- [ ] **Step 2: Run the new tests to verify they pass**

Run: `cd engine && python -m pytest tests/test_notifications_email.py -v`
Expected: All 5 tests pass. No SMTP connection is made to a real server.

- [ ] **Step 3: Run the existing notifications API tests to verify no regression**

Run: `cd engine && python -m pytest tests/test_notifications_api.py -v`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add engine/tests/test_notifications_email.py
git commit -m "test(001au): cover smtp send path and best-effort delivery"
```

---

## Task 4: Update domain docs

**Files:**
- Modify: `docs/domain/ui.md`
- Modify: `docs/domain/security.md`

**Interfaces:**
- Consumes: delivery spec described in `docs/domain/ui.md` lines 408-413; secrets policy in `docs/domain/security.md`

- [ ] **Step 1: Read the domain docs**

Read `docs/domain/ui.md` and `docs/domain/security.md` to find the exact open question text and the secrets section.

- [ ] **Step 2: Remove the open question from ui.md**

In `docs/domain/ui.md`, find the open question:

> "Should notifications land in-app only, email only, or both?"

Remove it from the open questions list. If removing it leaves the list empty, remove the entire open questions section header too. The delivery contract is now: in-app (bell/count polling) **and** email at event creation time via SMTP — this is already described in the delivery spec section (lines 408-413) which stays unchanged.

- [ ] **Step 3: Add SMTP credential note to security.md**

In `docs/domain/security.md`, in the secrets/credentials section (lines 152-163), add one bullet after the existing credential rules:

> - SMTP credentials (`smtp_username`, `smtp_password`) are deployment secrets set via environment variables; they must not appear in logs, exception messages, or generated artifacts

- [ ] **Step 4: Commit**

```bash
git add docs/domain/ui.md docs/domain/security.md
git commit -m "docs(001au): resolve notification delivery open question; note smtp secrets"
```

---

## Verification

After all four tasks:

1. **Focused email tests:** `cd engine && python -m pytest tests/test_notifications_email.py -v`
   Expected: 5 tests pass

2. **Existing notification API tests (no regression):** `cd engine && python -m pytest tests/test_notifications_api.py -v`
   Expected: all pass

3. **Config smoke test:** `cd engine && python -c "from src.migrations_engine.config import Settings; s = Settings(); print(s.smtp_host, s.smtp_port, s.smtp_use_tls)"`
   Expected: `'' 587 True`

4. **Credentials do not appear in logs:** search `engine/src/` for any log call that references `smtp_password` or `smtp_username` — there should be none.

## Commit summary

```
feat(001au): add smtp settings to engine config
feat(001au): replace email stub with smtp delivery
test(001au): cover smtp send path and best-effort delivery
docs(001au): resolve notification delivery open question; note smtp secrets
```
