# Task 001ad — Runs and Analysis Review Hardening

**Plan:** `plans/2026-06-30-001ad-runs-analysis-review-hardening.md`

## Domain

- `docs/domain/runs.md` — run scoping, snapshot pinning, resume behavior
- `docs/domain/source-model.md` — analysis contract and adapter slot behavior
- `docs/domain/governance.md` — task traceability and verification rules

## Depends on

- 001t (runs API exists)
- 001v (source analysis exists)

## Scope

Lock down the remaining review concerns around run scoping and source analysis
with explicit regression coverage. The core code paths already implement the
intended behavior; this slice makes sure those guarantees stay visible in tests.

## Current State

- `execute_run()` already scopes run lookup by `project_id` before launch or
  resume.
- Run records already preserve the full `lookup_snapshot_versions` dict for
  multi-lookup execution.
- `analyze_source_slice()` already uses the `field_mapping` adapter slot and
  returns a completed response synchronously.
- The missing piece is direct regression coverage for the reviewed behavior.

## Objective

Add focused tests that prove launch/resume cannot cross projects and that
source analysis keeps using the correct adapter slot and sync response shape.

## Out of Scope

- New API surface
- New migration work
- UI changes
- Reworking the execution engine beyond regression coverage

## Blast Radius

- `engine/tests/test_runs_api.py`
- `engine/tests/test_source_analysis_service.py`

## File Changes

- Add a run API regression test covering wrong-project launch/resume failures.
- Add a source-analysis service regression test covering the `field_mapping`
  adapter slot.

## Tests

- `cd engine && PYTHONPATH=src pytest tests/test_runs_api.py -q`
- `cd engine && PYTHONPATH=src pytest tests/test_source_analysis_service.py -q`

## Verification

- Launch and resume requests against a foreign project return a governed
  `run_not_found` response.
- Source analysis uses the `field_mapping` adapter slot and still returns the
  synchronous completed response shape.

## Pitfalls

- Do not weaken the project scope check in the execution path.
- Do not add unrelated source-analysis refactors while adding the regression.

## Commit

- `test(review): lock down runs and source analysis behavior`
