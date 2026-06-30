Task: tasks/001aa-reconciliation.md
Domain: docs/domain/runs.md · docs/design/stitch/11-reconciliation-lineage.md
Depends on: 001t (RunRecord), 001z (Gate 2 approval)

## Source of truth

`docs/design/stitch/11-reconciliation-lineage.md` is the screen contract.
`docs/domain/runs.md` § "Reconciliation and lineage" defines the evidence requirements.
Access control: `central_team` only for write operations; all roles (including
`read_only_auditor`) for read and export.

## Current state

| File | What exists |
|---|---|
| `engine/src/migrations_engine/db/models.py` | No reconciliation tables |
| `engine/migrations/versions/` | Latest: `0014_run_record_lookup_snapshot_versions.py` (revision `0014_run_record_lookup_snapshot_versions`) |
| `engine/src/migrations_engine/management/` | No reconciliation service |
| `engine/src/migrations_engine/routes/` | No reconciliation routes |
| `web/app/runs/[id]/` | Tab 5 "Reconciliation & Lineage" link present per 001u; target page does not exist |
| `docs/domain/runs.md` | Has § "Reconciliation and lineage" describing evidence requirements; no schema detail |

## Blast radius

| File | Action |
|---|---|
| `engine/src/migrations_engine/db/models.py` | add `ReconciliationReport`, `ReconciliationLineageRow` |
| `engine/migrations/versions/0015_reconciliation_tables.py` | create — migration |
| `engine/src/migrations_engine/api/schemas.py` | add reconciliation schemas |
| `engine/src/migrations_engine/management/reconciliation.py` | create — service |
| `engine/src/migrations_engine/routes/reconciliation.py` | create — 5 routes |
| `engine/src/migrations_engine/app.py` | register reconciliation router |
| `engine/tests/test_reconciliation_api.py` | create — backend tests |
| `web/lib/reconciliation-api.ts` | create — TS types + fetch helpers |
| `web/app/runs/[id]/reconciliation/page.tsx` | create — UI page |
| `web/app/runs/[id]/reconciliation/page.test.tsx` | create — UI tests |
| `docs/domain/runs.md` | update — add reconciliation report + lineage schema detail |

## DB models

### `ReconciliationReport`

```python
class ReconciliationReport(Base):
    __tablename__ = "reconciliation_reports"

    report_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("run_records.run_id"), nullable=False, index=True
    )
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    # each check: {check_name: str, status: "pass"|"fail", detail: str}
    overall_status: Mapped[str] = mapped_column(String(16), nullable=False, default="in_progress")
    # "in_progress" | "pass" | "fail"
    row_count_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # {source_rows: int, destination_rows: int, rejected: int, duplicated: int, partially_mapped: int}
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

### `ReconciliationLineageRow`

One row per source row processed during execution. Enables the lineage explorer
(select a source row → see its destination row(s) and outcome).

```python
class ReconciliationLineageRow(Base):
    __tablename__ = "reconciliation_lineage_rows"

    lineage_row_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reconciliation_reports.report_id"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("run_records.run_id"), nullable=False, index=True
    )
    source_row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    source_row_key: Mapped[str | None] = mapped_column(String(255))
    # primary key value extracted from the source row (for display in the explorer)
    destination_row_id: Mapped[str | None] = mapped_column(String(255))
    # destination record identifier (null for rejected rows)
    mapping_rules_applied: Mapped[list[str] | None] = mapped_column(JSON)
    # list of field binding names used (["customer_id → id", "full_name → name"])
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    # "confirmed" | "rejected" | "duplicated" | "partially_mapped"
    outcome_detail: Mapped[str | None] = mapped_column(String(512))
    # reason string for non-confirmed outcomes
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

## Migration 0015

**File:** `engine/migrations/versions/0015_reconciliation_tables.py`

```python
revision = "0015_reconciliation_tables"
down_revision = "0014_run_record_lookup_snapshot_versions"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "reconciliation_reports",
        sa.Column("report_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("run_records.run_id"), nullable=False),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("overall_status", sa.String(16), nullable=False, server_default="in_progress"),
        sa.Column("row_count_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reconciliation_reports_run_id", "reconciliation_reports", ["run_id"])

    op.create_table(
        "reconciliation_lineage_rows",
        sa.Column("lineage_row_id", sa.String(36), primary_key=True),
        sa.Column("report_id", sa.String(36), sa.ForeignKey("reconciliation_reports.report_id"), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("run_records.run_id"), nullable=False),
        sa.Column("source_row_index", sa.Integer(), nullable=False),
        sa.Column("source_row_key", sa.String(255), nullable=True),
        sa.Column("destination_row_id", sa.String(255), nullable=True),
        sa.Column("mapping_rules_applied", sa.JSON(), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("outcome_detail", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reconciliation_lineage_rows_report_id", "reconciliation_lineage_rows", ["report_id"])
    op.create_index("ix_reconciliation_lineage_rows_run_id", "reconciliation_lineage_rows", ["run_id"])

def downgrade() -> None:
    op.drop_index("ix_reconciliation_lineage_rows_run_id", "reconciliation_lineage_rows")
    op.drop_index("ix_reconciliation_lineage_rows_report_id", "reconciliation_lineage_rows")
    op.drop_table("reconciliation_lineage_rows")
    op.drop_index("ix_reconciliation_reports_run_id", "reconciliation_reports")
    op.drop_table("reconciliation_reports")
```

Verify the migration chain before implementing:
```bash
cd engine && alembic history | head -5
# must show 0014_run_record_lookup_snapshot_versions as the current head
alembic upgrade head
```

