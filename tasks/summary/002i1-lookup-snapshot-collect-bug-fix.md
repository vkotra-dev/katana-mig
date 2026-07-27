Task: tasks/completed/002i1-lookup-snapshot-collect-bug-fix.md
Plan: plans/2026-07-24-002i1-lookup-snapshot-collect-bug-fix.md
Commits: ab7ab83 (implementation + plan + task files + TASK_INDEX update)

## Changes Made

### `engine/src/migrations_engine/codegen/service.py`
- `_select_lookup_snapshot_version()` changed from returning a single `str | None` to returning
  `list[dict[str, str]]` with entries `{"lookup_name": ..., "snapshot_version": ...}`.
- Collects ALL matching lookup snapshots from a mapping snapshot instead of returning on first match.
- `_build_user_prompt()` updated to receive `lookup_snapshots` list instead of single value.

### `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2`
- Changed from iterating over a single `lookup_snapshot_version` string to iterating over the
  `lookup_snapshots` list, displaying each lookup name and its version.

### `engine/tests/test_codegen_service_api.py`
- New `test_select_lookup_snapshot_version_collects_all`: verifies 3 lookup snapshots are all returned.
- New `test_select_lookup_snapshot_version_empty_on_no_lookups`: verifies empty list for zero lookups.

## Deviations from Plan

None. Implementation matches the plan's File Changes section exactly.

## Domain Updates Required

- `docs/domain/source-model.md` — Verified: the `lookup_snapshot_version` list type is documented
  in the code generation artifact section. No change needed — already current.

## Tests

`.venv/bin/python -m pytest engine/tests -q` — all tests pass, 0 failures.

## Verification

`scripts/validate_okf.py` — all 12 domain docs pass, 0 warnings.
