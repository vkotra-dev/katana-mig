---
id: 002ia
title: Fix artifact-history chronological ordering; rename lookup dest_val to id
status: completed
created: 2026-07-28
priority: medium
domain: engine
task: tasks/002ia-artifact-history-order-and-lookup-id-rename.md
plan: plans/2026-07-28-002ia-artifact-history-order-and-lookup-id-rename.md
---

# Task 002ia — Artifact history ordering + lookup reference column rename

## Context

Two independent bugs found while reviewing the codegen page:

**Bug A — Artifact history is not chronological.** The "Artifact history" table on the codegen page
(`web/app/projects/[id]/codegen/page.tsx`, table at line ~893) renders whatever order the backend
returns with no re-sort. The backend query, `list_codegen_artifacts()`
(`engine/src/migrations_engine/codegen/service.py:264-276`), orders by
`CodeGenerationArtifact.destination_object_name.asc(), CodeGenerationArtifact.created_at.desc()` —
grouped by destination table first, chronological only *within* each group. Users see blocks of
history per table instead of one true chronological feed.

**Bug B — Lookup reference tables/prompt/seed-scripts don't expose an "id" column.** Traced the full
value pipeline: `LookupValueMap.source_value_map` / `LookupSnapshot.value_map`
(`engine/src/migrations_engine/db/models.py:397,415`) already store `{source_value: business_id}` —
the value is populated via `_extract_destination_id()`
(`engine/src/migrations_engine/management/lookup_mapping.py:500-511`), which prioritizes an actual
`id` column from the destination row. **The id is already flowing through correctly** — it is just
mislabeled `dest_val` everywhere downstream:
- `_build_lookup_tables()` (`codegen/service.py:494-537`) — `sample_mappings` key and the hardcoded
  `columns` list (`"dest_val VARCHAR(255) NOT NULL"`)
- `user_prompt.txt.j2:27` — renders `{{ m.dest_val }}`
- `system_prompt.txt.j2:15,18` — reference-table column description and the
  `SELECT @_<lookup_name>_id = CAST(ref.dest_val AS ...)` FK-resolution rule
- `codegen/lookup_upsert.py` — a **second, deterministic** seed-SQL generator
  (`generate_lookup_upsert_sql`, called from `management/fibers.py:491` when a lookup fiber is
  approved) that emits real CREATE TABLE / INSERT / upsert SQL for all four supported engines
  (postgresql, mysql, mssql, oracle), all using `dest_val` as the column name.

Because both the AI-facing prompt and this deterministic generator hardcode `dest_val`, no reader
(human or AI) can tell that column already holds a real id — the AI-generated seed script mirrors
that naming and never emits an explicit `id` column either.

