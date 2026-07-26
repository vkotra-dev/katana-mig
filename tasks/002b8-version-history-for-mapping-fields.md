---
id: 002b8
title: Add version history for mapping hints, codegen instructions, transformation instructions, and SQL scripts
status: active
created: 2026-07-24
priority: medium
domain: engine / web
---

# Task 002b8 — Version History for Mapping Fields

## Context

Four writable text fields across the platform currently have no version history — when an operator changes a value, the previous value is lost. The goal is a unified `version_history` table that records every change, a `GET /versions` endpoint per entity, and a timestamp-based dropdown UI near the editable fields.

The four entities:

| Entity | Table | Column | Current versioning |
|---|---|---|---|
| Mapping hints | `source_definitions` | `mapping_hints` (Text) | None |
| Codegen instructions | `project_definitions` | `codegen_instructions` (Text) | New definition per update (definition_id), but no version_history entry |
| Transformation instructions | `source_definitions` | `transformation_instructions` (Text) | None |
| SQL scripts | `code_generation_artifacts` | `sql_bundle` (Text) | Each run creates new artifact; already versioned by artifact_id but no version_history entry |

## Current State

- `source_definitions.mapping_hints` is patched via `PATCH /projects/{pid}/sources/{sid}/hints` (routes/feeds.py:151)
- `source_definitions.transformation_instructions` is patched via `PATCH /projects/{pid}/sources/{sid}/transformation-instructions` (routes/feeds.py:169)
- `project_definitions.codegen_instructions` is patched via `PATCH /projects/{pid}/codegen-instructions` (routes/projects.py:137)
- `code_generation_artifacts.sql_bundle` is set when `generate_codegen_artifact` creates a new artifact (codegen/service.py:54)
- No `version_history` table exists
- No version history API endpoint exists
- No UI for browsing versions

## Correct Output Contract

1. **Database**: `version_history` table with columns: `version_id`, `entity_type`, `entity_id`, `field_name`, `old_value`, `new_value`, `changed_by`, `changed_at`. Index on `(entity_type, entity_id, field_name)`.
2. **SQLAlchemy model**: `VersionHistory` mapped to `version_history`.
3. **API schemas**: `VersionHistoryResponse` (version_id, field_name, old_value, new_value, changed_by, changed_at) and `VersionHistoryCreateRequest`.
4. **API routes**: `GET /feed-hints/versions`, `GET /project-codegen/versions`, `GET /feed-transformation/versions`, `GET /codegen-sql/versions` — each returns list of VersionHistoryResponse ordered by changed_at desc.
5. **Patch hooks**: Each existing PATCH handler captures old value before writing and inserts a VersionHistory record.
6. **Frontend**: Version history dropdown near each editable field showing changed_at timestamps. Clicking a version shows old/new diff inline.

## Out of Scope

- No diff-generation algorithm — `old_value` and `new_value` are stored as full text, diff is UI-only
- No notification on version creation
- No soft-delete or purge of old versions
- No versioning for other fields (e.g. copybook_text, layout_information)

## Domain Updates Required

- `docs/domain/source-model.md` — Add `VersionHistory` model section
- `docs/domain/api.md` — Add version history endpoint documentation

## Red Flags

1. **Migration ordering** — Must inspect the current migration chain (last revision is `0042_add_source_ddl_to_source_schema_artifact.py`, revision `0042`) and create `0043` with correct `down_revision`.
2. **Model import in routes** — `routes/feeds.py` and `routes/projects.py` must import `VersionHistory` from `..db.models`. Must not break existing imports.
3. **ProjectDefinition is versioned by definition_id** — The `update_project` service creates a new `ProjectDefinition` per update. The version_history entry is separate metadata, not a replacement for the existing definition versioning.
4. **Frontend type safety** — New API endpoints must be typed in the existing API client modules (`feeds-api.ts`, `projects-api.ts`) following the existing pattern.
