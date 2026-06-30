from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import (
    SourceContractCreateRequest,
    SourceContractResponse,
    SourceSliceApprovalCountResponse,
    SourceSliceApprovalItemResponse,
    SourceSliceRejectRequest,
    SourceSliceResubmitRequest,
    SourceSliceResponse,
)
from ..db.models import ProjectMembership, ProjectRegistry, SourceDefinition, SourceSlice, SourceSliceRow, User, new_id
from ..intake.cobol_parser import parse_copybook
from ..intake.csv_intake import ingest_csv
from ..intake.fixed_intake import ingest_fixed
from ..management.platform import record_management_audit


def create_source_contract(
    db: Session,
    *,
    actor: User,
    project_id: str,
    body: SourceContractCreateRequest,
) -> SourceContractResponse:
    label = body.label.strip()
    source_definition = SourceDefinition(
        source_definition_id=new_id(),
        project_id=project_id,
        source_type=body.source_type,
        source_contract_version="v1",
        source_details={"label": label, "encoding": body.encoding},
        status="declared",
    )
    db.add(source_definition)
    db.flush()
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="source.contract.created",
        payload={
            "source_definition_id": source_definition.source_definition_id,
            "project_id": project_id,
            "source_type": body.source_type,
            "label": label,
            "encoding": body.encoding,
        },
    )
    db.commit()
    db.refresh(source_definition)
    return _source_contract_response(source_definition)


def list_source_contracts(db: Session, *, project_id: str) -> list[SourceContractResponse]:
    rows = db.scalars(
        select(SourceDefinition)
        .where(SourceDefinition.project_id == project_id)
        .order_by(SourceDefinition.created_at.asc())
    ).all()
    return [_source_contract_response(row) for row in rows]


def get_source_contract(db: Session, *, project_id: str, source_definition_id: str) -> SourceContractResponse:
    source_definition = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    return _source_contract_response(source_definition)


def upload_copybook(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    raw_bytes: bytes,
) -> SourceContractResponse:
    source_definition = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    if source_definition.source_type != "fixed_length_file":
        raise AuthApiError("layout_not_ready", "Copybook upload is only supported for fixed-length sources.", 409)

    encoding = _encoding_for_source(source_definition)
    copybook_text = _decode_text(raw_bytes, encoding=encoding)
    layout_information = [
        {
            "name": field.name,
            "offset": field.offset,
            "width": field.width,
            "picture": field.picture,
            "type_hint": field.type_hint,
        }
        for field in parse_copybook(copybook_text)
    ]
    source_definition.copybook_text = copybook_text
    source_definition.layout_information = layout_information
    source_definition.status = "layout_ready"
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="source.copybook.uploaded",
        payload={
            "source_definition_id": source_definition_id,
            "field_count": len(layout_information),
        },
    )
    db.commit()
    db.refresh(source_definition)
    return _source_contract_response(source_definition)


def upload_source_slice(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    raw_bytes: bytes,
) -> SourceSliceResponse:
    source_definition = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    if source_definition.source_type == "csv":
        result = ingest_csv(db, source_definition=source_definition, raw_bytes=raw_bytes)
    elif source_definition.source_type == "fixed_length_file":
        result = ingest_fixed(db, source_definition=source_definition, raw_bytes=raw_bytes)
    else:
        raise AuthApiError("unsupported_source_type", "Source type is not supported for uploads.", 422)

    source_definition.status = "active"
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="source.slice.uploaded",
        payload={
            "source_definition_id": source_definition_id,
            "source_slice_id": result.source_slice.source_slice_id,
            "row_count": result.row_count,
        },
    )
    db.commit()
    db.refresh(result.source_slice)
    return _source_slice_response(db, result.source_slice)


def list_source_slices(db: Session, *, project_id: str, source_definition_id: str) -> list[SourceSliceResponse]:
    _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    rows = db.scalars(
        select(SourceSlice)
        .where(SourceSlice.source_definition_id == source_definition_id)
        .order_by(SourceSlice.created_at.asc())
    ).all()
    return [_source_slice_response(db, row) for row in rows]


def get_source_slice(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
) -> SourceSliceResponse:
    _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    source_slice = db.get(SourceSlice, source_slice_id)
    if source_slice is None or source_slice.source_definition_id != source_definition_id:
        raise AuthApiError("source_slice_not_found", "Source slice not found.", 404)
    return _source_slice_response(db, source_slice)


