Task: tasks/completed/002b8-version-history-backend.md

## Housekeeping note

This task's code (migration, model, routes, patch hooks, tests) was already implemented and
committed prior to this summary being written — found during a `TASK_INDEX.md` audit that
several "Ready" tasks were actually done but never closed out. This summary documents what
exists, confirmed by reading the actual code (not the original task spec, which had drifted
from what shipped).

## Changes Made (as found in the codebase)

- Migration `0043_add_version_history.py` — creates `version_history` table.
- `VersionHistory` model (`db/models.py:680-694`) — `version_id`, `entity_type`, `entity_id`,
  `field_name`, `old_value`, `new_value`, `changed_by`, `changed_at`; indexed on
  `(entity_type, entity_id, field_name)`.
- `VersionHistoryResponse` schema (`api/schemas.py:877-885`).
- Four routes in `routes/versions.py`, one concrete route per entity type — **not** the single
  dynamic `/versions/{entity_type}` route the original task spec described:
  - `GET /projects/{project_id}/versions/hints/versions`
  - `GET /projects/{project_id}/versions/transformation/versions`
  - `GET /projects/{project_id}/versions/codegen/versions`
  - `GET /projects/{project_id}/versions/sql/versions`
  Each project-scoped via `require_project_access` plus a join back to the owning entity, and
  paginated (`limit` default 50/max 200, `offset`).
- Four capture points, one per entity type: `routes/feeds.py:167` (hints), `routes/feeds.py:195`
  (transformation), `routes/projects.py:154` (codegen), `codegen/service.py:233` (sql).
- `engine/tests/test_version_history.py` — 6 tests, all passing.

## Deviations from Plan

- Route shape: four concrete `/versions/{type}/versions` routes instead of one dynamic
  `/versions/{entity_type}` route.
- Entity type values are `"hints"`, `"transformation"`, `"codegen"`, `"sql"` — not the
  `"feed_hints"`/`"feed_transformation"`/`"project_codegen"` values the task's test list
  anticipated. The actual implementation's test file uses the shorter values consistently.

## Domain Updates Required

- `docs/domain/source-model.md` — **Updated**. Added "Field-level version history" section
  documenting the `VersionHistory` table, the four entity types and their capture points, and
  the actual four-route API shape (corrected from the task spec's single dynamic-route
  assumption). `timestamp` bumped to 2026-07-28.
- `docs/domain/api.md` — **Updated**. Added "Version history endpoints" section documenting all
  four routes, shared query params, and response shape. `timestamp` bumped to 2026-07-28.

## Tests

```
.venv/bin/python -m pytest engine/tests/test_version_history.py -q
6 passed, 2 warnings
```

`.venv/bin/python scripts/validate_okf.py` — zero warnings, 12/12 domain pages compliant.

## Note

002b9 (frontend dropdown UI, depends on this task) is **not** implemented — grepped all of
`web/` for `VersionHistory`/`version-history`/`versionHistory`, zero hits. This task's own scope
(backend only, per its "Out of Scope" section) is complete independent of that; 002b9 remains
open with no plan file.
