---
id: 002b8
title: Add version history table, API, and patch hooks (backend)
status: pending
created: 2026-07-24
priority: medium
depends-on: []
domain: engine
---

# Task 002b8 — Version History Backend

## Context

Four writable text fields across the platform have no change history — when an operator changes a value, the previous value is lost. This task creates the `version_history` table, a scoped REST API, and version-capture hooks in the existing PATCH handlers.

The four entities:

| Entity | Table | Column | Route prefix |
|---|---|---|---|
| Mapping hints | `source_definitions` | `mapping_hints` (Text) | `/projects/{pid}/versions/hints` |
| Codegen instructions | `project_definitions` | `codegen_instructions` (Text) | `/projects/{pid}/versions/codegen` |
| Transformation instructions | `source_definitions` | `transformation_instructions` (Text) | `/projects/{pid}/versions/transformation` |
| SQL scripts | `code_generation_artifacts` | `sql_bundle` (Text) | `/projects/{pid}/versions/sql` |

## Current State

- `source_definitions.mapping_hints` is patched via `PATCH /projects/{pid}/sources/{sid}/hints` (routes/feeds.py:151)
- `source_definitions.transformation_instructions` is patched via `PATCH /projects/{pid}/sources/{sid}/transformation-instructions` (routes/feeds.py:169)
- `project_definitions.codegen_instructions` is patched via `PATCH /projects/{pid}/codegen-instructions` (routes/projects.py:137)
- `code_generation_artifacts.sql_bundle` is set when `generate_codegen_artifact` creates a new artifact (codegen/service.py:54)
- No `version_history` table exists
- No version history API endpoint exists
- All existing routes are prefixed `/projects/{project_id}/` and call `require_project_access` for project isolation (I15/I21)

## Objective

1. **Migration**: `0043_add_version_history` creates `version_history` table with indexed `(entity_type, entity_id, field_name)`.
2. **Model**: `VersionHistory` SQLAlchemy model mapped to `version_history`.
3. **Schemas**: `VersionHistoryResponse` + `VersionHistoryCreateRequest` Pydantic schemas.
4. **API**: `GET /projects/{pid}/versions/{entity_type}` returns list of VersionHistoryResponse scoped by project_id, guarded by `require_project_access`.
5. **Patch hooks**: Each existing PATCH handler (hints, transformation, codegen, codegen-artifact) captures old value and inserts a `VersionHistory` record before committing.

## Out of Scope

- No UI/dropdown — handled in follow-up task 002b9
- No diff-generation algorithm — full `old_value` and `new_value` stored as text; diff is UI-only
- No notification on version creation
- No soft-delete or purge of old versions
- No versioning for other fields (e.g. copybook_text, layout_information)

## Domain Updates Required

- `docs/domain/source-model.md` — Add `VersionHistory` model section
- `docs/domain/api.md` — Add version history endpoint documentation

## Pitfalls

1. **Migration ordering**: Read `engine/migrations/versions/0042_add_source_ddl_to_source_schema_artifact.py` to confirm `down_revision = "0042"` before writing `0043`.
2. **timezone handling**: The codebase uses `from datetime import UTC, datetime` (codegen/service.py:3). Use `datetime.now(UTC)` — do NOT use `_dt.timezone.utc` (AttributeError).
3. **Project scoping**: Every new route must be under `/projects/{project_id}/`, accept a `project_id` path parameter, and call `require_project_access(db, user=actor, project_id=project_id)` before returning data.
4. **Import ordering**: New imports in existing route files must go in alphabetical/standard-import groups, not at the bottom of the file.
5. **ProjectDefinition versioning**: `update_project()` creates a new `ProjectDefinition` with a new `definition_id`. The version_history entry must be captured *before* calling `update_project()` and must read the old `codegen_instructions` from the current definition *before* the update overwrites it.
6. **Test fixtures**: The new test must import `VersionHistory` from `migrations_engine.db.models` and add the import to the existing `_setup_sqlite_db` fixture which calls `Base.metadata.create_all()`.

## Tests

Add `engine/tests/test_version_history.py` with:

1. `test_version_history_hints_capture` — PATCH hints, assert VersionHistory record created with correct old/new values
2. `test_version_history_hints_empty_old` — PATCH hints when field was previously null, assert old_value is null
3. `test_version_history_transformation_capture` — PATCH transformation_instructions, assert record created
4. `test_version_history_codegen_capture` — PATCH codegen_instructions, assert record created
5. `test_version_history_project_scoped` — user with access to project A cannot see version history of project B's feeds
6. `test_version_history_entity_types` — verify each entity_type value: "feed_hints", "feed_transformation", "project_codegen"

## Commit

```
feat(versioning): add version_history table, API, and patch hooks

- Migration 0043: version_history table with indexed (entity_type, entity_id, field_name)
- VersionHistory SQLAlchemy model
- VersionHistoryResponse + VersionHistoryCreateRequest schemas
- GET /projects/{pid}/versions/{entity_type} endpoint with require_project_access
- Patch hooks in feeds.py (hints, transformation), projects.py (codegen), codegen/service.py (sql)
- Test suite: 6 tests covering capture, project scoping, and entity types
```
