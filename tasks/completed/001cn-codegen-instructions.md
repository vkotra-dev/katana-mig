# Task: 001cn — Codegen Transformation Instructions

## Status
Ready

## Background

SQL generation currently receives field mappings and source data but has no way to express project-wide coding standards or per-feed transformation rules. Engineers know things the AI doesn't — date format conventions, field renaming rules, derived compound values — and have no place to record them in a way that feeds into SQL generation.

## Goal

Add natural-language instruction blocks at two levels:

- **Project-wide (global):** coding standards that apply to every feed (e.g. "all date columns must use DATE type, never DATETIME")
- **Per-feed (local):** transformation rules specific to a source (e.g. "map claim_no → external_claim_number; prepend 'OC' to form a 15-char claim ID")

Both are injected into the AI codegen prompt without touching the field mapping layer. Both panels live on the codegen page only.

## Data Model

Two new nullable TEXT columns:

- `project_definitions.codegen_instructions` — global coding standards
- `source_definitions.transformation_instructions` — per-feed transformation rules

Migrations: `0030_codegen_instructions.py`, `0031_transformation_instructions.py`

## API

```
PATCH /projects/{project_id}/codegen-instructions
Body: { codegen_instructions: str | null }
Response: ProjectResponse (with codegen_instructions field)
Role: admin | central_team

PATCH /projects/{project_id}/sources/{source_definition_id}/transformation-instructions
Body: { transformation_instructions: str | null }
Response: FeedResponse (with transformation_instructions field)
Role: admin | central_team
```

## Prompt Injection

**System prompt** (`_build_system_prompt`):
```
You generate SQL bundles for migration delivery.
Destination object: {name}
Target DB engine: {engine}
Staging schema: {staging_schema}
Destination schema: {destination_schema}

GLOBAL CODING STANDARDS
{codegen_instructions}     ← omit block entirely if null/blank
```

**User prompt** (`_build_user_prompt`), after field bindings and discussion:
```
FEED-SPECIFIC TRANSFORMATION INSTRUCTIONS
{transformation_instructions}   ← omit block entirely if null/blank
```

## Copy-on-Write Persistence

Both fields must be carried through `update_project()` and `copy_project()` in `management/projects.py`, and the feed copy loop in `copy_project()` must include `transformation_instructions`.

## Frontend

Codegen page (`/projects/[id]/codegen`):

1. **Global instructions panel** — above the sources table; textarea seeded from project; Save calls `PATCH /codegen-instructions`
2. **Per-feed expandable row** — each feed row has a toggle; expands inline textarea; Save calls `PATCH .../transformation-instructions`

Both textareas are read-only for roles other than `central_team` / `admin`.

## Files Changed

**Backend:**
- `engine/migrations/versions/0030_codegen_instructions.py` (new)
- `engine/migrations/versions/0031_transformation_instructions.py` (new)
- `engine/src/migrations_engine/db/models.py` — two new columns
- `engine/src/migrations_engine/api/schemas.py` — `FeedResponse`, `ProjectResponse`, two new request schemas
- `engine/src/migrations_engine/management/projects.py` — `save_codegen_instructions()`, copy-on-write fixes
- `engine/src/migrations_engine/management/feeds.py` — `save_transformation_instructions()`
- `engine/src/migrations_engine/routes/projects.py` — new PATCH route
- `engine/src/migrations_engine/routes/feeds.py` — new PATCH route
- `engine/src/migrations_engine/codegen/service.py` — prompt injection

**Frontend:**
- `web/lib/feeds-api.ts` — `transformationInstructions` on `FeedContractRecord`
- `web/lib/codegen-api.ts` — `saveCodegenInstructions()`, `saveTransformationInstructions()`
- `web/app/projects/[id]/codegen/page.tsx` — global panel + per-feed expandable rows

**Docs:**
- `docs/domain/project.md` — `codegen_instructions` field
- `docs/domain/source-model.md` — `transformation_instructions` field + prompt structure

## Plan

[2026-07-10-codegen-instructions.md](../docs/superpowers/plans/2026-07-10-codegen-instructions.md)

## Spec

[2026-07-10-codegen-instructions-design.md](../docs/superpowers/specs/2026-07-10-codegen-instructions-design.md)

## Verification

1. Save global instructions → reload → textarea pre-populated
2. Save feed instructions → reload → expand same feed → pre-populated
3. Generate SQL → inspect AI call — both instruction blocks in prompt
4. Null instructions → blocks omitted from prompt (no empty headers)
5. `project_stakeholder` role → textareas read-only, no Save buttons
6. Duplicate project → new project retains global + per-feed instructions
7. Update any other project field → `codegen_instructions` not lost