## API schemas (`api/schemas.py` additions)

```python
class ReconciliationCheckResult(BaseModel):
    check_name: str
    status: str   # "pass" | "fail"
    detail: str

class RowCountSummary(BaseModel):
    source_rows: int
    destination_rows: int
    rejected: int
    duplicated: int
    partially_mapped: int

class ReconciliationReportResponse(BaseModel):
    report_id: str
    run_id: str
    checks: list[ReconciliationCheckResult]
    overall_status: str   # "in_progress" | "pass" | "fail"
    row_count_summary: RowCountSummary | None
    created_at: str
    completed_at: str | None

class LineageRowResponse(BaseModel):
    lineage_row_id: str
    source_row_index: int
    source_row_key: str | None
    destination_row_id: str | None
    mapping_rules_applied: list[str]
    outcome: str   # "confirmed" | "rejected" | "duplicated" | "partially_mapped"
    outcome_detail: str | None

class LineageResponse(BaseModel):
    rows: list[LineageRowResponse]
    total: int
    offset: int
    limit: int

class ReconciliationExportResponse(BaseModel):
    report_id: str
    run_id: str
    exported_at: str
    checks: list[ReconciliationCheckResult]
    overall_status: str
    row_count_summary: RowCountSummary | None
    lineage_rows: list[LineageRowResponse]
```

## Management service (`management/reconciliation.py`)

### Check definitions

Four checks, each returning `{check_name, status, detail}`:

**1. Row count check** — `source_rows` from `SourceSlice` (count of `SourceSliceRow` for the
pinned `source_slice_version`) vs `destination_rows` in `row_count_summary`. Pass if equal.

**2. Key integrity check** — sample up to 50 `SourceSliceRow.row_csv` rows, parse each as
CSV, extract the first column value as the key. For each key, check it appears in lineage
rows (i.e., a `ReconciliationLineageRow` with that `source_row_key` exists for the run,
with `outcome != "rejected"`). Pass if all 50 sampled keys found.

**3. Null rate check** — from `MappingArtifact.mapped_rows` (list of destination-shaped
dicts), compute null rate per destination field. Pass if every field has null rate < 5%.

**4. Lookup coverage check** — from `MappingArtifact.mapped_rows`, for every field that
was translated via lookup (derivable from `MappingSnapshot.field_bindings`), confirm the
destination value is non-null. Pass if all lookup-translated fields are non-null.

### Service functions

```python
def trigger_reconciliation(
    db: Session,
    *,
    project_id: str,
    run_id: str,
) -> ReconciliationReportResponse:
    """
    Requires gate_2 approved on run. Creates ReconciliationReport(status="in_progress"),
    builds lineage rows from MappingArtifact.mapped_rows + SourceSliceRow data,
    runs all 4 checks, writes results, sets overall_status = worst of all check statuses.
    Raises 409 if reconciliation already in_progress for this run.
    Raises 422 if gate_2 not approved.
    """
    ...

def get_latest_report(
    db: Session,
    *,
    project_id: str,
    run_id: str,
) -> ReconciliationReportResponse:
    """
    Returns the most-recently-created ReconciliationReport for the run.
    Raises 404 if no report exists.
    """
    ...

def list_reports(
    db: Session,
    *,
    project_id: str,
    run_id: str,
) -> list[ReconciliationReportResponse]:
    """All reports for the run, newest first."""
    ...

def get_lineage(
    db: Session,
    *,
    project_id: str,
    run_id: str,
    report_id: str,
    offset: int = 0,
    limit: int = 100,
    outcome: str | None = None,
    source_row_index: int | None = None,
) -> LineageResponse:
    """
    Paginated lineage rows. Filter by outcome or source_row_index for drill-down.
    Raises 404 if report not found for this run.
    """
    ...

def export_report(
    db: Session,
    *,
    project_id: str,
    run_id: str,
    report_id: str,
) -> ReconciliationExportResponse:
    """
    Full report + all lineage rows bundled as a single JSON-serialisable object.
    Used by the Download button. No pagination — intended for file download.
    Raises 404 if report not found for this run.
    """
    ...
```

### Lineage row builder

When `trigger_reconciliation` runs, after inserting the `ReconciliationReport`, build
lineage rows from `MappingArtifact.mapped_rows`. The engine's inner loop already writes
destination-shaped rows into `MappingArtifact`. Reconstruct lineage as follows:

```python
def _build_lineage_rows(
    db: Session,
    *,
    run: RunRecord,
    report: ReconciliationReport,
    source_rows: list[SourceSliceRow],
    mapped_rows: list[dict[str, str]],
    field_bindings: list[dict],  # from MappingSnapshot
) -> None:
    """
    Pair source_rows[i] with mapped_rows[i] by position (the inner loop processes
    source rows in order and appends to mapped_rows). For each pair:
      - parse source_row_key from row_csv first column
      - extract destination_row_id from mapped row primary key field (first binding target)
      - outcome: "confirmed" if destination_row_id is non-null, "rejected" otherwise
      - mapping_rules_applied: list of "src_field → dst_field" strings from field_bindings
    If len(source_rows) != len(mapped_rows): mark surplus source rows as "rejected"
    with outcome_detail "no destination row produced".
    """
```

## Routes (`routes/reconciliation.py`)

