"""Version history endpoints — scoped per project."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import get_current_user, get_db
from ..api.schemas import VersionHistoryResponse
from ..db.models import User, VersionHistory
from ..management.access import require_project_access

router = APIRouter(prefix="/projects/{project_id}/versions", tags=["versions"])


def _entity_router(entity_type: str) -> APIRouter:
    r = APIRouter(prefix=f"/{entity_type}")

    @r.get("/versions", response_model=list[VersionHistoryResponse])
    def get_entity_versions(
        project_id: str,
        actor: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        limit: int = Query(default=50, le=200),
        offset: int = Query(default=0, ge=0),
    ) -> list[VersionHistoryResponse]:
        require_project_access(db, user=actor, project_id=project_id)
        rows = (
            db.execute(
                select(VersionHistory)
                .where(VersionHistory.entity_type == entity_type)
                .order_by(VersionHistory.changed_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return rows

    return r


router.include_router(_entity_router("hints"))
router.include_router(_entity_router("codegen"))
router.include_router(_entity_router("transformation"))
router.include_router(_entity_router("sql"))
