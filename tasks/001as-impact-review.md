# Task 001as — Impact Review Backend Flow

**Plan:** `plans/2026-07-01-001as-impact-review.md`

## Domain

- `docs/domain/governance.md`
- `docs/domain/runs.md`
- `docs/domain/project.md`
- `docs/domain/source-model.md`

## Scope

Implement the backend impact-review flow: AI slot wiring, impact review service,
schemas, routes, app registration, and tests.

## Current State

- The `impact_analysis` AI slot is already present in `engine/config/engine.yaml`
  and the adapter factory.
- The impact-review API surface, schemas, and service module do not exist yet.
- The worktree already contains an untracked `engine/tests/test_impact_review_config.py`
  file and a modified `engine/tests/test_lookup_ai_slot.py` file.

## Objective

Ship the impact-review backend flow exactly as specified in the brief:
`GET /projects/{project_id}/runs/{run_id}/impact`,
`POST /projects/{project_id}/runs/{run_id}/impact/acknowledge`,
the related schemas, and the tests.

## Out of Scope

- Frontend work
- Database migrations
- Changing unrelated run or gate behavior
- Reworking existing AI slots beyond the impact-review slot

## Blast Radius

- `engine/config/engine.yaml`
- `engine/src/migrations_engine/ai/config.py`
- `engine/src/migrations_engine/ai/factory.py`
- `engine/src/migrations_engine/api/schemas.py`
- `engine/src/migrations_engine/management/impact.py`
- `engine/src/migrations_engine/routes/impact.py`
- `engine/src/migrations_engine/app.py`
- `engine/tests/test_impact_review_config.py`
- `engine/tests/test_impact_review_api.py`

## File Changes

- Keep the impact-analysis AI slot wired through config and factory.
- Add impact-review API response schemas.
- Add impact-review service functions to build the report and acknowledge it.
- Add the impact router and register it in the FastAPI app.
- Add tests covering the AI slot and the API contract.

## Tests

- `cd engine && python -m pytest tests/test_impact_review_config.py -v`
- `cd engine && python -m pytest tests/test_impact_review_api.py -v`

## Verification

- The AI factory accepts `impact_analysis`.
- `GET /projects/{project_id}/runs/{run_id}/impact` returns the report shape from
  the spec and fails closed on missing run or missing gate-1 rejection.
- `POST /projects/{project_id}/runs/{run_id}/impact/acknowledge` returns the
  updated `RunResponse` and persists the status change.

## Pitfalls

- Do not weaken project scoping.
- Do not silently invent defaults for missing gate-1 rejection data.
- Keep the service call to `impact_analysis` slot isolated behind the adapter factory.

## Commit

- `feat(review): add impact review backend flow`
