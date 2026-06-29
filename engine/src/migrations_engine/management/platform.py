from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import AuditEvent, ProjectDefinition, ProjectRegistry, new_id

PLATFORM_PROJECT_ID = "00000000-0000-4000-8000-000000000001"
PLATFORM_DEFINITION_ID = "00000000-0000-4000-8000-000000000002"


def ensure_platform_project(db: Session) -> str:
    if db.get(ProjectRegistry, PLATFORM_PROJECT_ID) is not None:
        return PLATFORM_PROJECT_ID

    db.add(
        ProjectDefinition(
            definition_id=PLATFORM_DEFINITION_ID,
            project_id=PLATFORM_PROJECT_ID,
            name="Platform",
            status="active",
        )
    )
    db.add(
        ProjectRegistry(
            project_id=PLATFORM_PROJECT_ID,
            name="Platform",
            definition_id=PLATFORM_DEFINITION_ID,
            status="active",
        )
    )
    db.flush()
    return PLATFORM_PROJECT_ID


def record_management_audit(
    db: Session,
    *,
    project_id: str,
    actor_user_id: str,
    event_type: str,
    payload: dict[str, object],
) -> None:
    db.add(
        AuditEvent(
            audit_event_id=new_id(),
            project_id=project_id,
            event_type=event_type,
            severity="info",
            actor_user_id=actor_user_id,
            event_payload=payload,
        )
    )
