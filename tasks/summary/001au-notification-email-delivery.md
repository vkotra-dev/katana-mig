# 001au — Notification Email Delivery

Implemented SMTP-backed notification delivery and closed the docs gap:

- added SMTP settings to engine config with password decoding support
- replaced the logging stub in `send_notification_email` with plain-text SMTP delivery
- kept notification persistence best-effort so email failures do not block writes
- added focused tests for SMTP success, skip behavior, failure handling, and persistence
- updated `docs/domain/ui.md` and `docs/domain/security.md` to describe the real delivery contract and secret handling

Verification:

- `PYTHONPATH=engine/src pytest engine/tests/test_notifications_email.py -q`
- `PYTHONPATH=engine/src pytest engine/tests/test_notifications_api.py -q`
- Result: `10 passed`

