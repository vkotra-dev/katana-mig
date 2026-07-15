from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import AICallLog


def list_ai_calls(
    db: Session,
    *,
    project_id: str,
    call_type: str | None = None,
    artifact_id: str | None = None,
) -> list[AICallLog]:
    q = select(AICallLog).where(AICallLog.project_id == project_id)
    if call_type is not None:
        q = q.where(AICallLog.call_type == call_type)
    if artifact_id is not None:
        q = q.where(AICallLog.artifact_id == artifact_id)
    return list(db.scalars(q.order_by(AICallLog.called_at.desc())).all())
