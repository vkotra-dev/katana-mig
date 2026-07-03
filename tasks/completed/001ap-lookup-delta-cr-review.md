# Task 001ap — Lookup Delta CR Review Screen

**Plan:** `plans/2026-07-01-001ap-lookup-delta-cr-review.md`

## Domain

- `docs/domain/api.md` — ChangeRequest lifecycle; lookup_delta type; resolve action

## Scope

Add the three backend endpoints and frontend review page for resolving lookup delta change requests:

- `GET /projects/{project_id}/change-requests` — list open CRs for a project
- `GET /projects/{project_id}/change-requests/{cr_id}` — CR detail (type, old/new values, status)
- `POST /projects/{project_id}/change-requests/{cr_id}/resolve` — project stakeholder accepts a mapping value; patches `LookupValueMap`, mints new approved `LookupSnapshot`, queues paused run, closes CR — all in one transaction
- Frontend: review page at `/projects/[id]/change-requests/[crId]` showing CR detail form + resolve button; redirects on success
- No new DB model — uses existing `ChangeRequest`, `LookupValueMap`, `LookupSnapshot`, `RunRecord`

## Tasks (3)

1. **Backend** — `list_change_requests`, `get_change_request`, `resolve_change_request` in `management/change_requests.py`; `routes/change_requests.py`; register in `app.py`; schemas in `api/schemas.py`.
2. **Frontend API helpers** — `listChangeRequests`, `getChangeRequest`, `resolveChangeRequest` in `web/lib/change-requests-api.ts`.
3. **Frontend review page** — `web/app/projects/[id]/change-requests/[crId]/page.tsx`.

## Success criteria

- Resolve endpoint applies mapping, re-queues run, closes CR in one transaction
- 409 `cr_not_open` if already resolved; 409 `cr_wrong_type` if not a lookup_delta CR
- Review page loads CR detail, submits form, redirects on success
- All tests pass

## Execution order

Execute after 001ai (existing CR infrastructure). No dependency on fiber models.
This sits after the feed/fiber/comment/AI priority stream and before the later-
phase delivery tickets only if you need the CR review surface earlier.
