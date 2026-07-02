# Task 001au — Notification Email Delivery

**Plan:** `plans/2026-07-03-001au-notification-email-delivery.md`

## Domain

- `docs/domain/ui.md` — notification delivery semantics; remove the open question once email delivery is real
- `docs/domain/security.md` — SMTP credentials and outbound mail remain secrets

## Scope

Replace the notification email logging stub with real outbound SMTP delivery:

- add SMTP settings to engine config
- send plain-text notification emails with event description and deep link
- keep notification creation best-effort so email failures do not block app-side notification writes
- add tests for the mailer and the notification service integration

## Tasks (2)

1. **Backend** — add SMTP-backed delivery in the notification service, wire config, and cover the send path with tests.
2. **Docs** — update the domain pages so the delivery contract no longer describes the email path as a stub or an open question.

## Success criteria

- notification emails are sent through SMTP when configured
- notification writes still succeed if email delivery fails
- SMTP secrets are not logged or embedded in artifacts
- all focused backend tests pass

