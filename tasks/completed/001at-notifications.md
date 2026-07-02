# Task 001at — Notifications

**Plan:** `plans/2026-07-01-001at-notifications.md`

## Domain

- `docs/domain/api.md` — Notification model; 9 event types; email delivery stub

## Scope

Add an in-app notification system:

- `Notification` DB model (FK → `users`, FK → `project_registry`), Alembic migration `0017_notifications` (chains after `0016_project_schema_analysis`)
- `create_notification(db, user_id, project_id, event_type, deep_link, payload)` service in `management/notifications.py`
- `send_notification_email` stub (logs to Python logger — no real SMTP)
- 4 endpoints in `routes/notifications.py`: GET list (unread first), GET count, POST mark-read, POST mark-all-read
- Frontend: `NotificationBell` component with 30-second polling, unread badge, dropdown list; deep-link navigation on click

Event types: `gate_1_waiting`, `gate_2_waiting`, `impact_review_waiting`, `dry_run_waiting`, `lookup_delta_discovered`, `reconciliation_failed`, `knowledge_freeze_published`, `execution_complete`, `feed_comment_added`

## Tasks (3)

1. **Backend** — `Notification` model + migration; `management/notifications.py`; `routes/notifications.py`; register in `app.py`; schemas in `api/schemas.py`.
2. **Frontend API helpers** — `listNotifications`, `getUnreadCount`, `markNotificationRead`, `markAllRead` in `web/lib/notifications-api.ts`.
3. **Frontend component** — `web/components/NotificationBell.tsx` with polling + dropdown.

## Success criteria

- Migration `0017_notifications` applies cleanly
- `create_notification` inserts row; mark-read/all-read update `read` flag
- `NotificationBell` shows badge with unread count, clears on mark-all-read
- All tests pass

## Execution order

No dependencies. Execute in Wave 1 alongside 001ah.
