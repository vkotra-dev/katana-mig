from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import LineageResponse, ReconciliationExportResponse, ReconciliationReportResponse
from ..db.models import User
from ..management.access import require_project_access
from ..management.reconciliation import export_report, get_latest_report, get_lineage, list_reports, trigger_reconciliation

router = APIRouter(prefix="/projects/{project_id}/runs/{run_id}/reconciliation", tags=["reconciliation"])


@router.post("", response_model=ReconciliationReportResponse, status_code=201)
def post_reconciliation(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> ReconciliationReportResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return trigger_reconciliation(db, project_id=project_id, run_id=run_id)


@router.get("", response_model=ReconciliationReportResponse)
def get_reconciliation(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReconciliationReportResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_latest_report(db, project_id=project_id, run_id=run_id)


@router.get("/history", response_model=list[ReconciliationReportResponse])
def get_reconciliation_history(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReconciliationReportResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_reports(db, project_id=project_id, run_id=run_id)


@router.get("/{report_id}/lineage", response_model=LineageResponse)
def get_reconciliation_lineage(
    project_id: str,
    run_id: str,
    report_id: str,
    offset: int = 0,
    limit: int = 100,
    outcome: str | None = None,
    source_row_index: int | None = None,
    destination_row_id: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LineageResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_lineage(
        db,
        project_id=project_id,
        run_id=run_id,
        report_id=report_id,
        offset=offset,
        limit=limit,
        outcome=outcome,
        source_row_index=source_row_index,
        destination_row_id=destination_row_id,
    )


@router.get("/{report_id}/export", response_model=ReconciliationExportResponse)
def get_reconciliation_export(
    project_id: str,
    run_id: str,
    report_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReconciliationExportResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return export_report(db, project_id=project_id, run_id=run_id, report_id=report_id)
