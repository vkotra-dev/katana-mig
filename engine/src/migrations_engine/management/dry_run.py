from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import DryRunArtifactResponse, PushBackRequest, RunResponse
from ..db.models import DryRunArtifact, RunRecord
from ..management.platform import record_management_audit


def _get_run_or_404(db: Session, *, project_id: str, run_id: str) -> RunRecord:
    run = db.scalar(select(RunRecord).where(RunRecord.run_id == run_id, RunRecord.project_id == project_id))
    if run is None:
        raise AuthApiError("run_not_found", "Run not found.", 404)
    return run


def _get_artifact_or_404(db: Session, *, project_id: str, run_id: str) -> DryRunArtifact:
    artifact = db.scalar(
        select(DryRunArtifact).where(
            DryRunArtifact.run_id == run_id,
            DryRunArtifact.project_id == project_id,
        )
    )
    if artifact is None:
        raise AuthApiError("dry_run_artifact_not_found", "No dry-run artifact found for this run.", 404)
    return artifact


def get_dry_run_artifact(db: Session, *, project_id: str, run_id: str) -> DryRunArtifactResponse:
    _get_run_or_404(db, project_id=project_id, run_id=run_id)
    artifact = _get_artifact_or_404(db, project_id=project_id, run_id=run_id)
    return DryRunArtifactResponse(
        dry_run_artifact_id=artifact.dry_run_artifact_id,
        run_id=artifact.run_id,
        project_id=artifact.project_id,
        destination_object_name=artifact.destination_object_name,
        success_count=artifact.success_count,
        failure_count=artifact.failure_count,
        field_coverage_pct=artifact.field_coverage_pct,
        pii_fields=artifact.pii_fields,
        sample_rows=artifact.sample_rows,
        failures=artifact.failures,
        push_back_comment=artifact.push_back_comment,
        status=artifact.status,
        created_at=artifact.created_at,
    )


def _run_to_response(run: RunRecord) -> RunResponse:
    return RunResponse(
        run_id=run.run_id,
        project_id=run.project_id,
        destination_object_name=run.destination_object_name,
        source_definition_reference=run.source_definition_reference,
        environment=run.environment,
        status=run.status,
        current_stage=run.current_stage,
        source_slice_version=run.source_slice_version,
        mapping_snapshot_version=run.mapping_snapshot_version,
        lookup_snapshot_version=run.lookup_snapshot_version,
        lookup_snapshot_versions=run.lookup_snapshot_versions,
        code_generation_input_snapshot_version=run.code_generation_input_snapshot_version,
        codegen_artifact_id=run.codegen_artifact_id,
        knowledge_freeze_version=run.knowledge_freeze_version,
        start_metadata=run.start_metadata,
        pause_metadata=run.pause_metadata,
        resume_metadata=run.resume_metadata,
        completion_metadata=run.completion_metadata,
        started_at=None,
        last_checkpoint_at=None,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def approve_dry_run(db: Session, *, project_id: str, run_id: str, actor_user_id: str) -> RunResponse:
    run = _get_run_or_404(db, project_id=project_id, run_id=run_id)
    artifact = _get_artifact_or_404(db, project_id=project_id, run_id=run_id)

    artifact.status = "approved"
    run.status = "queued"

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="dry_run_approved",
        payload={"run_id": run_id, "dry_run_artifact_id": artifact.dry_run_artifact_id},
    )
    db.commit()
    db.refresh(run)
    return _run_to_response(run)


def push_back_dry_run(
    db: Session,
    *,
    project_id: str,
    run_id: str,
    actor_user_id: str,
    body: PushBackRequest,
) -> RunResponse:
    run = _get_run_or_404(db, project_id=project_id, run_id=run_id)
    artifact = _get_artifact_or_404(db, project_id=project_id, run_id=run_id)

    artifact.status = "pushed_back"
    artifact.push_back_comment = body.comment

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="dry_run_pushed_back",
        payload={
            "run_id": run_id,
            "dry_run_artifact_id": artifact.dry_run_artifact_id,
            "comment": body.comment,
        },
    )
    db.commit()
    db.refresh(run)
    return _run_to_response(run)