```python
router = APIRouter(prefix="/projects/{project_id}/runs/{run_id}/reconciliation", tags=["reconciliation"])

@router.post("", response_model=ReconciliationReportResponse, status_code=201)
def trigger(project_id: str, run_id: str, db: Session = Depends(get_db), session: UiSession = Depends(require_role("central_team"))):
    return trigger_reconciliation(db, project_id=project_id, run_id=run_id)

@router.get("", response_model=ReconciliationReportResponse)
def get_report(project_id: str, run_id: str, db: Session = Depends(get_db), session: UiSession = Depends(require_auth)):
    return get_latest_report(db, project_id=project_id, run_id=run_id)

@router.get("/history", response_model=list[ReconciliationReportResponse])
def history(project_id: str, run_id: str, db: Session = Depends(get_db), session: UiSession = Depends(require_auth)):
    return list_reports(db, project_id=project_id, run_id=run_id)

@router.get("/{report_id}/lineage", response_model=LineageResponse)
def lineage(
    project_id: str, run_id: str, report_id: str,
    offset: int = 0, limit: int = 100,
    outcome: str | None = None,
    source_row_index: int | None = None,
    db: Session = Depends(get_db),
    session: UiSession = Depends(require_auth),
):
    return get_lineage(db, project_id=project_id, run_id=run_id, report_id=report_id,
                       offset=offset, limit=limit, outcome=outcome, source_row_index=source_row_index)

@router.get("/{report_id}/export", response_model=ReconciliationExportResponse)
def export(project_id: str, run_id: str, report_id: str, db: Session = Depends(get_db), session: UiSession = Depends(require_auth)):
    return export_report(db, project_id=project_id, run_id=run_id, report_id=report_id)
```

Register in `app.py`:
```python
from migrations_engine.routes import reconciliation
app.include_router(reconciliation.router)
```

## Backend tests (`engine/tests/test_reconciliation_api.py`)

```python
import pytest
from fastapi.testclient import TestClient

# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def seeded_run(db_session, central_team_token):
    """RunRecord with gate_2 approved, MappingArtifact with 3 mapped rows,
    matching SourceSliceRow entries (3 rows), and a MappingSnapshot."""
    ...  # create project, run, source_slice, 3 SourceSliceRows, MappingArtifact(mapped_rows=[...])
    return run_id

# ── trigger ───────────────────────────────────────────────────────────────────

def test_trigger_creates_report(client, seeded_run, central_team_token):
    r = client.post(f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation",
                    headers={"Authorization": f"Bearer {central_team_token}"})
    assert r.status_code == 201
    data = r.json()
    assert data["overall_status"] in ("pass", "fail")
    assert len(data["checks"]) == 4

def test_trigger_requires_central_team(client, seeded_run, auditor_token):
    r = client.post(f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation",
                    headers={"Authorization": f"Bearer {auditor_token}"})
    assert r.status_code == 403

def test_trigger_requires_gate2_approved(client, db_session, central_team_token):
    """Run without gate_2 approval raises 422."""
    run_id = make_run_without_gate2(db_session)
    r = client.post(f"/projects/{PROJECT_ID}/runs/{run_id}/reconciliation",
                    headers={"Authorization": f"Bearer {central_team_token}"})
    assert r.status_code == 422

def test_trigger_idempotent_blocks_concurrent(client, seeded_run, central_team_token):
    """Second trigger while in_progress raises 409."""
    client.post(f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation",
                headers={"Authorization": f"Bearer {central_team_token}"})
    # force report to stay in_progress
    ...
    r = client.post(f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation",
                    headers={"Authorization": f"Bearer {central_team_token}"})
    assert r.status_code == 409

# ── row count check ───────────────────────────────────────────────────────────

def test_row_count_check_passes_when_counts_match(client, seeded_run, central_team_token):
    r = client.post(f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation",
                    headers={"Authorization": f"Bearer {central_team_token}"})
    report = r.json()
    row_count_check = next(c for c in report["checks"] if c["check_name"] == "row_count")
    assert row_count_check["status"] == "pass"

def test_row_count_check_fails_on_mismatch(client, db_session, central_team_token):
    """Add extra SourceSliceRow not reflected in MappingArtifact → row_count fails."""
    run_id = make_run_with_extra_source_row(db_session)
    r = client.post(f"/projects/{PROJECT_ID}/runs/{run_id}/reconciliation",
                    headers={"Authorization": f"Bearer {central_team_token}"})
    report = r.json()
    row_count_check = next(c for c in report["checks"] if c["check_name"] == "row_count")
    assert row_count_check["status"] == "fail"
    assert report["overall_status"] == "fail"

# ── key integrity check ───────────────────────────────────────────────────────

def test_key_integrity_passes_all_keys_present(client, seeded_run, central_team_token):
    r = client.post(f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation",
                    headers={"Authorization": f"Bearer {central_team_token}"})
    key_check = next(c for c in r.json()["checks"] if c["check_name"] == "key_integrity")
    assert key_check["status"] == "pass"

def test_key_integrity_fails_missing_key(client, db_session, central_team_token):
    """One source row marked rejected in lineage → key integrity fails."""
    run_id = make_run_with_rejected_row(db_session)
    r = client.post(f"/projects/{PROJECT_ID}/runs/{run_id}/reconciliation",
                    headers={"Authorization": f"Bearer {central_team_token}"})
    key_check = next(c for c in r.json()["checks"] if c["check_name"] == "key_integrity")
    assert key_check["status"] == "fail"

# ── lineage ───────────────────────────────────────────────────────────────────

def test_lineage_rows_created_on_trigger(client, seeded_run, central_team_token):
    r = client.post(f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation",
                    headers={"Authorization": f"Bearer {central_team_token}"})
    report_id = r.json()["report_id"]
    lineage_r = client.get(
        f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation/{report_id}/lineage",
        headers={"Authorization": f"Bearer {central_team_token}"},
    )
    assert lineage_r.status_code == 200
    assert lineage_r.json()["total"] == 3  # seeded_run has 3 source rows

def test_lineage_filter_by_outcome(client, seeded_run, central_team_token):
    r = client.post(f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation",
                    headers={"Authorization": f"Bearer {central_team_token}"})
    report_id = r.json()["report_id"]
    lineage_r = client.get(
        f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation/{report_id}/lineage?outcome=confirmed",
        headers={"Authorization": f"Bearer {central_team_token}"},
    )
    assert all(row["outcome"] == "confirmed" for row in lineage_r.json()["rows"])

def test_lineage_drill_down_by_source_row_index(client, seeded_run, central_team_token):
    """Filter lineage by source_row_index=0 returns exactly one row."""
    r = client.post(f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation",
                    headers={"Authorization": f"Bearer {central_team_token}"})
    report_id = r.json()["report_id"]
    lineage_r = client.get(
        f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation/{report_id}/lineage?source_row_index=0",
        headers={"Authorization": f"Bearer {central_team_token}"},
    )
    assert lineage_r.json()["total"] == 1

def test_lineage_read_only_auditor_can_read(client, seeded_run, auditor_token, central_team_token):
    r = client.post(f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation",
                    headers={"Authorization": f"Bearer {central_team_token}"})
    report_id = r.json()["report_id"]
    lineage_r = client.get(
        f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation/{report_id}/lineage",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert lineage_r.status_code == 200

# ── export ────────────────────────────────────────────────────────────────────

def test_export_bundles_report_and_lineage(client, seeded_run, central_team_token):
    r = client.post(f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation",
                    headers={"Authorization": f"Bearer {central_team_token}"})
    report_id = r.json()["report_id"]
    export_r = client.get(
        f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation/{report_id}/export",
        headers={"Authorization": f"Bearer {central_team_token}"},
    )
    assert export_r.status_code == 200
    data = export_r.json()
    assert "checks" in data
    assert "lineage_rows" in data
    assert "exported_at" in data

def test_export_auditor_can_download(client, seeded_run, auditor_token, central_team_token):
    r = client.post(f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation",
                    headers={"Authorization": f"Bearer {central_team_token}"})
    report_id = r.json()["report_id"]
    export_r = client.get(
        f"/projects/{PROJECT_ID}/runs/{seeded_run}/reconciliation/{report_id}/export",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert export_r.status_code == 200
```

