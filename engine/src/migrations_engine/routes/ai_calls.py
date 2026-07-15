from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError, get_current_user, get_db
from ..api.schemas import AICallLogResponse
from ..db.models import User
from ..management.access import require_project_access
from ..management.ai_calls import list_ai_calls
from ..roles import ADMIN_ROLE, CENTRAL_TEAM_ROLE

router = APIRouter(prefix="/projects/{project_id}/ai-calls", tags=["ai-calls"])


@router.get("", response_model=list[AICallLogResponse])
def get_ai_calls(
    project_id: str,
    call_type: str | None = None,
    artifact_id: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AICallLogResponse]:
    if actor.role not in {ADMIN_ROLE, CENTRAL_TEAM_ROLE}:
        raise AuthApiError("forbidden", "Admin or central team access required.", 403)
    require_project_access(db, user=actor, project_id=project_id)
    rows = list_ai_calls(db, project_id=project_id, call_type=call_type, artifact_id=artifact_id)
    return [
        AICallLogResponse(
            call_id=r.call_id,
            call_type=r.call_type,
            artifact_id=r.artifact_id,
            model_id=r.model_id,
            system_prompt=r.system_prompt,
            user_prompt=r.user_prompt,
            raw_response=r.raw_response,
            error_detail=r.error_detail,
            called_at=r.called_at,
        )
        for r in rows
    ]
