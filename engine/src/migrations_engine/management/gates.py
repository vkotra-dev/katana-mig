from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import (
    FieldBindingSummary,
    Gate1EvidenceResponse,
    Gate2EvidenceResponse,
    GateApproveRequest,
    GatePushbackRequest,
    GateRecordResponse,
    GateStatusResponse,
    LookupRowResponse,
)
from ..db.models import LookupValueMap, RunRecord
from ..intake.masking import is_pii_field
from ..management.platform import record_management_audit
from ..management.source_analysis import get_latest_source_schema_artifact
from ..mapping.exceptions import SnapshotNotFoundError
from ..mapping.snapshots import select_latest_approved_mapping_snapshot


def _get_run_or_404(db: Session, *, project_id: str, run_id: str) -> RunRecord:
    run = db.scalar(select(RunRecord).where(RunRecord.run_id == run_id, RunRecord.project_id == project_id))
    if run is None:
        raise AuthApiError("run_not_found", "Run not found.", 404)
    return run


def _find_gate_record(run: RunRecord, gate: str) -> dict[str, object] | None:
    for record in run.approvals or []:
        if record.get("gate") == gate:
            return record
    return None


def _to_gate_record_response(record: dict[str, object] | None) -> GateRecordResponse | None:
    if record is None:
        return None
    decided_at = record.get("decided_at")
    if not isinstance(decided_at, str):
        raise AuthApiError("invalid_gate_record", "Gate record is invalid.", 500)
    return GateRecordResponse(
        gate=str(record["gate"]),
        decision=str(record["decision"]),
        approver_user_id=record.get("approver_user_id") if isinstance(record.get("approver_user_id"), str) else None,
        decided_at=datetime.fromisoformat(decided_at),
        notes=record.get("notes") if isinstance(record.get("notes"), str) else None,
        affected_objects=record.get("affected_objects") if isinstance(record.get("affected_objects"), list) else None,
        required_changes=record.get("required_changes") if isinstance(record.get("required_changes"), str) else None,
    )


def get_gate_status(db: Session, *, project_id: str, run_id: str) -> GateStatusResponse:
    run = _get_run_or_404(db, project_id=project_id, run_id=run_id)
    return GateStatusResponse(
        run_id=run_id,
        gate_1=_to_gate_record_response(_find_gate_record(run, "gate_1")),
        gate_2=_to_gate_record_response(_find_gate_record(run, "gate_2")),
    )


def get_gate1_evidence(db: Session, *, project_id: str, run_id: str) -> Gate1EvidenceResponse:
    run = _get_run_or_404(db, project_id=project_id, run_id=run_id)
    mapping_snapshot_version: str | None = None
    field_bindings: list[FieldBindingSummary] = []
    mapped_source_fields: set[str] = set()

    try:
        mapping_snapshot = select_latest_approved_mapping_snapshot(
            db,
            project_id=project_id,
            destination_object_name=run.destination_object_name,
        )
        mapping_snapshot_version = mapping_snapshot.mapping_snapshot_version
        for binding in mapping_snapshot.field_bindings:
            source_field = str(binding.get("source_field", ""))
            destination_field = str(binding.get("destination_field", ""))
            lookup_name = binding.get("lookup_name")
            field_bindings.append(
                FieldBindingSummary(
                    source_field=source_field,
                    destination_field=destination_field,
                    lookup_name=str(lookup_name) if lookup_name is not None else None,
                )
            )
            if source_field:
                mapped_source_fields.add(source_field)
    except SnapshotNotFoundError:
        pass

    pii_fields: list[str] = []
    coverage_gaps: list[str] = []
    source_definition_id = run.source_definition_reference
    if source_definition_id:
        try:
            schema_artifact = get_latest_source_schema_artifact(
                db,
                project_id=project_id,
                source_definition_id=source_definition_id,
            )
        except AuthApiError:
            schema_artifact = None
        if schema_artifact is not None:
            for column in schema_artifact.columns:
                if is_pii_field(column.name):
                    pii_fields.append(column.name)
                if column.name not in mapped_source_fields:
                    coverage_gaps.append(column.name)

    return Gate1EvidenceResponse(
        run_id=run_id,
        destination_object_name=run.destination_object_name,
        mapping_snapshot_version=mapping_snapshot_version,
        field_bindings=field_bindings,
        pii_fields=pii_fields,
        coverage_gaps=coverage_gaps,
    )


