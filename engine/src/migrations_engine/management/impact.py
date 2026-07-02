from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.factory import get_adapter
from ..api.deps import AuthApiError
from ..api.schemas import (
    GateRejectionDetail,
    ImpactAIRecommendation,
    ImpactReportResponse,
    RunResponse,
)
from ..db.models import MappingSnapshot, RunRecord
from ..management.platform import record_management_audit


class _ImpactAnalysisAIResponse(BaseModel):
    recommendation: str
    suggested_fix: str
    minimal_replay_scope: list[str]


def _get_run_or_404(db: Session, *, project_id: str, run_id: str) -> RunRecord:
    run = db.scalar(
        select(RunRecord).where(
            RunRecord.run_id == run_id,
            RunRecord.project_id == project_id,
        )
    )
    if run is None:
        raise AuthApiError("run_not_found", "Run not found.", 404)
    return run


def _find_gate1_rejection(run: RunRecord) -> dict[str, Any] | None:
    for record in run.approvals or []:
        if record.get("gate") == "gate_1" and record.get("decision") == "rejected":
            return record
    return None


def _get_field_bindings(
    db: Session,
    *,
    project_id: str,
    destination_object_name: str,
    mapping_snapshot_version: str | None,
) -> list[dict[str, Any]]:
    if mapping_snapshot_version is None:
        return []

    snapshot = db.scalar(
        select(MappingSnapshot).where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.destination_object_name == destination_object_name,
            MappingSnapshot.mapping_snapshot_version == mapping_snapshot_version,
        )
    )
    if snapshot is None:
        return []
    return list(snapshot.field_bindings)


def _compute_replay_scope(
    db: Session,
    *,
    project_id: str,
    run_id: str,
    affected_objects: list[str],
) -> list[str]:
    if not affected_objects:
        return []

    siblings = db.scalars(
        select(RunRecord.run_id).where(
            RunRecord.project_id == project_id,
            RunRecord.run_id != run_id,
            RunRecord.destination_object_name.in_(affected_objects),
            RunRecord.status.notin_(["completed", "failed"]),
        )
    ).all()
    return list(siblings)


def _call_impact_ai(
    *,
    required_changes: str,
    affected_objects: list[str],
    field_bindings: list[dict[str, Any]],
) -> _ImpactAnalysisAIResponse:
    adapter = get_adapter("impact_analysis")
    system = (
        "You are a data migration expert. Analyse the Gate 1 pushback and produce a structured "
        "remediation recommendation. Return JSON matching the schema exactly."
    )
    user = (
        "Gate 1 rejection details:\n"
        f"Required changes: {required_changes}\n"
        f"Affected objects: {', '.join(affected_objects)}\n\n"
        "Current field bindings:\n"
        + "\n".join(
            f"  {binding.get('source_field')} -> {binding.get('destination_field')}"
            + (f" (lookup: {binding.get('lookup_name')})" if binding.get("lookup_name") else "")
            for binding in field_bindings
        )
    )
    return adapter.call(system, user, _ImpactAnalysisAIResponse)


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
        started_at=getattr(run, "started_at", None),
        last_checkpoint_at=None,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def get_impact_report(db: Session, *, project_id: str, run_id: str) -> ImpactReportResponse:
    run = _get_run_or_404(db, project_id=project_id, run_id=run_id)
    rejection = _find_gate1_rejection(run)
    if rejection is None:
        raise AuthApiError("gate_1_not_rejected", "Gate 1 has not been rejected for this run.", 404)

    affected_objects = [str(item) for item in rejection.get("affected_objects") or [] if str(item)]
    required_changes = str(rejection.get("required_changes", ""))
    rejected_at_raw = rejection.get("decided_at")
    if not isinstance(rejected_at_raw, str):
        raise AuthApiError("invalid_gate_record", "Gate record is invalid.", 500)

    field_bindings = _get_field_bindings(
        db,
        project_id=project_id,
        destination_object_name=run.destination_object_name,
        mapping_snapshot_version=run.mapping_snapshot_version,
    )
    replay_scope = _compute_replay_scope(
        db,
        project_id=project_id,
        run_id=run_id,
        affected_objects=affected_objects,
    )
    ai_result = _call_impact_ai(
        required_changes=required_changes,
        affected_objects=affected_objects,
        field_bindings=field_bindings,
    )

    return ImpactReportResponse(
        run_id=run_id,
        gate_rejection=GateRejectionDetail(
            rejected_by=rejection.get("approver_user_id") if isinstance(rejection.get("approver_user_id"), str) else None,
            rejected_at=datetime.fromisoformat(rejected_at_raw),
            affected_objects=affected_objects,
            required_changes=required_changes,
            notes=rejection.get("notes") if isinstance(rejection.get("notes"), str) else None,
        ),
        replay_scope=replay_scope,
        ai_recommendation=ImpactAIRecommendation(
            recommendation=ai_result.recommendation,
            suggested_fix=ai_result.suggested_fix,
            minimal_replay_scope=ai_result.minimal_replay_scope,
        ),
    )


def acknowledge_impact(db: Session, *, project_id: str, run_id: str, actor_user_id: str) -> RunResponse:
    run = _get_run_or_404(db, project_id=project_id, run_id=run_id)
    if _find_gate1_rejection(run) is None:
        raise AuthApiError("gate_1_not_rejected", "Gate 1 has not been rejected for this run.", 404)

    run.status = "pending_gate_1"
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="gate_1_impact_acknowledged",
        payload={"run_id": run_id},
    )
    db.commit()
    db.refresh(run)
    return _run_to_response(run)
