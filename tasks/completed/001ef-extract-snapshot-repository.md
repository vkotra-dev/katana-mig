# Plan: 001ef — Extract Snapshot DB-Helpers into mapping/snapshots.py

## Task and Domain links

- Task: `tasks/001ef-extract-snapshot-repository.md`
- Domain: none — internal module organization, no behavior change

## Current State

- (Post-001ee) `mapping/review.py` still holds, at what was lines 108-270 before 001ee removed
  the DDL-parsing block above it: `_get_project_destination_schema`, `_get_source_definition`,
  `_latest_snapshot`, `_next_snapshot_version`, `derive_destination_fields`,
  `_snapshot_to_response`, `_latest_source_columns`, `_get_project_definition`.
- Confirmed via grep: `_get_project_destination_schema` calls `parse_ddl` (post-001ee name);
  `derive_destination_fields` calls `parse_all_ddl_tables`.
- Confirmed via grep, only one external caller: `routes/mapping_snapshots.py:14`:
  `from ..mapping.review import derive_destination_fields`.
- `get_mapping` (`review.py:587` pre-001ee numbering) calls `_get_project_destination_schema` —
  confirmed via grep, this is the reason `review.py` still needs to import from `snapshots.py`
  after this task, not just `proposal.py`.

## Objective

1. New `mapping/snapshots.py`, functions renamed without leading underscore, importing
   `parse_all_ddl_tables`/`parse_ddl` from `.ddl`.
2. `review.py` imports whatever subset of `snapshots.py` its remaining functions need.
3. `routes/mapping_snapshots.py` repointed to the new module.

## Out of Scope

- `propose_mapping` extraction — 001eg.
- Any query/response-shaping logic change.

## Blast Radius

- `engine/src/migrations_engine/mapping/snapshots.py` (new)
- `engine/src/migrations_engine/mapping/review.py` (edited — ~160 lines removed, import added)
- `engine/src/migrations_engine/routes/mapping_snapshots.py` (edited — 1 import line)
- `engine/tests/test_snapshots.py` (new, if warranted — see Tests)
- No API/frontend change.

## File Changes

**`engine/src/migrations_engine/mapping/snapshots.py` (new)**
- `from .ddl import parse_all_ddl_tables, parse_ddl`
- `get_project_destination_schema`, `get_source_definition`, `latest_snapshot`,
  `next_snapshot_version`, `derive_destination_fields`, `snapshot_to_response`,
  `latest_source_columns`, `get_project_definition` — bodies moved verbatim, underscore dropped,
  internal calls to `_parse_ddl`/`_parse_all_ddl_tables` updated to the post-001ee names.

**`engine/src/migrations_engine/mapping/review.py`**
- Delete the 8-function block.
- Add `from .snapshots import <whichever subset propose_mapping / get_mapping / patch_mapping /
  approve_mapping / reject_mapping / unapprove_mapping actually call>` — confirm the exact set
  while moving (don't blanket-import all 8 into every consumer if some are unused there).

**`engine/src/migrations_engine/routes/mapping_snapshots.py`**
- Line 14: repoint import to `..mapping.snapshots`.

## Tests

- `engine/tests/test_snapshots.py`: if `test_mapping_review_api.py` has any tests directly
  exercising these helper functions in isolation (not just indirectly via `propose_mapping`/
  `get_mapping`/etc.), move them; otherwise this is optional — the helpers are already covered
  indirectly by the full API test suite.
- Full `test_mapping_review_api.py` run — should pass unchanged.
- Confirm `routes/mapping_snapshots.py`'s own test coverage (if any) still passes after the
  import repoint.

## Verification

- `mypy --strict` / `ruff` clean.
- `git diff --stat`: boring diff, move + rename only.
- Full test suite green, including anything exercising `GET`/mapping-snapshot endpoints that go
  through `routes/mapping_snapshots.py`.

## Pitfalls

- `get_mapping` (staying in `review.py`) still needs `get_project_destination_schema` from the
  new module — don't assume `review.py` only needs helpers because `propose_mapping` hasn't moved
  yet either; check every remaining function's actual call graph, not just the ones being
  extracted.
- Keep the dependency direction one-way: `snapshots.py` imports from `ddl.py`, never the reverse.

## Commit

Own commit, second of three. Requires 001ee merged/landed first.
