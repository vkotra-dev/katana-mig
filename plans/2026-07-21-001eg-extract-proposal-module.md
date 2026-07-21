# Plan: 001eg — Extract propose_mapping into mapping/proposal.py

## Task and Domain links

- Task: `tasks/001eg-extract-proposal-module.md`
- Domain: none — internal module organization, no behavior change

## Current State

- (Post-001ee/001ef) `review.py` still holds `propose_mapping` (~270 lines) plus the 5
  review/approval functions.
- `propose_mapping` uses, confirmed via its body: DDL parsing (`parse_all_ddl_tables`), several
  `snapshots.py` helpers (`get_project_definition`, `get_source_definition`,
  `latest_source_columns`, `next_snapshot_version` — confirm exact set while extracting), the
  hardened AI schema (`ai_schemas.AIFieldMappingProposal`/`Binding`/`validate_source_fields` from
  001ea), and the templated prompt (`ai/prompt.Prompt` from 001ed).
- `routes/mapping.py:10` imports all 6 verb functions (5 staying in `review.py` + `propose_mapping`)
  from one line.
- `test_mapping_review_api.py`: 26 references to `mapping_review_module` (its alias for `from
  migrations_engine.mapping import review as mapping_review_module`), 16 of which are
  `monkeypatch.setattr(mapping_review_module, "get_adapter", ...)` — all for `propose_mapping`
  tests, confirmed via grep count.

## Objective

1. New `mapping/proposal.py` holding `propose_mapping`, unchanged behavior.
2. `routes/mapping.py`'s import split across `review`/`proposal`.
3. All 16 test monkeypatch targets repointed; `review.py` left holding only the 5
   review/approval-workflow functions.

## Out of Scope

- Any logic change to `propose_mapping`.
- Further splitting beyond the planned 4 modules.

## Blast Radius

- `engine/src/migrations_engine/mapping/proposal.py` (new)
- `engine/src/migrations_engine/mapping/review.py` (edited — `propose_mapping` removed, now
  holds only 5 functions, ~400 lines total)
- `engine/src/migrations_engine/routes/mapping.py` (edited — import split)
- `engine/tests/test_mapping_review_api.py` (edited — 16 monkeypatch targets + import line)

## File Changes

**`engine/src/migrations_engine/mapping/proposal.py` (new)**
- `from .ddl import parse_all_ddl_tables`
- `from .snapshots import get_project_definition, get_source_definition, latest_source_columns, next_snapshot_version`
  (confirm exact subset against `propose_mapping`'s actual body before finalizing — don't
  over-import)
- `from .ai_schemas import AIFieldMappingProposal, Binding, validate_source_fields`
- `from ..ai.prompt import Prompt`
- `propose_mapping(...)` body moved verbatim.

**`engine/src/migrations_engine/mapping/review.py`**
- Delete `propose_mapping` and any imports that become unused as a result (`AIFieldMappingProposal`,
  `Binding`, `validate_source_fields`, `Prompt`, `AICallError`, `AIResponseValidationError`,
  `ValidationError` if none of the 5 remaining functions use them — confirm before removing).

**`engine/src/migrations_engine/routes/mapping.py`**
- Line 10 split:
  ```python
  from ..mapping.review import approve_mapping, get_mapping, patch_mapping, reject_mapping, unapprove_mapping
  from ..mapping.proposal import propose_mapping
  ```

**`engine/tests/test_mapping_review_api.py`**
- Add `from migrations_engine.mapping import proposal as mapping_proposal_module` to the import
  block.
- All 16 `monkeypatch.setattr(mapping_review_module, "get_adapter", ...)` sites (grep for the
  exact pattern before starting, don't rely on line numbers which will have shifted) →
  `monkeypatch.setattr(mapping_proposal_module, "get_adapter", ...)`.
- Any other `mapping_review_module.<name>` reference tied to something that moved (e.g. if any
  test reaches into `ai_schemas` re-exports via the review module) — repoint as needed.
- Tests for `get_mapping`/`patch_mapping`/`approve_mapping`/`reject_mapping`/`unapprove_mapping`
  keep using `mapping_review_module` — unaffected.

## Tests

- No new test behavior — target-module updates only.
- Full `test_mapping_review_api.py` run after the split.
- Specifically: run just the `propose_mapping`-related tests in isolation first
  (`pytest -k propose`) to catch any missed monkeypatch site quickly, before running the full
  suite.

## Verification

- `mypy --strict` / `ruff` clean on all touched files.
- `grep -c mapping_review_module` inside any `propose_mapping`-related test function should be
  zero after this change — confirm no stray references remain.
- Full test suite green.
- Manually exercise "AI Analyze" through the real API to confirm `propose_mapping` still works
  end-to-end after the move.
- Final check: `wc -l mapping/review.py` should now be roughly ~400 lines, holding exactly 5
  functions — confirms the split achieved its stated goal.

## Pitfalls

- This is the task where a partially-completed monkeypatch migration causes real pain: a missed
  site doesn't fail cleanly, it silently calls the real `get_adapter` factory, which either hits
  a real AI provider (slow, possibly erroring on missing credentials in test env) or raises a
  `ConfigurationError` that looks unrelated to this refactor. Grep first, count matches, verify
  the count drops to zero for `propose_mapping` tests specifically before considering this task
  done.
- Don't leave unused imports behind in `review.py` after `propose_mapping` (and everything it
  alone needed) is removed — `ruff` will catch most of these, but verify manually too, since some
  imports (e.g. `AICallError`) might still be used by exception handling that also existed
  elsewhere in the file.

## Commit

Own commit, third of three. Requires 001ee and 001ef merged/landed first. After this lands,
`review.py` is fully at its intended final scope — no follow-up task needed.