## Frontend types (`web/lib/reconciliation-api.ts`)

```typescript
import { jsonRequest } from "./api-base";

export interface ReconciliationCheckResult {
  checkName: string;
  status: "pass" | "fail";
  detail: string;
}

export interface RowCountSummary {
  sourceRows: number;
  destinationRows: number;
  rejected: number;
  duplicated: number;
  partiallyMapped: number;
}

export interface ReconciliationReport {
  reportId: string;
  runId: string;
  checks: ReconciliationCheckResult[];
  overallStatus: "in_progress" | "pass" | "fail";
  rowCountSummary: RowCountSummary | null;
  createdAt: string;
  completedAt: string | null;
}

export interface LineageRow {
  lineageRowId: string;
  sourceRowIndex: number;
  sourceRowKey: string | null;
  destinationRowId: string | null;
  mappingRulesApplied: string[];
  outcome: "confirmed" | "rejected" | "duplicated" | "partially_mapped";
  outcomeDetail: string | null;
}

export interface LineageResponse {
  rows: LineageRow[];
  total: number;
  offset: number;
  limit: number;
}

export interface ReconciliationExport extends ReconciliationReport {
  exportedAt: string;
  lineageRows: LineageRow[];
}

// ── mappers ────────────────────────────────────────────────────────────────

function mapReport(r: Record<string, unknown>): ReconciliationReport {
  const summary = r.row_count_summary as Record<string, number> | null;
  return {
    reportId: r.report_id as string,
    runId: r.run_id as string,
    checks: (r.checks as Array<Record<string, string>>).map((c) => ({
      checkName: c.check_name,
      status: c.status as "pass" | "fail",
      detail: c.detail,
    })),
    overallStatus: r.overall_status as ReconciliationReport["overallStatus"],
    rowCountSummary: summary
      ? {
          sourceRows: summary.source_rows,
          destinationRows: summary.destination_rows,
          rejected: summary.rejected,
          duplicated: summary.duplicated,
          partiallyMapped: summary.partially_mapped,
        }
      : null,
    createdAt: r.created_at as string,
    completedAt: (r.completed_at as string | null) ?? null,
  };
}

function mapLineageRow(r: Record<string, unknown>): LineageRow {
  return {
    lineageRowId: r.lineage_row_id as string,
    sourceRowIndex: r.source_row_index as number,
    sourceRowKey: (r.source_row_key as string | null) ?? null,
    destinationRowId: (r.destination_row_id as string | null) ?? null,
    mappingRulesApplied: (r.mapping_rules_applied as string[]) ?? [],
    outcome: r.outcome as LineageRow["outcome"],
    outcomeDetail: (r.outcome_detail as string | null) ?? null,
  };
}

// ── API calls ──────────────────────────────────────────────────────────────

export async function triggerReconciliation(
  projectId: string, runId: string
): Promise<ReconciliationReport> {
  const r = await jsonRequest<Record<string, unknown>>(
    `POST /projects/${projectId}/runs/${runId}/reconciliation`, {}
  );
  return mapReport(r);
}

export async function getLatestReport(
  projectId: string, runId: string
): Promise<ReconciliationReport> {
  const r = await jsonRequest<Record<string, unknown>>(
    `GET /projects/${projectId}/runs/${runId}/reconciliation`
  );
  return mapReport(r);
}

export async function getLineage(
  projectId: string, runId: string, reportId: string,
  opts: { offset?: number; limit?: number; outcome?: string; sourceRowIndex?: number } = {}
): Promise<LineageResponse> {
  const params = new URLSearchParams();
  if (opts.offset !== undefined) params.set("offset", String(opts.offset));
  if (opts.limit !== undefined) params.set("limit", String(opts.limit));
  if (opts.outcome) params.set("outcome", opts.outcome);
  if (opts.sourceRowIndex !== undefined) params.set("source_row_index", String(opts.sourceRowIndex));
  const r = await jsonRequest<{ rows: Record<string, unknown>[]; total: number; offset: number; limit: number }>(
    `GET /projects/${projectId}/runs/${runId}/reconciliation/${reportId}/lineage?${params}`
  );
  return { rows: r.rows.map(mapLineageRow), total: r.total, offset: r.offset, limit: r.limit };
}

export async function exportReport(
  projectId: string, runId: string, reportId: string
): Promise<ReconciliationExport> {
  const r = await jsonRequest<Record<string, unknown>>(
    `GET /projects/${projectId}/runs/${runId}/reconciliation/${reportId}/export`
  );
  return {
    ...mapReport(r),
    exportedAt: r.exported_at as string,
    lineageRows: (r.lineage_rows as Array<Record<string, unknown>>).map(mapLineageRow),
  };
}
```

