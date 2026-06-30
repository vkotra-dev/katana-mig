# Task 001z — Review Gates (Gate 1, Gate 2 + UI)

**Plan:** `plans/2026-06-29-001z-review-gates.md` _(to be written)_

## Domain

- `docs/domain/governance.md` — approval chain, Gate 1, Gate 2, audit events
- `docs/domain/runs.md` — baton chain; runs move past gates on approval
- `docs/design/stitch/08-gate-1-review.md` — Gate 1 mockup
- `docs/design/stitch/09-gate-2-review.md` — Gate 2 mockup (if exists)
- `docs/design/stitch/10-impact-review.md` — impact review mockup (if exists)

## Depends on

- 001y (CodeGenerationArtifact must exist — Gate 1 reviews the generated SQL)
- 001t (RunRecord must exist — gates advance the run)

## Scope

Two formal approval gates that operator (`central_team`) must pass before data migration
proceeds:

**Gate 1 — Code review gate:** Review `CodeGenerationArtifact.sql_bundle` + mapping
configuration before staging execution.

**Gate 2 — Impact review gate:** Review the staging table counts, sample rows, and
reconciliation preview before the final cut-over.

Each gate creates an approval record on `RunRecord.approvals` (existing JSON column)
or a new `GateApproval` model.

## Gate approval model

Check if `RunRecord.approvals` JSON column is sufficient for gate tracking. If not,
add a new `GateApproval` model (migration 0013):

```python
class GateApproval(Base):
    __tablename__ = "gate_approvals"

    approval_id: str        # UUID pk
    run_id: str             # FK → run_records
    gate: str               # "gate_1" | "gate_2"
    approved_by: str        # user_id
    approved_at: datetime
    notes: str | None
```

If `RunRecord.approvals` is already a JSON blob that can hold gate records,
use that instead (YAGNI — no new model if avoidable).

## API routes (`routes/gates.py`)

```
POST /projects/{project_id}/runs/{run_id}/gates/gate-1/approve
  — marks Gate 1 approved on this run
  — emits AuditEvent(event_type="gate_1_approved")
  — transitions run to next stage
  — central_team only

POST /projects/{project_id}/runs/{run_id}/gates/gate-1/reject
  — marks Gate 1 rejected; run status → "paused"
  — central_team only

POST /projects/{project_id}/runs/{run_id}/gates/gate-2/approve
  — marks Gate 2 approved
  — emits AuditEvent(event_type="gate_2_approved")
  — central_team only

POST /projects/{project_id}/runs/{run_id}/gates/gate-2/reject
  — marks Gate 2 rejected
  — central_team only

GET  /projects/{project_id}/runs/{run_id}/gates
  — returns gate status for both gates on this run
```

## UI pages

### Gate 1 review (`web/app/runs/[id]/gate-1/page.tsx`)

Per stitch `08-gate-1-review.md`:
- SQL bundle viewer: scrollable, monospace, copy icon
- Mapping summary table: source field → destination field → lookup field
- Codegen artifact metadata: artifact ID, created_at, model used
- Approve / Reject buttons (central_team only)
- Rejection: modal with notes field

### Gate 2 review (`web/app/runs/[id]/gate-2/page.tsx`)

Per stitch `09-gate-2-review.md` (verify file exists first):
- Staging table row count
- Sample rows (first 10) in a table
- Pre-reconciliation impact summary
- Approve / Reject buttons (central_team only)

## Acceptance criteria

- [ ] `POST .../gate-1/approve` records approval and advances run stage
- [ ] `POST .../gate-1/reject` pauses run and records rejection reason
- [ ] Gate 2 routes follow same pattern
- [ ] `AuditEvent` is created for each approval and rejection
- [ ] Gate 1 UI renders sql_bundle viewer and mapping summary
- [ ] Gate 2 UI renders staging row count and sample rows
- [ ] Approve/Reject buttons are hidden for non-`central_team` roles

## Notes

- Gates are sequential: Gate 2 cannot be approved before Gate 1
- Rejected runs can be re-proposed (operator fixes the issue and re-triggers code gen)
- Read stitch files at `docs/design/stitch/08-*.md`, `09-*.md`, `10-*.md` before implementing
  UI to ensure exact vocabulary and layout are followed
- If stitch files for gate 2 or impact review don't exist, use stitch `08` as the template
  pattern and note the gap
