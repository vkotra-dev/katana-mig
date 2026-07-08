# Task 001cb — Promote LookupValueMap to Project Scope

**Plan:** `plans/2026-07-08-001cb-lookup-value-map-project-scope.md`

## Context

`LookupValueMap` is currently keyed by `(source_definition_id, lookup_name)` — one map per feed per lookup name. But a lookup table in the destination system (e.g., `GENDER_CODES`) is shared across all feeds in the project. Two feeds both mapping a `gender` column duplicate the same map entry. Worse, after 001ca bridges confirmed fiber mappings into `LookupValueMap`, the bridge would write one entry per feed — creating duplicates rather than sharing.

The fix: promote `LookupValueMap` to project scope — keyed by `(project_id, lookup_name)`. Listing for a specific feed is derived via `ProjectFiber` (which already declares which lookup names belong to which feed).

## Scope

### Migration

- Add `project_id VARCHAR(36)` FK to `project_registry.project_id` on `lookup_value_maps`
- Backfill: `UPDATE lookup_value_maps lvm JOIN source_definitions sd ON lvm.source_definition_id = sd.source_definition_id SET lvm.project_id = sd.project_id`
- Drop `source_definition_id` column from `lookup_value_maps`
- Add unique constraint on `(project_id, lookup_name)` replacing the old one on `(source_definition_id, lookup_name)`

### Backend — `db/models.py`

Replace:
```python
source_definition_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_definitions.source_definition_id"), nullable=False)
```
With:
```python
project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project_registry.project_id"), nullable=False, index=True)
```

### Backend — `management/lookup_mapping.py`

- `create_lookup_value_map`: remove `source_definition_id` param; use `project_id` as the key
- `list_lookup_value_maps`: accept optional `feed_id` param; when provided, filter `lookup_name IN (fiber_keys for that feed via ProjectFiber)`; when absent, return all for project
- `_latest_lookup_value_map`: filter by `(project_id, lookup_name)` instead of `(source_definition_id, lookup_name)`
- `generate_lookup_snapshot`: keep `source_definition_id` in signature — still needed to find source analysis and mapping snapshot for validation; only `LookupValueMap` lookup changes to project-scoped

### Backend — `management/change_requests.py` and `management/gates.py`

Both query `LookupValueMap` by `source_definition_id`. Change to filter by `(project_id, lookup_name)`. Both already have `project_id` in scope from the run record.

### Routes — `routes/lookup.py`

Change lookup-maps URLs from:
- `POST /projects/{project_id}/sources/{source_definition_id}/lookup-maps`
- `GET  /projects/{project_id}/sources/{source_definition_id}/lookup-maps`

To:
- `POST /projects/{project_id}/lookup-maps`
- `GET  /projects/{project_id}/lookup-maps?feed_id={feedId}` (feed_id is optional query param)

`generate_lookup_snapshot` route stays at `/projects/{project_id}/sources/{source_definition_id}/lookup-snapshots` — that call is inherently feed-specific (validates against source analysis for that feed).

### Frontend — `web/lib/lookup-api.ts`

- `listLookupValueMaps(token, projectId, feedId)`: URL becomes `/projects/${projectId}/lookup-maps?feed_id=${feedId}`
- `createLookupValueMap(token, projectId, sourceDefinitionId, input)`: remove `sourceDefinitionId` param; URL becomes `/projects/${projectId}/lookup-maps`
- `generateLookupSnapshot`: no URL change

### Frontend — Callers

- `web/app/projects/[id]/feeds/[feedId]/page.tsx`: update `createLookupValueMap` call (remove feedId arg)
- `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`: `listLookupValueMaps` call unchanged in args (feedId still passed, just moves to query param)

### 001ca bridge update

In `_bridge_lookup_fiber_to_value_map` (added by 001ca), change:
```python
source_definition_id=fiber.feed_id  →  project_id=fiber.project_id
```

## Acceptance Criteria

- Two feeds with the same `lookup_name` share one `LookupValueMap` row — approving either fiber's mappings writes to the same row
- `GET /projects/{id}/lookup-maps?feed_id={feedId}` returns only lookup maps whose `lookup_name` matches a lookup fiber on that feed
- `GET /projects/{id}/lookup-maps` (no feed_id) returns all maps for the project
- `generate_lookup_snapshot` continues to validate against source analysis for the specific feed
- Existing data migrated without loss
- TypeScript compiles cleanly

## Pitfalls

- Migration backfill requires joining through `Feed` (`source_definitions`) to get `project_id` — run as a raw SQL update in the migration, not ORM
- The unique constraint changes from `(source_definition_id, lookup_name)` to `(project_id, lookup_name)` — if existing data has duplicate `(project_id, lookup_name)` rows from different feeds, the migration will fail. Add a dedup step first (keep the most recent row per `(project_id, lookup_name)`).
- `change_requests.py` derives `source_definition_id` from the run record to find the map — after this change it uses `project_id` from the run instead. Verify `RunRecord` has `project_id` directly.
- `listLookupValueMaps` in the review page passes `feedId` as second arg — the function signature changes but the caller is unchanged; only the underlying URL format changes.

## Commit

- `feat(001cb): promote LookupValueMap to project scope; list by feed via ProjectFiber`
