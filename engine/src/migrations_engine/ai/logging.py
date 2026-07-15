from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..db.models import AICallLog, new_id


def log_ai_call(
    db: Session,
    *,
    project_id: str,
    call_type: str,
    model_id: str,
    system: str,
    user: str,
    raw_response: str | None,
    error_detail: str | None = None,
    artifact_id: str | None = None,
) -> AICallLog:
    """Write one row to ai_call_log. Caller must commit (or flush) the session."""
    entry = AICallLog(
        call_id=new_id(),
        project_id=project_id,
        call_type=call_type,
        model_id=model_id,
        system_prompt=system,
        user_prompt=user,
        raw_response=raw_response,
        error_detail=error_detail,
        artifact_id=artifact_id,
        called_at=datetime.now(UTC),
    )
    db.add(entry)
    db.flush()
    return entry


def backfill_artifact_id(db: Session, call_id: str, artifact_id: str) -> None:
    """Back-fill artifact_id after the artifact is committed."""
    entry = db.get(AICallLog, call_id)
    if entry is not None:
        entry.artifact_id = artifact_id
        db.flush()