def list_pending_approvals(db: Session, *, actor: User) -> list[SourceSliceApprovalItemResponse]:
    stmt = (
        select(
            ProjectRegistry.project_id,
            ProjectRegistry.name,
            SourceDefinition.source_definition_id,
            SourceDefinition.source_type,
            SourceDefinition.source_details,
            SourceSlice.source_slice_id,
            SourceSlice.source_slice_version,
            SourceSlice.status,
            SourceSlice.parse_warnings,
            SourceSlice.created_at,
            func.count(SourceSliceRow.id).label("row_count"),
        )
        .join(SourceDefinition, SourceDefinition.project_id == ProjectRegistry.project_id)
        .join(SourceSlice, SourceSlice.source_definition_id == SourceDefinition.source_definition_id)
        .outerjoin(SourceSliceRow, SourceSliceRow.source_slice_id == SourceSlice.source_slice_id)
        .where(SourceSlice.status == "pending_approval")
        .group_by(
            ProjectRegistry.project_id,
            ProjectRegistry.name,
            SourceDefinition.source_definition_id,
            SourceDefinition.source_type,
            SourceDefinition.source_details,
            SourceSlice.source_slice_id,
            SourceSlice.source_slice_version,
            SourceSlice.status,
            SourceSlice.parse_warnings,
            SourceSlice.created_at,
        )
        .order_by(SourceSlice.created_at.asc())
    )
    stmt = _apply_visibility_filter(stmt, actor=actor)
    rows = db.execute(stmt).all()
    return [
        SourceSliceApprovalItemResponse(
            project_id=project_id,
            project_name=project_name,
            source_definition_id=source_definition_id,
            source_label=_source_label(source_details),
            source_type=source_type,
            source_slice_id=source_slice_id,
            source_slice_version=source_slice_version,
            row_count=row_count,
            status=status,
            parse_warnings=parse_warnings,
            created_at=created_at,
        )
        for (
            project_id,
            project_name,
            source_definition_id,
            source_type,
            source_details,
            source_slice_id,
            source_slice_version,
            status,
            parse_warnings,
            created_at,
            row_count,
        ) in rows
    ]


def count_pending_approvals(db: Session, *, actor: User) -> SourceSliceApprovalCountResponse:
    return SourceSliceApprovalCountResponse(pending_count=len(list_pending_approvals(db, actor=actor)))


def approve_source_slice(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
) -> SourceSliceResponse:
    _source_definition, source_slice = _get_source_definition_and_slice(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        source_slice_id=source_slice_id,
    )
    if source_slice.status != "pending_approval":
        raise AuthApiError("slice_not_pending", "Source slice is not pending approval.", 409)

    source_slice.status = "approved"
    source_slice.approved_at = datetime.now(UTC)
    source_slice.approved_by_user_id = actor.user_id
    source_slice.approval_rejection_reason = None
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="source_slice_approved",
        payload={
            "source_definition_id": source_definition_id,
            "source_slice_id": source_slice_id,
        },
    )
    db.commit()
    db.refresh(source_slice)
    return _source_slice_response(db, source_slice)


def reject_source_slice(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
    body: SourceSliceRejectRequest,
) -> SourceSliceResponse:
    _source_definition, source_slice = _get_source_definition_and_slice(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        source_slice_id=source_slice_id,
    )
    if source_slice.status != "pending_approval":
        raise AuthApiError("slice_not_pending", "Source slice is not pending approval.", 409)

    reason = body.reason.strip()
    source_slice.status = "rejected"
    source_slice.approval_rejection_reason = reason
    source_slice.approved_at = None
    source_slice.approved_by_user_id = None
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="source_slice_rejected",
        payload={
            "source_definition_id": source_definition_id,
            "source_slice_id": source_slice_id,
            "reason": reason,
        },
    )
    db.commit()
    db.refresh(source_slice)
    return _source_slice_response(db, source_slice)


