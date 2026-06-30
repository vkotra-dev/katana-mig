# Task 001z — Review Gates (Gate 1, Gate 2 + UI)

**Plan:** `plans/2026-06-30-001z-review-gates.md`

## Domain

- `docs/domain/ui.md` — authoritative Gate 1 / Gate 2 contract
- `docs/domain/governance.md` — approval chain, audit events, task workflow
- `docs/domain/runs.md` — baton chain; runs move past gates on approval
- `docs/design/stitch/08-gate1-review.md` — Gate 1 mockup
- `docs/design/stitch/09-gate2-review.md` — Gate 2 mockup
- `docs/design/stitch/10-other-review-gates.md` — impact/dry-run/lookup-delta follow-up screens

## Depends on

- 001y (CodeGenerationArtifact must exist — Gate 1 reviews the generated SQL)
- 001t (RunRecord must exist — gates advance the run)

## Scope

Two formal approval gates that run reviewers pass before data migration proceeds:

**Gate 1:** review the domain object map, PII classification, and coverage gaps.

**Gate 2:** review the Lookup Inventory versus Lookup Map comparison.

Approval records are stored in `RunRecord.approvals` as JSON records. No new gate
model was required.

## Backend

- Added `GateApproveRequest`, `GatePushbackRequest`, `GateRecordResponse`,
  `GateStatusResponse`, `Gate1EvidenceResponse`, and `Gate2EvidenceResponse`.
- Added `management/gates.py` for evidence lookup and approval state transitions.
- Added `routes/gates.py` with:
  - `GET /projects/{project_id}/runs/{run_id}/gates`
  - `GET /projects/{project_id}/runs/{run_id}/gates/gate-1/evidence`
  - `GET /projects/{project_id}/runs/{run_id}/gates/gate-2/evidence`
  - `POST /projects/{project_id}/runs/{run_id}/gates/gate-1/approve`
  - `POST /projects/{project_id}/runs/{run_id}/gates/gate-1/reject`
  - `POST /projects/{project_id}/runs/{run_id}/gates/gate-2/approve`
  - `POST /projects/{project_id}/runs/{run_id}/gates/gate-2/reject`
- Registered the gates router in `app.py`.
- Gate 1 approval now moves the run to `awaiting_approval` with
  `current_stage="gate_2_pending"`.
- Gate 1 / Gate 2 rejections pause the run and store the push-back reason in
  `pause_metadata`.

## UI

- Added `web/lib/gates-api.ts`.
- Added `web/app/runs/[id]/gate-1/page.tsx`.
- Added `web/app/runs/[id]/gate-2/page.tsx`.
- Added page tests for both screens.

## Verification

- `KATANA_BOOTSTRAP_ADMIN_EMAIL=admin@example.com KATANA_BOOTSTRAP_ADMIN_PASSWORD=admin-password PYTHONPATH=engine/src pytest engine/tests/test_gates_api.py -q`
- `KATANA_BOOTSTRAP_ADMIN_EMAIL=admin@example.com KATANA_BOOTSTRAP_ADMIN_PASSWORD=admin-password PYTHONPATH=engine/src pytest engine/tests/test_runs_api.py -q`
- `KATANA_BOOTSTRAP_ADMIN_EMAIL=admin@example.com KATANA_BOOTSTRAP_ADMIN_PASSWORD=admin-password PYTHONPATH=engine/src pytest engine/tests/test_source_slice_approval_api.py -q`
- `cd web && npm test`

## Result

- 4 gate API tests passed
- 2 runs API tests passed
- 2 source slice approval tests passed
- 41 web test files passed, 110 tests total