## UI page (`web/app/runs/[id]/reconciliation/page.tsx`)

Layout matches stitch `11-reconciliation-lineage.md`: status banner at top, failed checks
pinned above passing checks, row-count summary cards, lineage explorer with drill-down.

```tsx
"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AlertTriangle, CheckCircle2, Download } from "lucide-react";
import { Topbar } from "../../../../components/Topbar";
import { loadUiSession, type UiSession } from "../../../../lib/session";
import {
  triggerReconciliation, getLatestReport, getLineage, exportReport,
  type ReconciliationReport, type LineageRow, type LineageResponse,
} from "../../../../lib/reconciliation-api";

type SelectedRow = { sourceRowIndex: number } | null;

export default function ReconciliationPage() {
  const { id: runId } = useParams<{ id: string }>();
  const projectId = ""; // derive from run context or pass via query param

  const [session, setSession] = useState<UiSession | null>(null);
  const [report, setReport] = useState<ReconciliationReport | null>(null);
  const [lineage, setLineage] = useState<LineageResponse | null>(null);
  const [selectedRow, setSelectedRow] = useState<SelectedRow>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      const s = await loadUiSession();
      setSession(s);
      try {
        const r = await getLatestReport(projectId, runId);
        setReport(r);
        const l = await getLineage(projectId, runId, r.reportId, { limit: 100 });
        setLineage(l);
      } catch {
        // no report yet — page shows trigger button only
      } finally {
        setLoading(false);
      }
    })();
  }, [runId, projectId]);

  async function handleTrigger() {
    setTriggering(true);
    setErrorMessage(null);
    try {
      const r = await triggerReconciliation(projectId, runId);
      setReport(r);
      const l = await getLineage(projectId, runId, r.reportId, { limit: 100 });
      setLineage(l);
    } catch (e: unknown) {
      setErrorMessage(e instanceof Error ? e.message : "Failed to trigger reconciliation.");
    } finally {
      setTriggering(false);
    }
  }

  async function handleDrillDown(sourceRowIndex: number) {
    if (!report) return;
    setSelectedRow({ sourceRowIndex });
    const l = await getLineage(projectId, runId, report.reportId, { sourceRowIndex });
    setLineage(l);
  }

  async function handleClearSelection() {
    if (!report) return;
    setSelectedRow(null);
    const l = await getLineage(projectId, runId, report.reportId, { limit: 100 });
    setLineage(l);
  }

  function handleDownload() {
    if (!report) return;
    void exportReport(projectId, runId, report.reportId).then((data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `reconciliation-${report.reportId}.json`;
      a.click();
      URL.revokeObjectURL(url);
    });
  }

  // Sort checks: failed first, then passing
  const sortedChecks = report
    ? [...report.checks].sort((a, b) =>
        a.status === "fail" && b.status !== "fail" ? -1
        : b.status === "fail" && a.status !== "fail" ? 1
        : 0
      )
    : [];

  const isCentralTeam = session?.role === "central_team";

  return (
    <div className="min-h-screen bg-surface">
      <Topbar session={session} />

      <main className="mx-auto max-w-6xl px-6 py-8 space-y-6">
        {/* Page header + action buttons */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-neutral">
              Run {runId}
            </p>
            <h1 className="text-lg font-bold uppercase tracking-tight">Reconciliation & Lineage</h1>
          </div>
          <div className="flex items-center gap-2">
            {report && (
              <button
                className="flex items-center gap-1.5 rounded border border-outline-variant bg-surface px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-surface-container"
                onClick={handleDownload}
                type="button"
              >
                <Download className="h-3.5 w-3.5" />
                Download
              </button>
            )}
            {isCentralTeam && (
              <button
                className="rounded bg-primary px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                disabled={triggering}
                onClick={() => { void handleTrigger(); }}
                type="button"
              >
                {triggering ? "Running…" : report ? "Re-run Reconciliation" : "Run Reconciliation"}
              </button>
            )}
          </div>
        </div>

        {errorMessage && (
          <div className="rounded border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-600">
            {errorMessage}
          </div>
        )}

        {loading && <p className="text-sm text-neutral font-mono">Loading…</p>}

        {!loading && !report && (
          <p className="text-sm text-neutral font-mono">
            No reconciliation report yet.{isCentralTeam ? " Click "Run Reconciliation" to start." : ""}
          </p>
        )}

        {report && (
          <>
            {/* Overall status banner */}
            <div
              className={`rounded-2xl border p-5 ${
                report.overallStatus === "pass"
                  ? "border-emerald-500/20 bg-emerald-500/10"
                  : report.overallStatus === "fail"
                    ? "border-red-500/20 bg-red-500/10"
                    : "border-outline-variant bg-surface-container"
              }`}
            >
              <div className="flex items-center gap-3">
                {report.overallStatus === "pass" ? (
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                ) : report.overallStatus === "fail" ? (
                  <AlertTriangle className="h-5 w-5 text-red-500" />
                ) : null}
                <div>
                  <p className="text-sm font-bold uppercase font-mono">
                    {report.overallStatus === "pass"
                      ? "All checks passed"
                      : report.overallStatus === "fail"
                        ? "Reconciliation failed"
                        : "In progress…"}
                  </p>
                  <p className="mt-0.5 text-[10px] text-neutral font-mono">
                    Infrastructure success is not logical success — all checks must pass independently.
                  </p>
                </div>
              </div>
            </div>

            {/* Check results — failed pinned to top */}
            <div className="rounded-2xl border border-outline-variant bg-surface-container p-5 shadow-sm space-y-3">
              <h2 className="text-[9px] font-mono font-bold uppercase tracking-widest text-neutral">
                Check Results
              </h2>
              <div className="space-y-2">
                {sortedChecks.map((check) => (
                  <div
                    key={check.checkName}
                    className={`flex items-start gap-3 rounded border px-3 py-2.5 ${
                      check.status === "fail"
                        ? "border-red-500/10 bg-red-500/5 text-red-600"
                        : "border-outline-variant bg-surface text-slate-700"
                    }`}
                  >
                    {check.status === "fail" ? (
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-red-500" />
                    ) : (
                      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-emerald-500" />
                    )}
                    <div>
                      <p className="text-[10px] font-bold uppercase font-mono">{check.checkName.replace(/_/g, " ")}</p>
                      <p className="mt-0.5 text-[10px] text-neutral font-mono">{check.detail}</p>
                    </div>
                    <span
                      className={`ml-auto rounded px-2 py-0.5 text-[9px] font-bold uppercase font-mono ${
                        check.status === "fail"
                          ? "bg-red-500/10 text-red-500"
                          : "bg-emerald-500/10 text-emerald-600"
                      }`}
                    >
                      {check.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Row-count summary cards */}
            {report.rowCountSummary && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                {(
                  [
                    { label: "Source Rows", value: report.rowCountSummary.sourceRows, color: "text-slate-700" },
                    { label: "Destination Rows", value: report.rowCountSummary.destinationRows, color: "text-emerald-600" },
                    { label: "Rejected", value: report.rowCountSummary.rejected, color: "text-red-500" },
                    { label: "Duplicated", value: report.rowCountSummary.duplicated, color: "text-amber-500" },
                    { label: "Partially Mapped", value: report.rowCountSummary.partiallyMapped, color: "text-indigo-600" },
                  ] as const
                ).map(({ label, value, color }) => (
                  <div key={label} className="rounded-2xl border border-outline-variant bg-surface-container p-4 shadow-sm text-center">
                    <p className={`text-xl font-bold font-mono ${color}`}>{value.toLocaleString()}</p>
                    <p className="mt-1 text-[9px] font-mono font-semibold uppercase tracking-widest text-neutral">{label}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Lineage explorer */}
            <div className="rounded-2xl border border-outline-variant bg-surface-container p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-[9px] font-mono font-bold uppercase tracking-widest text-neutral">
                  Lineage Explorer
                </h2>
                {selectedRow && (
                  <button
                    className="text-[10px] font-mono text-primary underline"
                    onClick={() => { void handleClearSelection(); }}
                    type="button"
                  >
                    Clear selection
                  </button>
                )}
              </div>

              {selectedRow && (
                <div className="rounded border border-indigo-200/40 bg-indigo-50 px-3 py-2 text-[10px] font-mono text-indigo-700">
                  Showing destination row(s) for source row #{selectedRow.sourceRowIndex}
                </div>
              )}

              {lineage && lineage.rows.length === 0 && (
                <p className="text-[10px] font-mono text-neutral">No lineage rows found.</p>
              )}

              {lineage && lineage.rows.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-[11px]">
                    <thead>
                      <tr className="border-b border-outline-variant text-[9px] font-mono font-bold uppercase tracking-wider text-neutral">
                        <th className="px-3 py-2 text-left">Src Row</th>
                        <th className="px-3 py-2 text-left">Src Key</th>
                        <th className="px-3 py-2 text-left">Dst Row ID</th>
                        <th className="px-3 py-2 text-left">Mapping Rules</th>
                        <th className="px-3 py-2 text-left">Outcome</th>
                        <th className="px-3 py-2 text-left">Detail</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lineage.rows.map((row) => (
                        <tr
                          key={row.lineageRowId}
                          className={`border-b border-outline-variant/50 cursor-pointer transition-colors hover:bg-surface ${
                            selectedRow?.sourceRowIndex === row.sourceRowIndex
                              ? "bg-indigo-50"
                              : ""
                          }`}
                          onClick={() => { void handleDrillDown(row.sourceRowIndex); }}
                        >
                          <td className="px-3 py-2 font-mono">{row.sourceRowIndex}</td>
                          <td className="px-3 py-2 font-mono text-slate-500">{row.sourceRowKey ?? "—"}</td>
                          <td className="px-3 py-2 font-mono text-slate-500">{row.destinationRowId ?? "—"}</td>
                          <td className="px-3 py-2">
                            <div className="flex flex-wrap gap-1">
                              {row.mappingRulesApplied.map((rule) => (
                                <span key={rule} className="rounded bg-surface-container border border-outline-variant px-1.5 py-0.5 font-mono text-[9px] text-neutral">
                                  {rule}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="px-3 py-2">
                            <OutcomeChip outcome={row.outcome} />
                          </td>
                          <td className="px-3 py-2 font-mono text-[10px] text-slate-500">{row.outcomeDetail ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {lineage.total > lineage.rows.length && (
                    <p className="mt-2 text-[10px] font-mono text-neutral px-3">
                      Showing {lineage.rows.length} of {lineage.total} rows.
                    </p>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function OutcomeChip({ outcome }: { outcome: LineageRow["outcome"] }) {
  const styles: Record<LineageRow["outcome"], string> = {
    confirmed: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20",
    rejected: "bg-red-500/10 text-red-500 border-red-500/20",
    duplicated: "bg-amber-500/10 text-amber-600 border-amber-500/20",
    partially_mapped: "bg-indigo-50 text-indigo-600 border-indigo-200/40",
  };
  return (
    <span className={`rounded border px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase ${styles[outcome]}`}>
      {outcome.replace(/_/g, " ")}
    </span>
  );
}
```

