---
id: 002i9
title: Wire staging table name into codegen system prompt using shared helper
status: pending
created: 2026-07-24
priority: medium
depends-on: [002i8]
domain: engine
task: tasks/002i9-codegen-staging-table-name.md
plan: plans/2026-07-24-002i9-codegen-staging-table-name.md
---

# Task 002i9 — Codegen: Wire staging table name into system prompt

## Context

Task 002i8 makes the Slice-section source analysis DDL use a deterministic staging table name
(`stg_{feed_label}`, via a new shared `_staging_table_name()` helper in `feeds.py`). Codegen's own
system prompt (`system_prompt.txt.j2`, used to generate the destination-side stored procedures)
has no equivalent — it never computes or passes a real staging table name. The only reference is a
literal placeholder string in an illustrative example inside the lookup-resolution rules
(`<staging_schema>.staging_table`), not a real Jinja variable. This means the AI generating stored
procedures currently has to invent its own staging table name, which will not match what
`002i8` establishes for the same feed.

## Domain Updates Required

- `docs/domain/source-model.md` — note that `stg_{feed_label}` is now shared between source
  analysis DDL and codegen-generated stored procedures for the same feed (extends 002i8's doc note)

## Current State

- `codegen/service.py`'s `_build_system_prompt()` (around line 668) has parameters
  `project_config`, `destination_object_name`, `project_definition` — no `staging_table_name`.
- `generate_codegen_artifact()` fetches `source_definition = _get_source_definition(...)` at the
  top of the function (line ~65), and it remains in scope through the entire per-table loop,
  including at the `_build_system_prompt()` call site (line ~134) — so
  `source_definition.source_details` is available there without any additional query.
- `system_prompt.txt.j2` line 20 (inside "LOOKUP RESOLUTION RULES") has the placeholder text
  `<staging_schema>.staging_table stg ON stg.<source_column> = ref.source_val` — illustrative only,
  never a real variable.
- Same pattern already exists for a different value: `feed_instructions` is computed live inside
  the per-table loop (via `render_feed_instructions_template()`, task 002i2) and passed into
  `_build_user_prompt()`'s Jinja context. This task follows the identical mechanism —
  compute-live-per-call-and-inject — just for `_build_system_prompt()` instead.

## Objective

1. Import and reuse `_staging_table_name()` and `_source_label()` from `feeds.py` (created by
   002i8 — do NOT create a second, duplicate sanitization function here).
2. In `generate_codegen_artifact()`'s per-table loop, compute
   `staging_table_name = _staging_table_name(_source_label(source_definition.source_details))`
   once per feed (it does not vary per destination table — compute it before the loop, alongside
   the `comments`/`slice_comments` fetch that 002i7 already positioned there, not inside the loop).
3. Add a `staging_table_name: str` parameter to `_build_system_prompt()` and pass it into the
   Jinja render context.
4. Update `system_prompt.txt.j2`'s illustrative lookup-resolution example to use the real
   `{{ staging_table_name }}` value instead of the placeholder text.

## Out of Scope

- Creating a new sanitization helper — reuse 002i8's `_staging_table_name()` exactly as-is
- Changing `_build_user_prompt()` or `feed_instructions` — unrelated, already correct (002i2)
- Any change to `destination_object_name` naming/handling — that's the destination side, this task
  is about the staging/source-side table name referenced inside the generated SQL
- Per-table variation of the staging table name — it's per-feed, computed once, reused across every
  destination table's stored procedure for that feed

## Files Changed

| File | Change |
|------|--------|
| `engine/src/migrations_engine/codegen/service.py` | Import `_staging_table_name`/`_source_label`; compute once per feed before the loop; add parameter to `_build_system_prompt()` |
| `engine/src/migrations_engine/codegen/templates/system_prompt.txt.j2` | Replace placeholder `<staging_schema>.staging_table` with real `{{ staging_table_name }}` |
| `engine/tests/test_codegen_service_api.py` | Add test verifying `staging_table_name` reaches the rendered system prompt |

## Tests

- Unit/integration: seed a feed with `source_details = {"label": "Orders"}`, trigger codegen,
  assert the captured system prompt (via `FakeAdapter`) contains `stg_orders`.
- Unit/integration: seed a feed with no label, assert the fallback `stg_source` appears.
- Verify the value matches exactly what `002i8`'s source-analysis DDL would produce for the same
  `source_details` — same helper, same output, by construction (not re-tested per call, but worth
  one assertion confirming both call sites produce identical output for identical input).

## Verification

```bash
.venv/bin/python -m pytest engine/tests/test_codegen_service_api.py -v
.venv/bin/python -m pytest engine/tests -q
```

## Pitfalls

- Compute `staging_table_name` **once per feed, before the per-table loop** — not inside it. It's
  derived from `source_definition.source_details`, which doesn't change per destination table.
  Recomputing it per iteration would be wasteful and risks drift if the loop's `source_definition`
  reference is ever reassigned.
- Import `_staging_table_name` from `feeds.py`, don't reimplement it — if `002i8` changes the
  sanitization rules later, both call sites must stay in sync automatically.
- Don't confuse this with `destination_object_name` — that's the destination table name (already
  wired, unrelated), this is the *source/staging*-side table name referenced by lookup-resolution
  JOINs and any staging-table references inside the generated procedure body.

## Commit

```
feat(codegen): wire staging table name into system prompt

Reuse 002i8's shared _staging_table_name() helper. Compute once per feed
before the per-table loop, add as a new _build_system_prompt() parameter,
replace the illustrative placeholder in system_prompt.txt.j2 with the real
value. Source analysis DDL and codegen-generated procedures now reference
the identical stg_{feed_label} table name for the same feed.
```
