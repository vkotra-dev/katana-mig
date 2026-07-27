---
id: 002i8
title: Specify staging table name in source analysis prompt using feed label
status: pending
created: 2026-07-24
priority: medium
depends-on: [002c0]
domain: engine
task: tasks/002i8-source-analysis-staging-table-name.md
plan: plans/2026-07-24-002i8-source-analysis-staging-table-name.md
---

# Task 002i8 — Source Analysis: Specify staging table name in prompt

## Context

Source analysis AI generates a `CREATE TABLE` DDL for the staging source table. Currently, no
table name is provided in the prompt — the AI invents one arbitrarily. This makes the table name
nondeterministic and makes it impossible for downstream consumers (codegen, review UI) to know the
expected staging table name.

The feed has `source_details` containing a `label` field (a human-readable name like "orders",
"customers"). This label should be merged into the prompt so the AI uses a deterministic,
predictable table name.

**Naming convention decided:** `stg_{feed_label}` — a fixed `"stg_"` prefix. This matches the
convention already documented (but never implemented) in
`docs/domain/project.md:112` ("naming convention `stg_{destination_object_name}`") and
`docs/domain/source-model.md:531`, and is shared with task 002i9's codegen-side wiring so both
the Slice-section source DDL and the codegen-generated stored procedures reference the identical
table name for the same feed.

**Truncation decision:** Sanitize to 59 chars, then prefix `"stg_"` for a total of ≤63 chars
(PostgreSQL `NAMEDATALEN`, SQL Server `IDENTIFIER` limit).

## Domain Updates Required

- `docs/domain/source-model.md` — update `SourceSchemaArtifact.destination_ddl` section to note the
  `stg_{feed_label}` table naming convention and that it is now shared with codegen (task 002i9)

## Current State

- `engine/src/migrations_engine/ai/prompts/source_analysis.yaml` — prompt template with
  `$staging_schema` and `$target_db_engine`, rules numbered 1-6 (rule 6 is "SQL DDL Generation" —
  added by task 002c0). No table name guidance exists yet.
- `engine/src/migrations_engine/management/source_analysis.py` line ~86-90 — `prompt.set()` passes
  `source_type_section`, `sample_text`, `target_db_engine`, `staging_schema`. Does NOT pass feed
  label or table name.
- `engine/src/migrations_engine/management/feeds.py:598` — `_source_label(source_details)` helper
  extracts `source_details.get("label")`, falling back to `"Source"`. **Verified: this function
  currently has zero callers anywhere in the codebase** — it is unused dead code today, not an
  established pattern. This task is its first real usage.
- There is no existing, implemented table-naming helper anywhere in the codebase. The
  `stg_{destination_object_name}` convention is documented in `project.md`/`source-model.md` but
  was never built — grepped the entire codebase for `f"stg_{{...}}"` construction and found none.

## Objective

1. Add a new shared helper `_staging_table_name(feed_label: str) -> str` in
   `engine/src/migrations_engine/management/feeds.py`, next to `_source_label()`. It sanitizes the
   label (lowercase, `[a-z0-9_]` only, max 63 chars for DB identifier limits) and returns
   `f"stg_{sanitized_or_'source'}"`.
2. In `analyze_source_slice()`, compute `_staging_table_name(_source_label(source_definition.source_details))`
   and pass it to the prompt as `staging_table_name`.
3. Fold table-name guidance into the **existing rule 6** ("SQL DDL Generation") in
   `source_analysis.yaml` — do NOT add a new rule 6, since that number is already taken (verified
   current file: rules 1-6 are sequential, 6 = SQL DDL Generation, added by 002c0).
4. Update rule 5 (Schema Qualification) to reference `$staging_table_name` for the bare table name
   it qualifies with the schema.

## Implementation Details

### 1. `engine/src/migrations_engine/management/feeds.py`

Add next to `_source_label()` (around line 598):
```python
def _staging_table_name(feed_label: str) -> str:
    sanitized = re.sub(r'[^a-z0-9_]', '_', feed_label.lower())[:59]
    return f"stg_{sanitized if sanitized else 'source'}"
```
(If `re` is not already imported at module level in `feeds.py`, add the import at the top of the
file. Note: truncate to **59 chars** so that after adding the `"stg_"` prefix the total is
≤63 chars (PostgreSQL `NAMEDATALEN` limit).)

