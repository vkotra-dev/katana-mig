from __future__ import annotations

from email.message import EmailMessage

from migrations_engine.config import Settings
from migrations_engine.management import notifications


def test_settings_expose_smtp_defaults() -> None:
    settings = Settings()

    assert settings.smtp_host == ""
    assert settings.smtp_port == 587
    assert settings.smtp_username == ""
    assert settings.smtp_password == ""
    assert settings.smtp_from_address == ""
    assert settings.smtp_use_tls is True


def test_send_notification_email_uses_smtp(monkeypatch) -> None:
    sent_messages: list[EmailMessage] = []

    class FakeSMTP:
        def __init__(self, host: str, port: int) -> None:
            self.host = host
            self.port = port
            self.started_tls = False
            self.logged_in: tuple[str, str] | None = None

        def __enter__(self) -> "FakeSMTP":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def starttls(self) -> None:
            self.started_tls = True

        def login(self, username: str, password: str) -> None:
            self.logged_in = (username, password)

        def send_message(self, message: EmailMessage) -> None:
            sent_messages.append(message)

    monkeypatch.setattr(
        notifications,
        "get_settings",
        lambda: Settings(
            smtp_host="smtp.example.com",
            smtp_port=2525,
            smtp_username="mailer",
            smtp_password="secret%21",
            smtp_from_address="katana@example.com",
            smtp_use_tls=True,
        ),
    )
    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)

    notifications.send_notification_email(
        "user@example.com",
        "gate_1_waiting",
        "/projects/project-1/runs/run-1",
    )

    assert len(sent_messages) == 1
    message = sent_messages[0]
    assert message["From"] == "katana@example.com"
    assert message["To"] == "user@example.com"
    assert message["Subject"] == "[Katana] Gate 1 Waiting"
    assert "Event: gate_1_waiting" in message.get_content()
    assert "View: /projects/project-1/runs/run-1" in message.get_content()
