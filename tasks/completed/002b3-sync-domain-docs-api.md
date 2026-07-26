---
id: 002b3
title: Sync docs/domain/api.md against actual codebase
status: completed
created: 2026-07-24
priority: medium
domain: docs
depends-on: []
---

# Sync docs/domain/api.md

## Objective

Update `docs/domain/api.md` to accurately reflect all current API endpoints. Last updated 2026-07-24.

## Scope

- `docs/domain/api.md` only

## What to verify

1. **Extract all endpoints from route files** — List every endpoint in each route file:
   - `auth.py`, `users.py`, `projects.py`, `feeds.py`, `fibers.py`, `mapping.py`, `mapping_snapshots.py`
   - `lookup.py`, `codegen.py`, `analysis.py`, `runs.py`, `runs_progress.py`
   - `gates.py`, `change_requests.py`, `dry_run.py`, `impact.py`, `reconciliation.py`
   - `feed_slice_approval.py`, `feed_comments.py`, `notifications.py`, `sign_offs.py`
   - `ai_calls.py`, `config.py`, `auth.py`

2. **Endpoints to verify exist but may be missing from docs:**
   - `GET /{source_definition_id}/schema-artifact` (new, from task 001h0)
   - `GET /projects/{project_id}/lookup-maps` (updated structure)
   - `PATCH /{lookup_value_map_id}` (with addSourceValue, removeSourceValue, moveSourceValue)
   - `PATCH /{source_definition_id}/hints` (mapping hints)
   - `PATCH /{source_definition_id}/transformation-instructions`
   - `GET /projects/{project_id}/delivery-bundle`
   - `GET /projects/{project_id}/lookup-maps`
   - `GET /projects/{project_id}/schema-analysis`
   - `GET /projects/{project_id}/codegen-artifacts`
   - `GET /{report_id}/export`
   - `GET /{report_id}/lineage`
   - `POST /gate-1/approve`, `POST /gate-1/reject`
   - `POST /gate-2/approve`, `POST /gate-2/reject`

3. **Request/response shapes** — Verify all JSON schemas match actual response models

4. **Status codes** — Verify error responses match actual behavior

5. **Pagination** — Verify pagination is described for endpoints that support it

## Out of scope

- Any other domain doc files
- Backend implementation changes

## Acceptance criteria

- [ ] Every endpoint in route files is listed in the API doc
- [ ] Every endpoint in the API doc exists in the route files
- [ ] Request/response shapes match actual models
- [ ] Status codes are accurate
- [ ] Changelog updated
- [ ] timestamp updated
