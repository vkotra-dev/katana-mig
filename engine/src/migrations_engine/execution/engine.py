from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..db.models import (
    LookupSnapshot,
    MappingSnapshot,
    RunRecord,
    FeedSlice,
)
from ..management.platform import record_management_audit
from .checkpoints import get_latest_checkpoint, list_checkpoints_for_run
from .inner_loop import process_inner_loop

CHECKPOINT_INTERVAL = 500


def _require_run(db: Session, *, run_id: str, project_id: str) -> RunRecord:
    run = db.scalar(select(RunRecord).where(RunRecord.run_id == run_id, RunRecord.project_id == project_id))
    if run is None:
        raise AuthApiError("run_not_found", "Run not found.", 404)
    return run


def _select_latest_approved_source_slice(db: Session, *, source_definition_id: str) -> FeedSlice:
    source_slice = db.scalar(
        select(FeedSlice)
        .where(
            FeedSlice.source_definition_id == source_definition_id,
            FeedSlice.status == "approved",
        )
        .order_by(FeedSlice.approved_at.desc().nullslast(), FeedSlice.created_at.desc())
    )
    if source_slice is None:
        raise ValueError("missing_source_slice")
    return source_slice


def _select_latest_approved_mapping_snapshot(db: Session, *, project_id: str, destination_object_name: str) -> MappingSnapshot:
    mapping_snapshot = db.scalar(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.destination_object_name == destination_object_name,
            MappingSnapshot.status == "approved",
        )
        .order_by(MappingSnapshot.approved_at.desc().nullslast(), MappingSnapshot.created_at.desc())
    )
    if mapping_snapshot is None:
        raise ValueError("missing_mapping_snapshot")
    return mapping_snapshot


def _select_latest_approved_lookup_snapshot(db: Session, *, project_id: str, lookup_name: str) -> LookupSnapshot:
    lookup_snapshot = db.scalar(
        select(LookupSnapshot)
        .where(
            LookupSnapshot.project_id == project_id,
            LookupSnapshot.lookup_name == lookup_name,
            LookupSnapshot.status == "approved",
        )
        .order_by(LookupSnapshot.approved_at.desc().nullslast(), LookupSnapshot.created_at.desc())
    )
    if lookup_snapshot is None:
        raise ValueError("missing_lookup_snapshot")
    return lookup_snapshot