## UI tests (`web/app/runs/[id]/reconciliation/page.test.tsx`)

```typescript
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import ReconciliationPage from "./page";
import * as api from "../../../../lib/reconciliation-api";

vi.mock("next/navigation", () => ({ useParams: () => ({ id: "run_test_001" }) }));
vi.mock("../../../../lib/session", () => ({ loadUiSession: vi.fn(() => Promise.resolve({ role: "central_team" })) }));
vi.mock("../../../../lib/reconciliation-api");

const mockReport = {
  reportId: "rpt_001",
  runId: "run_test_001",
  checks: [
    { checkName: "row_count", status: "pass" as const, detail: "3 == 3" },
    { checkName: "key_integrity", status: "fail" as const, detail: "1 of 3 keys missing" },
  ],
  overallStatus: "fail" as const,
  rowCountSummary: { sourceRows: 3, destinationRows: 2, rejected: 1, duplicated: 0, partiallyMapped: 0 },
  createdAt: "2026-07-01T00:00:00Z",
  completedAt: "2026-07-01T00:00:05Z",
};

const mockLineage = {
  rows: [
    {
      lineageRowId: "lr_001", sourceRowIndex: 0, sourceRowKey: "C001",
      destinationRowId: "D001", mappingRulesApplied: ["customer_id → id"],
      outcome: "confirmed" as const, outcomeDetail: null,
    },
    {
      lineageRowId: "lr_002", sourceRowIndex: 1, sourceRowKey: "C002",
      destinationRowId: null, mappingRulesApplied: [],
      outcome: "rejected" as const, outcomeDetail: "Missing lookup value",
    },
  ],
  total: 2, offset: 0, limit: 100,
};

beforeEach(() => {
  vi.mocked(api.getLatestReport).mockResolvedValue(mockReport);
  vi.mocked(api.getLineage).mockResolvedValue(mockLineage);
});

describe("ReconciliationPage", () => {
  it("renders overall fail banner", async () => {
    render(<ReconciliationPage />);
    await screen.findByText("Reconciliation failed");
    expect(screen.getByText(/Infrastructure success is not logical success/)).toBeInTheDocument();
  });

  it("pins failed checks above passing checks", async () => {
    render(<ReconciliationPage />);
    await screen.findByText("Reconciliation failed");
    const chips = screen.getAllByRole("generic").filter(
      (el) => el.textContent === "fail" || el.textContent === "pass"
    );
    // First chip must be "fail" (key_integrity is failed, pinned first)
    expect(chips[0].textContent).toBe("fail");
  });

  it("renders row-count summary cards", async () => {
    render(<ReconciliationPage />);
    await screen.findByText("Source Rows");
    expect(screen.getByText("3")).toBeInTheDocument();  // source rows
    expect(screen.getByText("1")).toBeInTheDocument();  // rejected
  });

  it("renders lineage table with outcome chips", async () => {
    render(<ReconciliationPage />);
    await screen.findByText("Lineage Explorer");
    expect(screen.getByText("confirmed")).toBeInTheDocument();
    expect(screen.getByText("rejected")).toBeInTheDocument();
  });

  it("drill-down: clicking a row filters lineage by source_row_index", async () => {
    const drillLineage = { rows: [mockLineage.rows[0]], total: 1, offset: 0, limit: 100 };
    vi.mocked(api.getLineage)
      .mockResolvedValueOnce(mockLineage)        // initial load
      .mockResolvedValueOnce(drillLineage);       // drill-down
    render(<ReconciliationPage />);
    await screen.findByText("C001");
    fireEvent.click(screen.getByText("C001").closest("tr")!);
    await waitFor(() => {
      expect(vi.mocked(api.getLineage)).toHaveBeenCalledWith(
        expect.any(String), "run_test_001", "rpt_001",
        expect.objectContaining({ sourceRowIndex: 0 })
      );
    });
  });

  it("shows 'Clear selection' button after drill-down", async () => {
    vi.mocked(api.getLineage).mockResolvedValue(mockLineage);
    render(<ReconciliationPage />);
    await screen.findByText("C001");
    fireEvent.click(screen.getByText("C001").closest("tr")!);
    await screen.findByText("Clear selection");
  });

  it("hides Re-run button for read_only_auditor", async () => {
    vi.mocked(require("../../../../lib/session").loadUiSession).mockResolvedValue({ role: "read_only_auditor" });
    render(<ReconciliationPage />);
    await screen.findByText("Reconciliation failed");
    expect(screen.queryByText(/Re-run/)).toBeNull();
  });

  it("Download button calls exportReport and triggers file download", async () => {
    vi.mocked(api.exportReport).mockResolvedValue({
      ...mockReport,
      exportedAt: "2026-07-01T00:01:00Z",
      lineageRows: mockLineage.rows,
    });
    const createObjectURL = vi.fn(() => "blob:test");
    const revokeObjectURL = vi.fn();
    global.URL.createObjectURL = createObjectURL;
    global.URL.revokeObjectURL = revokeObjectURL;
    render(<ReconciliationPage />);
    await screen.findByText("Download");
    fireEvent.click(screen.getByText("Download"));
    await waitFor(() => expect(api.exportReport).toHaveBeenCalledWith("", "run_test_001", "rpt_001"));
  });

  it("shows no-report message when no report exists", async () => {
    vi.mocked(api.getLatestReport).mockRejectedValue(new Error("404"));
    render(<ReconciliationPage />);
    await screen.findByText(/No reconciliation report yet/);
  });
});
```