def resubmit_source_slice(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
    body: SourceSliceResubmitRequest,
) -> SourceSliceResponse:
    source_definition, source_slice = _get_source_definition_and_slice(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        source_slice_id=source_slice_id,
    )
    if source_slice.status != "rejected":
        raise AuthApiError("slice_not_rejected", "Source slice is not rejected.", 409)
    if not source_slice.file_storage_path:
        raise AuthApiError("file_not_retained", "Original file was not retained.", 422)

    for pending in db.scalars(
        select(SourceSlice).where(
            SourceSlice.source_definition_id == source_definition_id,
            SourceSlice.status == "pending_approval",
            SourceSlice.source_slice_id != source_slice_id,
        )
    ).all():
        pending.status = "rejected"
        pending.approval_rejection_reason = "superseded_by_resubmit"

    raw_bytes = _read_retained_file(source_slice.file_storage_path)
    encoding = body.encoding or _encoding_for_source(source_definition)
    try:
        if source_definition.source_type == "csv":
            result = ingest_csv(
                db,
                source_definition=source_definition,
                raw_bytes=raw_bytes,
                encoding_override=encoding,
                file_storage_path=source_slice.file_storage_path,
            )
        elif source_definition.source_type == "fixed_length_file":
            result = ingest_fixed(
                db,
                source_definition=source_definition,
                raw_bytes=raw_bytes,
                encoding_override=encoding,
                file_storage_path=source_slice.file_storage_path,
            )
        else:
            raise AuthApiError("unsupported_source_type", "Source type is not supported for resubmit.", 422)
    except AuthApiError as exc:
        raise AuthApiError("parse_failed", exc.message, 422) from exc

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="source_slice_resubmitted",
        payload={
            "old_slice_id": source_slice_id,
            "new_slice_id": result.source_slice.source_slice_id,
            "source_definition_id": source_definition_id,
        },
    )
    db.commit()
    db.refresh(result.source_slice)
    return _source_slice_response(db, result.source_slice)


def _source_contract_response(source_definition: SourceDefinition) -> SourceContractResponse:
    details = source_definition.source_details or {}
    label = cast(str, details.get("label", source_definition.source_type))
    encoding = cast(str, details.get("encoding", "utf-8"))
    return SourceContractResponse(
        source_definition_id=source_definition.source_definition_id,
        project_id=source_definition.project_id,
        source_type=source_definition.source_type,
        label=label,
        encoding=encoding,
        destination_object_references=source_definition.destination_object_references,
        layout_information=cast(list[dict[str, Any]] | None, source_definition.layout_information),
        copybook_text=source_definition.copybook_text,
        status=source_definition.status,
        created_at=source_definition.created_at,
    )


def _source_slice_response(db: Session, source_slice: SourceSlice) -> SourceSliceResponse:
    rows = db.scalars(
        select(SourceSliceRow)
        .where(SourceSliceRow.source_slice_id == source_slice.source_slice_id)
        .order_by(SourceSliceRow.row_index.asc())
    ).all()
    return SourceSliceResponse(
        source_slice_id=source_slice.source_slice_id,
        source_definition_id=source_slice.source_definition_id,
        source_slice_version=source_slice.source_slice_version,
        header_csv=source_slice.header_csv,
        row_count=len(rows),
        status=source_slice.status,
        approval_rejection_reason=source_slice.approval_rejection_reason,
        parse_warnings=source_slice.parse_warnings,
        file_storage_path=source_slice.file_storage_path,
        preview_rows=[row.row_csv for row in rows[:10]],
        created_at=source_slice.created_at,
    )


def _get_source_definition(db: Session, *, project_id: str, source_definition_id: str) -> SourceDefinition:
    source_definition = db.get(SourceDefinition, source_definition_id)
    if source_definition is None or source_definition.project_id != project_id:
        raise AuthApiError("source_not_found", "Source contract not found.", 404)
    return source_definition


def _get_source_definition_and_slice(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
) -> tuple[SourceDefinition, SourceSlice]:
    source_definition = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    source_slice = db.get(SourceSlice, source_slice_id)
    if source_slice is None or source_slice.source_definition_id != source_definition_id:
        raise AuthApiError("slice_not_found", "Source slice not found.", 404)
    return source_definition, source_slice


def _encoding_for_source(source_definition: SourceDefinition) -> str:
    details = source_definition.source_details or {}
    if isinstance(details, dict):
        encoding = details.get("encoding")
        if isinstance(encoding, str) and encoding:
            return encoding
    return "utf-8"


def _decode_text(raw_bytes: bytes, *, encoding: str) -> str:
    for candidate in (encoding, "utf-8", "latin-1", "cp1252"):
        try:
            return raw_bytes.decode(candidate)
        except UnicodeDecodeError:
            continue
    raise AuthApiError("unsupported_encoding", "Uploaded file encoding is not supported.", 422)


def _apply_visibility_filter(stmt: Any, *, actor: User) -> Any:
    if actor.role == "central_team":
        return stmt
    if actor.role == "project_stakeholder":
        return stmt.join(
            ProjectMembership,
            ProjectMembership.project_id == ProjectRegistry.project_id,
        ).where(ProjectMembership.user_id == actor.user_id)
    return stmt.where(False)


def _source_label(source_details: dict[str, Any] | None) -> str:
    if isinstance(source_details, dict):
        label = source_details.get("label")
        if isinstance(label, str) and label:
            return label
    return "Source"


def _read_retained_file(file_storage_path: str) -> bytes:
    with open(file_storage_path, "rb") as handle:
        return handle.read()
