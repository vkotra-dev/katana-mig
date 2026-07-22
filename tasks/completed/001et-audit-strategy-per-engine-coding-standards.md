---
type: Task Plan
title: Consolidate Audit-Trace Strategy into Per-Engine Coding Standards
status: ready
---

# Task: 001et-audit-strategy-per-engine-coding-standards

## Context

Two issues found while reviewing `001er`'s shipped output
(`engine/src/migrations_engine/ai/prompts/codegen_coding_standards.yaml`):

1. **The `mssql` section hardcodes literal schema names (`oc_stag`, `cxp`)** instead of using the
   `$stg`/`$dest` merge fields already used everywhere else in the file (5 occurrences: lines with
   `[oc_stag].[mig_upsert_log]`, `[oc_stag].[source_table]`, `[oc_stag].[lookup_table_1]`,
   `[oc_stag].[lookup_table_2]`, and `Schemas [cxp] and [oc_stag] are assumed to exist`). This bug
   is carried over verbatim from the original `generateCodingStandardsTemplate` JS function
   (`001er` was an intentional byte-for-byte relocation, not a rewrite — this pre-existing issue is
   now being fixed here).
2. **Row-level audit/traceability guidance (so every processed row can be traced back to both its
   source and destination identity, per run and table) exists today, but only for MSSQL, and lives
   entirely outside this YAML** — hardcoded as a Python f-string in
   `codegen/service.py::_build_system_prompt` (the "RUN LOGGING REQUIREMENTS" block, lines
   490-505), appended **unconditionally to every project's system prompt regardless of target DB
   engine**. A postgres/mysql/oracle project's actual codegen AI call currently receives
   MSSQL-specific `MERGE`/`OUTPUT`/`IDENTITY` syntax as a hard requirement, which is simply wrong
   for those engines.

## Requirements

1. In `codegen_coding_standards.yaml`'s `mssql` section: replace all 5 hardcoded `oc_stag`/`cxp`
   occurrences with `$stg`/`$dest`. Fold in the `[_row_num] BIGINT IDENTITY(1,1) NOT NULL` staging
   column requirement (currently only stated in the Python-hardcoded block, not in this YAML at
   all) into the existing item 4, which already covers audit-logging column specifics.
2. Add a full, parallel-depth "Migration SP Requirements" numbered list (matching MSSQL's existing
   21-item structure, not just a couple of summary bullets) to the `postgresql`, `mysql`, and
   `oracle` sections — each translating the same underlying principles (idempotent
   creation/re-creation, transaction/error handling, FK-lookup-via-JOIN, audit-column exclusion,
   duplicate-key validation, idempotent seed data, and — the specific new content this task adds —
   a `$stg.mig_upsert_log` audit table (columns: `run_ref`, `dest_table`, `source_row_num`,
   `dest_row_id`, `action`) populated via each engine's own correct, idiomatic mechanism:
   - PostgreSQL: `INSERT ... ON CONFLICT DO UPDATE ... RETURNING` (`xmax = 0` idiom for
     insert-vs-update detection), set-based.
   - MySQL: no `MERGE` exists; `INSERT ... ON DUPLICATE KEY UPDATE` doesn't expose per-row
     identity/action set-based, so this is row-by-row via a cursor with `ROW_COUNT()`/
     `LAST_INSERT_ID()`, batch-committed every 500 rows — genuinely less efficient than the other
     three engines, and the YAML content must say so explicitly as a caveat, not present it as
     equally efficient.
   - Oracle: `MERGE` does **not** support `RETURNING` (verified — this is a real, confirmed Oracle
     limitation, not a stylistic choice) — use two guarded statements instead
     (`UPDATE ... WHERE EXISTS (...) RETURNING ... BULK COLLECT INTO` for matched rows,
     `INSERT ... SELECT ... WHERE NOT EXISTS (...) RETURNING ... BULK COLLECT INTO` for new rows),
     each followed by a `FORALL` insert into the log table.
3. Remove the "RUN LOGGING REQUIREMENTS" block entirely from
   `codegen/service.py::_build_system_prompt` — audit-trace guidance now lives exclusively in
   `codegen_instructions` (populated from this YAML via the "Suggest Standards" button, same as
   every other coding standard), not as a separate Python-enforced append. This is an intentional,
   explicitly-agreed trade-off: audit logging becomes editable/removable text like the rest of the
   coding standards, not a hard Python guarantee. `_build_system_prompt`'s now-unused `run_ref`
   parameter is removed along with it (its call site's `run_ref=f"{project_id}_{source_definition_id}"`
   kwarg for `_build_system_prompt` is deleted; `_build_user_prompt`'s own, separate `run_ref`
   parameter is untouched — it's still needed there and unrelated to this removal).

## Out of Scope

- No change to `_build_user_prompt`/`user_prompt.txt.j2` — already correctly includes
  `run_ref` for its own purposes, unrelated to this task.
- No change to `001es` (wiring the Suggest Standards button to the endpoint) — different files,
  no dependency either direction.
- No backfill/migration of any project's already-saved `codegen_instructions` text — this only
  changes what *new* "Suggest Standards" clicks produce going forward.
- No change to the `shared_header`/`shared_footer` sections' existing content beyond what's needed
  structurally to keep the per-engine sections consistent.

## Dependencies

None. Independent of `001es`.