## Docs update (`docs/domain/runs.md`)

Add to the end of the `## Reconciliation and lineage` section:

```markdown
### Reconciliation report schema

A `ReconciliationReport` is the persisted record of a reconciliation run:

- `report_id` — UUID
- `run_id` — links to the RunRecord
- `checks` — ordered list of `{check_name, status: "pass"|"fail", detail}` results;
  failed checks are displayed pinned to the top of the evidence screen
- `overall_status` — `"in_progress"` | `"pass"` | `"fail"`;
  set to `"fail"` if any check fails
- `row_count_summary` — `{source_rows, destination_rows, rejected, duplicated, partially_mapped}`
- `created_at`, `completed_at`

Re-running reconciliation creates a new `ReconciliationReport`; old reports are retained
for audit. The most-recent report is the canonical status.

### Lineage evidence schema

A `ReconciliationLineageRow` links one source row to its destination outcome:

- `lineage_row_id`, `report_id`, `run_id`
- `source_row_index` — position of the row in the approved `SourceSlice`
- `source_row_key` — primary key value from the source row (for drill-down display)
- `destination_row_id` — the destination record identifier; `null` for rejected rows
- `mapping_rules_applied` — list of `"src_field → dst_field"` strings used
- `outcome` — `"confirmed"` | `"rejected"` | `"duplicated"` | `"partially_mapped"`
- `outcome_detail` — human-readable reason for non-confirmed outcomes

The lineage explorer on the Reconciliation & Lineage screen allows a reviewer to
select any source row and see its destination row(s) and the mapping rules applied.
The reconciliation evidence export bundles the full report and all lineage rows as
a single JSON artifact for offline audit.
```

