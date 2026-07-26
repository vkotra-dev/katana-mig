---
id: 001h0
title: Source DDL Generation from AI Analysis
status: ready
created: 2026-07-24
priority: medium
domain: engine / frontend / codegen
depends-on: []
---

# Task 001h0 — Source DDL Generation from AI Analysis

- **Plan**: [2026-07-24-001h0-source-ddl-from-ai-analysis.md](../plans/2026-07-24-001h0-source-ddl-from-ai-analysis.md)
- **Domain**: [source-model.md](../docs/domain/source-model.md), [api.md](../docs/domain/api.md)

## Context

Source analysis runs AI on sample data and produces columns (name, inferred_type, nullable, max_length) stored in `SourceSchemaArtifact`. Currently there is no way to get the generated DDL from the source analysis. The user wants a button on the feed page that shows the generated DDL after source analysis completes.

## Objective

Extend the source analysis AI prompt to also generate a SQL DDL statement (CREATE TABLE) using the inferred columns and the target database engine. Store the generated DDL against the source schema artifact and display it in a collapsible section on the feed page with a "Copy to clipboard" button.

## Out of Scope

- Do NOT auto-apply the DDL to the project's `destination_schema_ddl`
- Do NOT generate DDL for multiple tables — one per source feed
- Do NOT modify the existing column schema or analysis flow beyond adding the DDL field
- Do NOT change the destination schema analysis flow

## Blast Radius

| File | Action | What changes |
|------|--------|-------------|
| `engine/src/migrations_engine/ai/prompts/source_analysis.yaml` | modify | Add `target_db_engine` to prompt + DDL generation instructions |
| `engine/src/migrations_engine/management/analysis_schemas.py` | modify | Add `ddl: str` field to `AnalysisResult` |
| `engine/src/migrations_engine/db/models.py` | modify | Add `destination_ddl` column to `SourceSchemaArtifact` |
| `engine/migrations/versions/0042_add_source_ddl_to_source_schema_artifact.py` | create | Alembic migration for new column |
| `engine/src/migrations_engine/management/source_analysis.py` | modify | Pass `target_db_engine` to prompt + save DDL |
| `engine/src/migrations_engine/api/schemas.py` | modify | Add `destination_ddl` to responses |
| `web/lib/feeds-api.ts` | modify | Include `destinationDDL` in response type |
| `web/app/projects/[id]/feeds/[feedId]/page.tsx` | modify | Add collapsible Source DDL section with copy button |
| `docs/domain/source-model.md` | modify | Document `destination_ddl` field |
| `docs/domain/api.md` | modify | Document new response field |

## Domain Updates Required

- `docs/domain/source-model.md` — document `destination_ddl` on `SourceSchemaArtifact`
- `docs/domain/api.md` — document DDL response field

## Files to Read Before Execution

- `engine/src/migrations_engine/ai/prompts/source_analysis.yaml` — current prompt
- `engine/src/migrations_engine/management/analysis_schemas.py` — `AnalysisResult` schema
- `engine/src/migrations_engine/db/models.py` (lines 319-338) — `SourceSchemaArtifact` model
- `engine/src/migrations_engine/management/source_analysis.py` (lines 41-192) — analyze function
- `engine/src/migrations_engine/api/schemas.py` (lines 404-422) — response schemas
- `web/lib/feeds-api.ts` (lines 591-607) — `analyzeFeedSource` API
- `web/app/projects/[id]/feeds/[feedId]/page.tsx` (lines 667-693) — analyze button section
- `docs/domain/source-model.md` — current source model docs

## Verification

```bash
# Backend: run all tests
.venv/bin/python -m pytest engine/tests -q

# Frontend: verify no type errors
cd web && npx tsc --noEmit 2>&1 | head -20
```

## Pitfalls

- The `AnalysisResult` schema change means the AI must return `ddl` in its JSON output — the prompt must be explicit about the schema
- The `target_db_engine` may be null — default to "postgresql" in the prompt
- The Alembic migration must target `0041` (the current head of the numbered chain)
- Do NOT change the `SourceSchemaArtifact` unique constraint (source_definition_id + source_slice_version)

## Commit

```
feat(source-analysis): generate DDL from AI and display on feed page
```