def _serialize_run(run: RunRecord, *, last_checkpoint_at: datetime | None = None) -> dict[str, Any]:
    started_at = None
    if run.start_metadata and run.start_metadata.get("started_at"):
        started_at = datetime.fromisoformat(str(run.start_metadata["started_at"]))
    return {
        "run_id": run.run_id,
        "project_id": run.project_id,
        "destination_object_name": run.destination_object_name,
        "source_definition_reference": run.source_definition_reference,
        "environment": run.environment,
        "status": run.status,
        "current_stage": run.current_stage,
        "source_slice_version": run.source_slice_version,
        "mapping_snapshot_version": run.mapping_snapshot_version,
        "lookup_snapshot_version": run.lookup_snapshot_version,
        "lookup_snapshot_versions": run.lookup_snapshot_versions,
        "code_generation_input_snapshot_version": run.code_generation_input_snapshot_version,
        "codegen_artifact_id": run.codegen_artifact_id,
        "knowledge_freeze_version": run.knowledge_freeze_version,
        "start_metadata": run.start_metadata,
        "pause_metadata": run.pause_metadata,
        "resume_metadata": run.resume_metadata,
        "completion_metadata": run.completion_metadata,
        "started_at": started_at,
        "last_checkpoint_at": last_checkpoint_at,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def _latest_checkpoint_timestamp(db: Session, *, run_id: str) -> datetime | None:
    checkpoint = get_latest_checkpoint(db, run_id=run_id)
    if checkpoint is None:
        return None
    return checkpoint.created_at


def list_runs_for_project(db: Session, *, project_id: str) -> list[dict[str, Any]]:
    runs = list(
        db.scalars(
            select(RunRecord)
            .where(RunRecord.project_id == project_id)
            .order_by(RunRecord.created_at.desc(), RunRecord.updated_at.desc())
        )
    )
    return [_serialize_run(run, last_checkpoint_at=_latest_checkpoint_timestamp(db, run_id=run.run_id)) for run in runs]


def get_run(db: Session, *, project_id: str, run_id: str) -> dict[str, Any]:
    run = _require_run(db, run_id=run_id, project_id=project_id)
    return _serialize_run(run, last_checkpoint_at=_latest_checkpoint_timestamp(db, run_id=run.run_id))


def list_run_checkpoints(db: Session, *, project_id: str, run_id: str) -> list[dict[str, Any]]:
    run = _require_run(db, run_id=run_id, project_id=project_id)
    _ = run
    checkpoints = list_checkpoints_for_run(db, run_id=run_id)
    return [
        {
            "run_checkpoint_id": checkpoint.run_checkpoint_id,
            "run_id": checkpoint.run_id,
            "current_stage": checkpoint.current_stage,
            "current_object": checkpoint.current_object,
            "current_environment": checkpoint.current_environment,
            "approved_snapshots": checkpoint.approved_snapshots,
            "last_completed_checkpoint_boundary": checkpoint.last_completed_checkpoint_boundary,
            "last_completed_row": (checkpoint.checkpoint_payload or {}).get("last_completed_row"),
            "pause_reason": checkpoint.pause_reason,
            "created_at": checkpoint.created_at,
        }
        for checkpoint in checkpoints
    ]


def _pin_run(
    run: RunRecord,
    *,
    source_slice: FeedSlice,
    mapping_snapshot: MappingSnapshot,
    lookup_snapshot_versions: dict[str, str],
    resume: bool,
) -> None:
    lookup_snapshot_version = _primary_lookup_snapshot_version(lookup_snapshot_versions)
    run.source_slice_version = source_slice.source_slice_version
    run.mapping_snapshot_version = mapping_snapshot.mapping_snapshot_version
    run.lookup_snapshot_version = lookup_snapshot_version
    run.lookup_snapshot_versions = lookup_snapshot_versions or None
    run.code_generation_input_snapshot_version = source_slice.source_slice_version
    run.current_stage = "mapping"
    if resume:
        run.resume_metadata = {
            "resumed_at": datetime.now(UTC).isoformat(),
            "source_slice_version": source_slice.source_slice_version,
            "mapping_snapshot_version": mapping_snapshot.mapping_snapshot_version,
            "lookup_snapshot_versions": lookup_snapshot_versions,
            "lookup_snapshot_version": lookup_snapshot_version,
        }
    elif run.start_metadata is None:
        run.start_metadata = {
            "started_at": datetime.now(UTC).isoformat(),
            "source_slice_version": source_slice.source_slice_version,
            "mapping_snapshot_version": mapping_snapshot.mapping_snapshot_version,
            "lookup_snapshot_versions": lookup_snapshot_versions,
            "lookup_snapshot_version": lookup_snapshot_version,
        }


def _primary_lookup_snapshot_version(lookup_snapshot_versions: dict[str, str]) -> str | None:
    unique_versions = set(lookup_snapshot_versions.values())
    if len(unique_versions) == 1:
        return next(iter(unique_versions))
    return None


def execute_run(
    db: Session,
    *,
    project_id: str,
    run_id: str,
    actor_user_id: str | None,
    resume: bool = False,
    checkpoint_interval: int = CHECKPOINT_INTERVAL,
) -> dict[str, Any]:
    run = _require_run(db, run_id=run_id, project_id=project_id)
    if not resume and run.status != "queued":
        raise AuthApiError("run_not_launchable", "Run is not launchable.", 409)
    if resume and run.status not in {"paused", "awaiting_approval"}:
        raise AuthApiError("run_not_resumable", "Run is not resumable.", 409)

    source_definition_id = run.source_definition_reference
    if source_definition_id is None:
        raise AuthApiError("missing_source_slice", "A source slice is required.", 409)

    try:
        source_slice = _select_latest_approved_source_slice(db, source_definition_id=source_definition_id)
        mapping_snapshot = _select_latest_approved_mapping_snapshot(
            db,
            project_id=run.project_id,
            destination_object_name=run.destination_object_name,
        )
        lookup_names = sorted(
            {
                str(binding["lookup_name"])
                for binding in mapping_snapshot.field_bindings
                if binding.get("lookup_name") is not None
            }
        )
        lookup_snapshots = {
            lookup_name: _select_latest_approved_lookup_snapshot(
                db,
                project_id=run.project_id,
                lookup_name=lookup_name,
            )
            for lookup_name in lookup_names
        }
    except ValueError as exc:
        error_code = str(exc)
        if error_code in {"missing_source_slice", "missing_mapping_snapshot", "missing_lookup_snapshot"}:
            raise AuthApiError(error_code, "Required approved artifact is missing.", 409) from exc
        raise

    _pin_run(
        run,
        source_slice=source_slice,
        mapping_snapshot=mapping_snapshot,
        lookup_snapshot_versions={
            lookup_name: snapshot.lookup_snapshot_version for lookup_name, snapshot in lookup_snapshots.items()
        },
        resume=resume,
    )
    run.status = "running"
    db.flush()
    record_management_audit(
        db,
        project_id=run.project_id,
        actor_user_id=actor_user_id,
        event_type="run_started" if not resume else "run_resumed",
        payload={
            "run_id": run.run_id,
            "source_slice_version": run.source_slice_version,
            "mapping_snapshot_version": run.mapping_snapshot_version,
            "lookup_snapshot_version": run.lookup_snapshot_version,
            "lookup_snapshot_versions": run.lookup_snapshot_versions,
        },
    )

    start_row_index = 0
    if resume:
        checkpoint = get_latest_checkpoint(db, run_id=run.run_id)
        if checkpoint is not None and checkpoint.checkpoint_payload is not None:
            last_completed_row = checkpoint.checkpoint_payload.get("last_completed_row")
            if isinstance(last_completed_row, int):
                start_row_index = last_completed_row + 1
    result = process_inner_loop(
        db,
        run=run,
        source_slice=source_slice,
        mapping_snapshot=mapping_snapshot,
        lookup_snapshots=lookup_snapshots,
        start_row_index=start_row_index,
        actor_user_id=actor_user_id,
        checkpoint_interval=checkpoint_interval,
    )
    if result.paused:
        db.commit()
        return _serialize_run(run, last_checkpoint_at=_latest_checkpoint_timestamp(db, run_id=run.run_id))

    run.status = "completed"
    run.completion_metadata = {
        "processed_rows": result.processed_rows,
        "last_completed_row": result.last_completed_row,
        "source_slice_version": run.source_slice_version,
        "mapping_snapshot_version": run.mapping_snapshot_version,
        "lookup_snapshot_version": run.lookup_snapshot_version,
        "lookup_snapshot_versions": run.lookup_snapshot_versions,
    }
    record_management_audit(
        db,
        project_id=run.project_id,
        actor_user_id=actor_user_id,
        event_type="run_completed",
        payload={
            "run_id": run.run_id,
            "processed_rows": result.processed_rows,
            "last_completed_row": result.last_completed_row,
        },
    )
    db.commit()
    return _serialize_run(run, last_checkpoint_at=_latest_checkpoint_timestamp(db, run_id=run.run_id))


def pause_run(db: Session, *, project_id: str, run_id: str, actor_user_id: str | None) -> dict[str, Any]:
    run = _require_run(db, run_id=run_id, project_id=project_id)
    if run.status != "running":
        raise AuthApiError("run_not_pauseable", "Run is not pauseable.", 409)
    checkpoint = get_latest_checkpoint(db, run_id=run_id)
    run.status = "paused"
    run.pause_metadata = {
        "pause_reason": "manual",
        "last_completed_row": (checkpoint.checkpoint_payload or {}).get("last_completed_row") if checkpoint else None,
        "paused_at": datetime.now(UTC).isoformat(),
    }
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="run_paused",
        payload={"run_id": run_id},
    )
    db.commit()
    return _serialize_run(run, last_checkpoint_at=_latest_checkpoint_timestamp(db, run_id=run_id))
