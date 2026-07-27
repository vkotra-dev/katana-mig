Task: tasks/002i9-codegen-staging-table-name.md
Plan: plans/2026-07-24-002i9-codegen-staging-table-name.md
Commits: 6b3ef41 (implementation + test + plan + task file)

## Changes Made

### `engine/src/migrations_engine/codegen/service.py`
- Imported `_source_label` and `_staging_table_name` from `feeds.py` (shared helper from 002i8).
- Computed `staging_table_name` once per feed, before the per-table loop in `generate_codegen_artifact()`.
- Added `staging_table_name: str` parameter to `_build_system_prompt()` and passed it into the Jinja render context.
- All call sites in the loop now receive the real staging table name.

### `engine/src/migrations_engine/codegen/templates/system_prompt.txt.j2`
- Replaced the placeholder `<staging_schema>.staging_table` with the real `{{ staging_table_name }}` value in the lookup-resolution example (line 20).

### `engine/tests/test_codegen_service_api.py`
- New `_seed_project_with_details()` helper that accepts custom `source_details`.
- New `test_system_prompt_includes_staging_table_name` — feeds with `label: "My-Orders.csv"` assert `stg_my_orders_csv` in system prompt.
- New `test_system_prompt_staging_table_name_fallback` — feeds with no label assert `stg_source` fallback.

### `engine/tests/test_codegen_system_prompt.py`
- Added `staging_table_name` argument to `_build_system_prompt` calls in existing test.

### `test_codegen_includes_staging_table_name`
- Updated `test_system_prompt_has_one_proc_per_table_rule` to pass the new `staging_table_name` parameter.

## Deviations from Plan

None. Implementation matches the plan's File Changes section exactly.

## Domain Updates Required

- `docs/domain/source-model.md` — Updated: noted that `stg_{feed_label}` is now shared between source analysis DDL and codegen-generated stored procedures. Timestamp bumped to 2026-07-27.

## Tests

`.venv/bin/python -m pytest engine/tests -q` — all tests pass, 0 failures.

## Verification

`scripts/validate_okf.py` — all 12 domain docs pass, 0 warnings.
