# Task 001ao — FeedComment Model + Thread

**Plan:** `plans/2026-07-01-001ao-feed-comment.md`

## Domain

- `docs/domain/api.md` — FeedComment entity; commenting roles (central_team ↔ project_stakeholder cross-notify)

## Scope

Add threaded commenting on Feeds:

- `FeedComment` DB model (FK → `feeds.source_definition_id`), Alembic migration `0020_feed_comments`
- `GET /projects/{project_id}/feeds/{feed_id}/comments` — list all comments ordered by `created_at`
- `POST /projects/{project_id}/feeds/{feed_id}/comments` — create comment, fire cross-role notification (central_team comment notifies stakeholders; stakeholder comment notifies all central_team users)
- Frontend: `FeedCommentThread` component with fetch-on-mount, comment list with role badges, textarea + submit button
- Notification delivery wraps in `try/except` — comments are never blocked by notification failure

## Tasks (3)

1. **Backend** — `FeedComment` model + migration; `FeedCommentCreateRequest` / `FeedCommentResponse` schemas; `management/feed_comments.py`; `routes/feed_comments.py`; register in `app.py`.
2. **Frontend API helpers** — `FeedCommentRecord` type + `listFeedComments` + `createFeedComment` in `web/lib/feeds-api.ts`.
3. **Frontend component** — `web/components/FeedCommentThread.tsx`.

## Success criteria

- POST creates a comment and returns it; GET returns list in chronological order
- Notification fires to correct recipients without blocking the response
- `FeedCommentThread` renders, submits, and clears textarea on success
- All tests pass

## Execution order

Execute after 001ak. This is in the feed/fiber/comment/AI priority stream and
should land before the later-phase delivery tickets. Requires 001at
(notifications) for `create_notification` import, but can stub if running before
001at.
