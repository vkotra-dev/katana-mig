# Summary: Task 001as — Impact Review Backend Flow

## What changed

- Added the impact-review backend flow for runs.
- Added impact-review response schemas for the report payload.
- Added `management/impact.py` to build the report and acknowledge gate 1 rejection.
- Added `routes/impact.py` and registered it in the FastAPI app.
- Added tests for the impact-review config slot and API contract.

## Behavior

- `GET /projects/{project_id}/runs/{run_id}/impact` returns the gate-1 rejection context, replay scope, and AI recommendation.
- `POST /projects/{project_id}/runs/{run_id}/impact/acknowledge` advances the run to `pending_gate_1` and records a management audit event.
- Both endpoints remain project-scoped.

## Verification

- `PYTHONPATH=src python -m pytest tests/test_impact_review_api.py tests/test_impact_review_config.py -q`
- `PYTHONPATH=src python -m pytest tests/test_runs_api.py tests/test_gates_api.py -q`

## Notes

- The regression suite entry point for runs and gates was skipped in this sandbox environment.
- The feature commit already exists on the branch as `c79d1b2`.