## Implementation order

1. **Migration 0015** — confirm `down_revision` matches `0014_run_record_lookup_snapshot_versions`;
   add `ReconciliationReport` + `ReconciliationLineageRow` to `models.py`; write and run migration.
   `cd engine && alembic upgrade head`. Commit.

2. **Management service** — `management/reconciliation.py` with all 5 functions + `_build_lineage_rows`.
   Write and run backend tests: `pytest engine/tests/test_reconciliation_api.py -v`. Commit.

3. **Routes + registration** — `routes/reconciliation.py` + `app.py` router include. Re-run tests. Commit.

4. **Frontend types** — `web/lib/reconciliation-api.ts`. Compile-check: `pnpm --filter web tsc --noEmit`. Commit.

5. **UI page** — `web/app/runs/[id]/reconciliation/page.tsx` + tests. Run `pnpm --filter web test`. Commit.

6. **Docs update** — extend `docs/domain/runs.md`. Commit.

7. Final: `pnpm --filter web build` — zero TS/lint errors.

## Verification checklist

- [ ] `alembic upgrade head` succeeds from a clean state
- [ ] `pytest engine/tests/test_reconciliation_api.py -v` — all tests green
- [ ] `POST .../reconciliation` returns 403 for `read_only_auditor`
- [ ] `POST .../reconciliation` returns 422 when gate_2 not approved
- [ ] `GET .../reconciliation` returns 200 for `read_only_auditor`
- [ ] `GET .../reconciliation/{report_id}/export` returns 200 for `read_only_auditor`
- [ ] Lineage drill-down: `GET .../lineage?source_row_index=0` returns exactly the matching rows
- [ ] `pnpm --filter web test` — all UI tests green
- [ ] Failed checks rendered above passing checks in UI
- [ ] Download button produces a `.json` file containing `checks` and `lineage_rows`
- [ ] "Re-run Reconciliation" button hidden for `read_only_auditor` session
- [ ] `pnpm --filter web build` — zero TS errors