### 2. `engine/src/migrations_engine/management/source_analysis.py`

Add import:
```python
from .feeds import _source_label, _staging_table_name
```

In `analyze_source_slice()`, after extracting `staging_schema`:
```python
feed_label = _source_label(source_definition.source_details)
staging_table_name = _staging_table_name(feed_label)
```

Pass to prompt:
```python
prompt.set(
    source_type_section=source_type_section,
    sample_text=sample_text,
    target_db_engine=target_db,
    staging_schema=staging_schema or "",
    staging_table_name=staging_table_name,
)
```

### 3. `engine/src/migrations_engine/ai/prompts/source_analysis.yaml`

Update rule 5 (Schema Qualification):
```
5. Schema Qualification: If a staging schema name is provided ('$staging_schema'), qualify the table name with this schema (e.g. CREATE TABLE $staging_schema.$staging_table_name (...)). If no schema is provided ('$staging_schema' is empty), use the bare table name.
```

Update rule 6 (SQL DDL Generation) to reference the exact name instead of letting the AI invent one
— fold this in, do not renumber or add a new rule:
```
6. SQL DDL Generation: Using the inferred columns, the target database engine '$target_db_engine', the schema name '$staging_schema', and the EXACT table name '$staging_table_name' (do NOT invent or randomize the table name), generate a valid CREATE TABLE SQL statement. ...
```

## Out of Scope

- Per-feed staging schema (handled in 002c0)
- Changing the `_source_label()` helper's own extraction logic — it already does the right thing
- Wiring `staging_table_name` into codegen's `system_prompt.txt.j2` / `_build_system_prompt()` —
  that is task 002i9, which depends on this task's shared `_staging_table_name()` helper
- Frontend changes — the table name is reflected in the stored DDL automatically

## Pitfalls

1. `source_details` may be `None` — `_source_label()` already handles this, returning `"Source"`.
2. Feed labels may contain special characters (spaces, hyphens, periods) — sanitize to
   `[a-z0-9_]` only before use in a SQL identifier.
3. DB identifier length limits — sanitize to 59 chars, then prefix `"stg_"` for a total of
   ≤63 chars (PostgreSQL `NAMEDATALEN`, SQL Server limit). This was decided in the Context section.
4. Rule numbering: do NOT add a new rule 6 — the current file already has 6 rules (1-6), verified
   directly against the file. Fold this task's guidance into existing rules 5/6 only.
5. Existing artifacts with random/AI-invented table names are unaffected — only new analyses use
   the convention.
6. This task creates `_staging_table_name()` as a **shared** helper — task 002i9 imports and reuses
   it for codegen's system prompt. Do not create a second, duplicate sanitization function there.

## Tests

- **Direct unit tests for `_staging_table_name()`** (test a helper in isolation, not via `analyze_source_slice`):
  - `_staging_table_name("Orders") == "stg_orders"`
  - `_staging_table_name("My-Orders.csv") == "stg_my_orders_csv"` (spaces/hyphens/periods → `_`)
  - `_staging_table_name("Source") == "stg_source"` (fallback from `_source_label()`)
  - `_staging_table_name("a" * 100) == "stg_" + "a" * 59` (truncation to 63-char total)
  - `_staging_table_name("") == "stg_source"` (empty string fallback)
- Integration: `analyze_source_slice()` with a labeled feed → verify `staging_table_name` appears
  in the rendered prompt and the stored DDL contains the expected `stg_{label}` table name.

## Commit

```
feat(source-analysis): specify staging table name in prompt using feed label

- Add shared _staging_table_name() helper in feeds.py (stg_{label} convention)
- Extract feed label via _source_label(), compute staging_table_name
- Pass staging_table_name to source_analysis prompt; fold into existing rule 6
- Fix schema-qualification rule 5 to reference the exact table name
- Add unit tests for sanitization, fallback, and truncation
```
