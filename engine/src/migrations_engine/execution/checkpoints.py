from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import RunCheckpoint, RunRecord, new_id


def write_checkpoint(
    db: Session,
    *,
    run: RunRecord,
    current_object: str,
    current_environment: str | None,
    approved_snapshots: dict[str, Any],
    last_completed_row: int | None,
    pause_reason: str | None = None,
) -> RunCheckpoint:
    checkpoint = RunCheckpoint(
        run_checkpoint_id=new_id(),
        run_id=run.run_id,
        current_stage=run.current_stage,
        current_object=current_object,
        current_environment=current_environment,
        approved_snapshots=approved_snapshots,
        last_completed_checkpoint_boundary=str(last_completed_row) if last_completed_row is not None else None,
        pause_reason=pause_reason,
        checkpoint_payload={"last_completed_row": last_completed_row},
    )
    db.add(checkpoint)
    db.flush()
    return checkpoint


def get_latest_checkpoint(db: Session, *, run_id: str) -> RunCheckpoint | None:
    return db.scalar(
        select(RunCheckpoint)
        .where(RunCheckpoint.run_id == run_id)
        .order_by(RunCheckpoint.created_at.desc(), RunCheckpoint.updated_at.desc())
    )


def list_checkpoints_for_run(db: Session, *, run_id: str) -> list[RunCheckpoint]:
    return list(
        db.scalars(
            select(RunCheckpoint)
            .where(RunCheckpoint.run_id == run_id)
            .order_by(RunCheckpoint.created_at.asc(), RunCheckpoint.updated_at.asc())
        )
    )
