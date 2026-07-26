"""Version history endpoints — scoped per project."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import get_current_user, get_db
from ..api.schemas import VersionHistoryResponse
from ..db.models import (
    CodeGenerationArtifact,
    Feed,
    User,
    VersionHistory,
)
from ..management.access import require_project_access

router = APIRouter(prefix="/projects/{project_id}/versions", tags=["versions"])


@router.get("/hints/versions", response_model=list[VersionHistoryResponse])
def get_hints_versions(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[VersionHistoryResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    # entity_id for hints = source_definition_id (Feed.primary_key)
    # Join via Feed to verify project ownership
    source_ids = (
        db.execute(
            select(Feed.source_definition_id)
            .where(Feed.project_id == project_id)
        )
        .scalars()
        .all()
    )
    if not source_ids:
        return []
    rows = (
        db.execute(
            select(VersionHistory)
            .where(
                VersionHistory.entity_type == "hints",
                VersionHistory.entity_id.in_(source_ids),
            )
            .order_by(VersionHistory.changed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return rows


@router.get("/transformation/versions", response_model=list[VersionHistoryResponse])
def get_transformation_versions(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[VersionHistoryResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    # entity_id for transformation = source_definition_id (Feed.primary_key)
    source_ids = (
        db.execute(
            select(Feed.source_definition_id)
            .where(Feed.project_id == project_id)
        )
        .scalars()
        .all()
    )
    if not source_ids:
        return []
    rows = (
        db.execute(
            select(VersionHistory)
            .where(
                VersionHistory.entity_type == "transformation",
                VersionHistory.entity_id.in_(source_ids),
            )
            .order_by(VersionHistory.changed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return rows


@router.get("/codegen/versions", response_model=list[VersionHistoryResponse])
def get_codegen_versions(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[VersionHistoryResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    # entity_id for codegen = project_id (direct equality)
    rows = (
        db.execute(
            select(VersionHistory)
            .where(
                VersionHistory.entity_type == "codegen",
                VersionHistory.entity_id == project_id,
            )
            .order_by(VersionHistory.changed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return rows


@router.get("/sql/versions", response_model=list[VersionHistoryResponse])
def get_sql_versions(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[VersionHistoryResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    # entity_id for sql = codegen_artifact_id
    # Join via CodeGenerationArtifact to verify project ownership
    artifact_ids = (
        db.execute(
            select(CodeGenerationArtifact.codegen_artifact_id)
            .where(CodeGenerationArtifact.project_id == project_id)
        )
        .scalars()
        .all()
    )
    if not artifact_ids:
        return []
    rows = (
        db.execute(
            select(VersionHistory)
            .where(
                VersionHistory.entity_type == "sql",
                VersionHistory.entity_id.in_(artifact_ids),
            )
            .order_by(VersionHistory.changed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return rows