This is a **rename**, not a data-model change: `source_val` stays the primary key/join key
(confirmed with the user — it's what the FK-resolution JOIN matches against the staging row), and
`dest_val` becomes `id`. No DB migration needed (`value_map` is a JSON column; shape is unchanged,
only the key name used when rendering it).

## Domain Updates Required

- `docs/domain/ui.md` — the "Artifact history" bullet (line ~162, under "SQL bundle delivery")
  currently says only "all artifacts (active and superseded) with timestamps" with no ordering
  claim. Clarify it to state the list is ordered chronologically (`created_at desc`) across all
  destination tables, since the query previously grouped by table first — worth documenting
  explicitly so this doesn't regress silently again.
- No other domain page requires a change. Grepped `docs/domain/*.md` for `dest_val`, `source_val`,
  and the lookup reference-table column names — none are documented anywhere; the `dest_val` → `id`
  rename is an internal SQL-text/rendering change with no existing domain-page claim to update.

## Objective

1. Fix `list_codegen_artifacts()`'s `ORDER BY` so the "Artifact history" UI shows one true
   chronological feed across all destination tables.
2. Rename `dest_val` → `id` across every place it represents the looked-up business key: the
   AI prompt template, the hardcoded reference-table schema/rule text, and the deterministic
   `lookup_upsert.py` seed-SQL generator — so the reference table, the AI's generated seed script,
   and the FK-resolution rule all consistently expose/use an explicit `id` column.

## Out of Scope

- No change to `LookupValueMap.source_value_map` / `LookupSnapshot.value_map` shape — already
  correct, `{source_value: id}`.
- No change to `_extract_destination_id()` or `_extract_destination_label()` — id extraction
  already works; label extraction is unrelated to this task (dead/unused in this pipeline).
- No change to `source_val`'s role as primary/join key.
- Do not touch the *other* use of the `destination_object_name.asc()` ordering pattern in
  `build_delivery_bundle_text` (`codegen/service.py` ~line 304) — that grouping is intentional there
  (assembling one bundle per table), unrelated to the "Artifact history" list view.
- Task 001fb (lookup AI-proposal contract, `id`/`dest_value` naming at the fiber-proposal layer) is
  a separate, still-open task — this task only touches the codegen-consumption side
  (`LookupSnapshot.value_map` onward), not the AI proposal/`dest_row` layer.

## Blast Radius

| File | Change |
|------|--------|
| `engine/src/migrations_engine/codegen/service.py` | Fix `list_codegen_artifacts()` ORDER BY (line ~274). Rename `dest_val` → `id` in `_build_lookup_tables()` (lines ~526,533). |
| `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2` | Rename `m.dest_val` → `m.id` (line ~27). |
| `engine/src/migrations_engine/codegen/templates/system_prompt.txt.j2` | Rename `dest_val` → `id` in reference-table column description and FK-resolution `SELECT`/`CAST` rule (lines ~15,18). |
| `engine/src/migrations_engine/codegen/lookup_upsert.py` | Rename `dest_val` → `id` in generated DDL/DML for all four engines (lines ~33,41,54,56,69,71,85-89,103-107). |
| `engine/tests/test_codegen_service_api.py` | Update `dest_val` assertion (line ~630) to `id`; add ordering test for `list_codegen_artifacts`. |
| `engine/tests/test_codegen_system_prompt.py` | Update `dest_val` assertions (lines ~54-55) to `id`. |
| `engine/tests/test_bundle_sequencing.py` | Update all `dest_val` SQL-text assertions (~10 occurrences) to `id`. |
| `docs/domain/ui.md` | Clarify the "Artifact history" bullet (line ~162) to state chronological ordering across all destination tables; bump `timestamp` to the actual change date. |

## Tests

- `test_list_codegen_artifacts_is_chronological` — seed artifacts for 2+ destination tables with
  interleaved `created_at` timestamps, assert the returned order matches `created_at desc` globally
  (not grouped by table).
- Update existing lookup-table tests (`test_codegen_service_api.py`,
  `test_codegen_system_prompt.py`, `test_bundle_sequencing.py`) to assert `id` instead of `dest_val`
  in both the structured `sample_mappings`/`columns` output and the generated SQL text.

## Verification

```bash
.venv/bin/python -m pytest engine/tests/test_codegen_service_api.py engine/tests/test_codegen_system_prompt.py engine/tests/test_bundle_sequencing.py -v
.venv/bin/python -m pytest engine/tests -q
.venv/bin/python scripts/validate_okf.py
```

`validate_okf.py` must report zero warnings for `docs/domain/ui.md` before this task moves to
`tasks/completed/` (I22 completion gate).

## Pitfalls

- `dest_val` appears in both the AI-facing prompt/template AND the deterministic
  `lookup_upsert.py` generator — miss either one and the two seed-script surfaces (AI-generated
  bundle vs. fiber-triggered lookup upsert) will disagree on column naming again.
- Don't touch `source_val` — it's confirmed to stay the primary/join key.
- Don't widen `LookupSnapshot.value_map`/`LookupValueMap.source_value_map` — they're already
  correctly shaped; this task is a rendering/SQL-text rename only.
- `build_delivery_bundle_text`'s `destination_object_name.asc()` ordering (service.py ~line 304) is
  a different, intentional use — don't change it.

## Commit

```
fix(codegen): chronological artifact history; rename lookup dest_val to id

- list_codegen_artifacts() now orders by created_at only, so the codegen
  page's Artifact history shows one true chronological feed instead of
  blocks grouped by destination table.
- Renamed dest_val -> id throughout the lookup reference-table pipeline
  (prompt template, hardcoded schema/rules, lookup_upsert.py seed
  generator). The value was already the business id (via
  _extract_destination_id()); it was just mislabeled downstream, so
  neither the AI-generated seed script nor the fiber-triggered upsert
  script ever emitted an explicit id column.
```
