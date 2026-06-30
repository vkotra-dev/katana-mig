# Task 001aa — Reconciliation (Backend + UI)

**Plan:** `plans/2026-07-01-001aa-reconciliation.md`

## Domain

- `docs/domain/governance.md` — reconciliation, audit trail
- `docs/domain/runs.md` — final stage of the baton chain
- `docs/design/stitch/11-reconciliation-lineage.md` — reconciliation screen mockup

## Depends on

- 001t (RunRecord — reconciliation links to a completed run)
- 001z (Gate 2 must be approved before reconciliation can run)

## Scope

After Gate 2 approval, run reconciliation: compare staging table row counts and key
samples against source records to verify completeness. Produce a `ReconciliationReport`
with pass/fail status per check.

## New model: `ReconciliationReport`

```python
class ReconciliationReport(Base):
    __tablename__ = "reconciliation_reports"

    report_id: str          # UUID pk
    run_id: str             # FK → run_records
    checks: list[dict]      # [{check_name, status: "pass"|"fail", detail}]
    overall_status: str     # "pass" | "fail" | "in_progress"
    created_at: datetime
    completed_at: datetime | None
```

Migration 0014 (after gate_approvals 0013, or merge if 0013 not needed).

## Reconciliation checks

1. **Row count check**: staging table row count == source slice row count
2. **Key integrity check**: sample of 50 primary keys present in staging table
3. **Null rate check**: null rate per field within acceptable threshold (< 5%)
4. **Lookup coverage check**: all lookup fields have non-null values in staging

Checks run synchronously; results written to `ReconciliationReport.checks`.

## API routes (`routes/reconciliation.py`)

```
POST /projects/{project_id}/runs/{run_id}/reconciliation
  — trigger reconciliation for the completed run
  — creates ReconciliationReport(status="in_progress"), runs checks, marks completed
  — central_team only

GET  /projects/{project_id}/runs/{run_id}/reconciliation
  — get latest ReconciliationReport for this run
  — returns report with all check results

GET  /projects/{project_id}/runs/{run_id}/reconciliation/history
  — list all reconciliation reports for this run (re-runs produce multiple)
```

## UI page (`web/app/runs/[id]/reconciliation/page.tsx`)

Per stitch `11-reconciliation.md`:
- Overall status banner (green PASS / red FAIL)
- Checks table: check name | status chip | detail (expandable)
- Row count comparison: expected vs actual
- Sample key table (50 rows)
- "Re-run reconciliation" button (central_team only)
- Link from run detail tab 5 (Reconciliation & lineage)

## Acceptance criteria

- [ ] `POST .../reconciliation` runs all 4 checks and writes report
- [ ] Row count check passes when staging count equals source slice count
- [ ] Key integrity check flags missing keys
- [ ] `ReconciliationReport.overall_status` reflects worst-case check result
- [ ] UI renders overall status banner and per-check rows
- [ ] Migration runs cleanly after previous migrations
- [ ] Tests use an in-memory SQLite test DB (no live staging DB required)

## Notes

- Reconciliation reads staging table counts from the DB session; in the test environment
  use seeded data rather than an actual staging schema
- "Re-run" is allowed: operators can re-trigger reconciliation after fixing a staging issue
- The run detail page (001u) links to this page from tab 5 but does not embed the content
- If stitch `11-reconciliation.md` does not exist, check `docs/design/stitch/` directory
  and use the closest matching screen as reference
