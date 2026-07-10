# Design: Codegen Transformation Instructions

**Date:** 2026-07-10
**Status:** Approved

---

## Problem

SQL generation currently receives field mappings and source data but has no mechanism to express:

- **Global coding standards** that apply to every feed in a project (e.g. date format rules, naming conventions)
- **Feed-specific transformation rules** (e.g. rename a field, derive a compound value, prepend a prefix)

Without these, the AI generates SQL that is technically correct but not aligned with the project's conventions or the specific transformations required for each source.

---

## Goal

Add natural-language instruction blocks — at project level and per-feed level — that get included in the codegen AI prompt, steering SQL generation without touching the field mapping layer.

---

## Out of Scope

- Structured/typed rule forms (rename, format, derive as separate UI controls)
- Per-field granular instructions (instructions are at the feed level, not per-binding)
- Review page changes — instructions live only on the codegen page

---

## Data Model

Two new nullable TEXT columns, each requiring an Alembic migration.

### Migration 0030 — `project_definitions.codegen_instructions`

```sql
ALTER TABLE project_definitions ADD COLUMN codegen_instructions TEXT;
```

- Stores project-wide coding standards and global transformation rules
- Nullable; absence means no global instructions

### Migration 0031 — `source_definitions.transformation_instructions`

```sql
ALTER TABLE source_definitions ADD COLUMN transformation_instructions TEXT;
```

- Stores feed-specific transformation rules
- Nullable; absence means no feed-specific instructions

**No migration needed for schema fields** — `staging_schema`, `destination_schema`, and `target_db_engine` already exist inside `domain_config` on `ProjectDefinition` and are parsed via `MigrationProjectConfig`.

---

## Backend

### New API Endpoints

#### `PATCH /projects/{project_id}/codegen-instructions`

```python
class CodegenInstructionsRequest(BaseModel):
    codegen_instructions: str | None

# Response: existing ProjectResponse (updated to include codegen_instructions)
```

- Role guard: `admin` or `central_team`
- Updates `project_definitions.codegen_instructions` for the project's active definition
- Returns the updated `ProjectResponse`

#### `PATCH /projects/{project_id}/sources/{source_definition_id}/transformation-instructions`

```python
class TransformationInstructionsRequest(BaseModel):
    transformation_instructions: str | None

# Response: existing FeedResponse (updated to include transformation_instructions)
```

- Role guard: `admin` or `central_team`
- Updates `source_definitions.transformation_instructions`
- Returns the updated `FeedResponse`
- Mirrors the existing `PATCH .../hints` pattern for `mapping_hints`

### Updated Response Schemas

**`FeedResponse`** — add field:
```python
transformation_instructions: str | None = None
```

**`ProjectResponse`** — add field:
```python
codegen_instructions: str | None = None
```

### Codegen Prompt (`codegen/service.py`)

**`_build_system_prompt`** already receives `project_config: MigrationProjectConfig`. Extend its signature to also accept `codegen_instructions: str | None`. Add `destination_schema` (already in `project_config` but currently omitted) and append the global instructions block:

```
You generate SQL bundles for migration delivery.
Destination object: {destination_object_name}
Target DB engine: {project_config.target_db_engine or 'unknown'}
Staging schema: {project_config.staging_schema or 'unknown'}
Destination schema: {project_config.destination_schema or 'unknown'}

GLOBAL CODING STANDARDS
{codegen_instructions}     ← omit this block entirely if null/empty
```

At the call site in `generate_codegen_artifact`, pass `codegen_instructions=project_definition.codegen_instructions`.

**`_build_user_prompt`** already receives `source_definition: Feed`. Read `source_definition.transformation_instructions` directly inside the function and append it:

```
FEED-SPECIFIC TRANSFORMATION INSTRUCTIONS
{source_definition.transformation_instructions}   ← omit this block entirely if null/empty
```

Place this block after the field mapping section and before (or after) the discussion threads — it provides override context for the specific data being generated.

Each block is omitted entirely (not rendered as an empty header) when the field is null or blank.

---

## Frontend (`web/app/projects/[id]/codegen/page.tsx`)

### New Panel: Coding Standards & Global Instructions

Placed **above** the existing Sources table. Always visible.

```
┌─ Coding Standards & Global Instructions ───────────────────────────────┐
│ Applied to all feeds in this project during SQL generation.             │
│                                                                         │
│ [textarea — free text, min 4 rows]                                      │
│                                                          [Save]         │
└─────────────────────────────────────────────────────────────────────────┘
```

- Loads `project.codegenInstructions` on page mount
- Save calls `PATCH /projects/{project_id}/codegen-instructions`
- Visible to all roles; editable only by `central_team` / `admin`

### Per-Feed: Expandable Instructions Row

Each row in the Sources table gains a toggle chevron. Clicking it expands an inline panel below the row:

```
┌─ [Source label]  [destination]  [encoding]  [status]  [Generate SQL ▼] ┐
│  ▼ Feed-specific transformation instructions                             │
│  [textarea — free text, min 3 rows]                          [Save]     │
└──────────────────────────────────────────────────────────────────────────┘
```

- Loads `source.transformationInstructions` from the sources list response
- Save calls `PATCH /projects/{project_id}/sources/{id}/transformation-instructions`
- Collapsed by default; user expands per feed
- Editable only by `central_team` / `admin`

### New API calls in `codegen-api.ts`

```typescript
saveCodegenInstructions(token, projectId, instructions: string | null)
saveTransformationInstructions(token, projectId, sourceDefinitionId, instructions: string | null)
```

`listFeedContracts` already returns `FeedContractRecord` which will gain `transformationInstructions` once the backend response is updated. The codegen page already calls `listFeedContracts` — no new fetch needed for the per-feed field.

---

## Prompt Construction Example

Given:
- `staging_schema = "stg"`
- `destination_schema = "dbo"`
- `codegen_instructions = "All date columns must use DATE type, never DATETIME. No default timestamps."`
- `transformation_instructions = "Move source field claim_no to destination field external_claim_number. Generate a 15-char claim ID by prepending 'OC' to a zero-padded 13-digit sequence number."`

The system prompt becomes:

```
Target DB engine: sqlserver
Staging schema: stg
Destination schema: dbo

GLOBAL CODING STANDARDS
All date columns must use DATE type, never DATETIME. No default timestamps.

FEED-SPECIFIC TRANSFORMATION INSTRUCTIONS
Move source field claim_no to destination field external_claim_number. Generate a 15-char claim ID by prepending 'OC' to a zero-padded 13-digit sequence number.

[... existing field mapping context ...]
```

---

## Migration Numbering

- `0030_codegen_instructions.py` — adds `codegen_instructions` to `project_definitions`
- `0031_transformation_instructions.py` — adds `transformation_instructions` to `source_definitions`

Verify `down_revision` against latest migration before writing:
```bash
ls engine/migrations/versions/ | sort | tail -1
```

---

## Verification

1. Save global instructions on codegen page → triggers `PATCH /codegen-instructions` → persists
2. Reload page → global instructions textarea pre-populated
3. Expand a feed row → save feed instructions → persists
4. Click Generate SQL → inspect AI call payload — confirm both instruction blocks appear in system prompt
5. Instructions with `null` value → blocks are omitted from prompt (no empty headers)
6. `project_stakeholder` / `read_only_auditor` roles → textareas read-only, no Save button visible
