Task: tasks/completed/002i8-source-analysis-staging-table-name.md
Plan: plans/2026-07-24-002i8-source-analysis-staging-table-name.md
Commits: 641a61a (implementation + plan + task file + TASK_INDEX update), 6b3ef41 (002i9 test updates)

## Changes Made

### `engine/src/migrations_engine/management/feeds.py`
- Added `_staging_table_name(feed_label: str) -> str` helper: sanitizes label to `[a-z0-9_]`,
  truncates to 59 chars, prefixes `"stg_"`, falls back to `"stg_source"`.

### `engine/src/migrations_engine/management/source_analysis.py`
- Imported `_source_label` and `_staging_table_name` from `feeds.py`.
- Computed `feed_label` and `staging_table_name` in `analyze_source_slice()`, passed them to the prompt.

### `engine/src/migrations_engine/ai/prompts/source_analysis.yaml`
- Updated rule 5 (Schema Qualification) to reference `$staging_table_name`.
- Updated rule 6 (SQL DDL Generation) to use the exact table name instead of letting AI invent one.

## Deviations from Plan

None. Implementation matches the plan's File Changes section exactly.

## Domain Updates Required

- `docs/domain/source-model.md` — Updated: noted that `stg_{feed_label}` is now shared between source analysis DDL and codegen-generated stored procedures (extends 002i8's doc note). Timestamp bumped to 2026-07-27.

## Tests

`.venv/bin/python -m pytest engine/tests -q` — all tests pass, 0 failures.

## Verification

`scripts/validate_okf.py` — all 12 domain docs pass, 0 warnings.