def get_gate2_evidence(db: Session, *, project_id: str, run_id: str) -> Gate2EvidenceResponse:
    run = _get_run_or_404(db, project_id=project_id, run_id=run_id)
    source_definition_id = run.source_definition_reference
    if not source_definition_id:
        raise AuthApiError("source_not_linked", "Run has no linked source definition.", 409)

    lookup_name: str | None = None
    try:
        mapping_snapshot = select_latest_approved_mapping_snapshot(
            db,
            project_id=project_id,
            destination_object_name=run.destination_object_name,
        )
    except SnapshotNotFoundError:
        mapping_snapshot = None

    if mapping_snapshot is not None:
        for binding in mapping_snapshot.field_bindings:
            lookup_candidate = binding.get("lookup_name")
            if lookup_candidate:
                lookup_name = str(lookup_candidate)
                break

    if not lookup_name:
        return Gate2EvidenceResponse(run_id=run_id, lookup_name="", rows=[], confirmed_count=0, unmapped_count=0)

    lookup_value_map = db.scalar(
        select(LookupValueMap).where(
            LookupValueMap.source_definition_id == source_definition_id,
            LookupValueMap.lookup_name == lookup_name,
        )
    )
    if lookup_value_map is None:
        return Gate2EvidenceResponse(
            run_id=run_id,
            lookup_name=lookup_name,
            rows=[],
            confirmed_count=0,
            unmapped_count=0,
        )

    destination_values = {
        _extract_destination_id(row)
        for row in lookup_value_map.destination_table
        if _extract_destination_id(row)
    }
    rows: list[LookupRowResponse] = []
    for source_value, destination_value in lookup_value_map.source_value_map.items():
        rows.append(
            LookupRowResponse(
                source_value=source_value,
                destination_value=destination_value or None,
                state="confirmed" if destination_value in destination_values else "unmapped",
            )
        )

    confirmed_count = sum(1 for row in rows if row.state == "confirmed")
    unmapped_count = sum(1 for row in rows if row.state == "unmapped")
    return Gate2EvidenceResponse(
        run_id=run_id,
        lookup_name=lookup_name,
        rows=rows,
        confirmed_count=confirmed_count,
        unmapped_count=unmapped_count,
    )


def approve_gate(
    db: Session,
    *,
    project_id: str,
    run_id: str,
    gate: str,
    actor_user_id: str,
    body: GateApproveRequest,
) -> GateStatusResponse:
    run = _get_run_or_404(db, project_id=project_id, run_id=run_id)
    existing_record = _find_gate_record(run, gate)
    if existing_record is not None and existing_record.get("decision") == "approved":
        raise AuthApiError("gate_already_approved", f"{gate} is already approved.", 422)
    if gate == "gate_2":
        gate_1_record = _find_gate_record(run, "gate_1")
        if gate_1_record is None or gate_1_record.get("decision") != "approved":
            raise AuthApiError("gate_1_not_approved", "Gate 1 must be approved before Gate 2 can be approved.", 422)
        if run.status != "awaiting_approval":
            raise AuthApiError("gate_not_ready", "Gate 2 is not ready for approval.", 409)

    approvals = [record for record in (run.approvals or []) if record.get("gate") != gate]
    approvals.append(
        {
            "gate": gate,
            "decision": "approved",
            "approver_user_id": actor_user_id,
            "decided_at": datetime.now(UTC).isoformat(),
            "notes": body.notes,
        }
    )
    run.approvals = approvals
    if gate == "gate_1":
        run.status = "awaiting_approval"
        run.current_stage = "gate_2_pending"
    else:
        run.current_stage = "gate_2_approved"

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type=f"{gate}_approved",
        payload={"run_id": run_id, "notes": body.notes},
    )
    db.commit()
    db.refresh(run)
    return get_gate_status(db, project_id=project_id, run_id=run_id)


def reject_gate(
    db: Session,
    *,
    project_id: str,
    run_id: str,
    gate: str,
    actor_user_id: str,
    body: GatePushbackRequest,
) -> GateStatusResponse:
    run = _get_run_or_404(db, project_id=project_id, run_id=run_id)
    approvals = [record for record in (run.approvals or []) if record.get("gate") != gate]
    approvals.append(
        {
            "gate": gate,
            "decision": "rejected",
            "approver_user_id": actor_user_id,
            "decided_at": datetime.now(UTC).isoformat(),
            "affected_objects": body.affected_objects,
            "required_changes": body.required_changes,
            "notes": body.notes,
        }
    )
    run.approvals = approvals
    run.status = "paused"
    run.pause_metadata = {
        "gate": gate,
        "reason": body.required_changes,
        "paused_at": datetime.now(UTC).isoformat(),
    }

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type=f"{gate}_rejected",
        payload={
            "run_id": run_id,
            "affected_objects": body.affected_objects,
            "required_changes": body.required_changes,
            "notes": body.notes,
        },
    )
    db.commit()
    db.refresh(run)
    return get_gate_status(db, project_id=project_id, run_id=run_id)


def _extract_destination_id(row: dict[str, object]) -> str:
    for key in ("id", "value", "code", "key", "destination_id"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
