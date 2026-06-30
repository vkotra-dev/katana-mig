from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import (
    SourceAnalysisResponse,
    SourceSchemaColumnResponse,
    SourceValueSummaryResponse,
)
from ..db.models import User
from ..management.access import require_project_access
from ..management.source_analysis import (
    analyze_source_slice,
    get_latest_source_schema_artifact,
    list_source_value_summaries,
)

router = APIRouter(prefix="/projects/{project_id}/sources", tags=["analysis"])


@router.post("/{source_definition_id}/analyze", response_model=SourceAnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
def post_source_analysis(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> SourceAnalysisResponse:
    return analyze_source_slice(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
    )


@router.get("/{source_definition_id}/schema", response_model=list[SourceSchemaColumnResponse])
def get_source_schema(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SourceSchemaColumnResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return get_latest_source_schema_artifact(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
    ).columns


@router.get("/{source_definition_id}/value-summary", response_model=list[SourceValueSummaryResponse])
def get_source_value_summary(
    project_id: str,
    source_definition_id: str,
    field: str | None = Query(default=None),
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SourceValueSummaryResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_source_value_summaries(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        field_name=field,
    )
