from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Literal, cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import (
    FeedCreateRequest,
    FeedResponse,
    FeedSliceRejectRequest,
    FeedSliceResubmitRequest,
    FeedSliceResponse,
)
from ..db.models import (
    ProjectMembership, ProjectRegistry, Feed, FeedSlice, FeedSliceRow,
    RunRecord, User, MappingSnapshot, ProjectFiber, LookupValueMap, new_id,
)
from ..intake.cobol_parser import parse_copybook
from ..intake.csv_intake import ingest_csv
from ..intake.fixed_intake import ingest_fixed
from ..management.platform import record_management_audit


def create_source_contract(
    db: Session,
    *,
    actor: User,
    project_id: str,
    body: FeedCreateRequest,
) -> FeedResponse:
    label = body.label.strip()
    source_definition = Feed(
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
    return _source_contract_response(source_definition, db=db)


def list_source_contracts(
    db: Session,
    *,
    project_id: str,
    include_discarded: bool = False,
) -> list[FeedResponse]:
    stmt = select(Feed).where(Feed.project_id == project_id)
    if not include_discarded:
        stmt = stmt.where(Feed.status != "discarded")
    stmt = stmt.order_by(Feed.created_at.asc())
    rows = db.scalars(stmt).all()

    feed_ids = {f.source_definition_id for f in rows}
    status_map = _batch_mapping_status(db, project_id, feed_ids)

    result: list[FeedResponse] = []
    for feed in rows:
        details = feed.source_details or {}
        label = cast(str, details.get("label", feed.source_type))
        encoding = cast(str, details.get("encoding", "utf-8"))
        result.append(FeedResponse(
            source_definition_id=feed.source_definition_id,
            project_id=feed.project_id,
            source_type=feed.source_type,
            label=label,
            encoding=encoding,
            destination_object_references=feed.destination_object_references,
            layout_information=cast(list[dict[str, Any]] | None, feed.layout_information),
            copybook_text=feed.copybook_text,
            status=feed.status,
            created_at=feed.created_at,
            mapping_hints=feed.mapping_hints,
            transformation_instructions=feed.transformation_instructions,
            mapping_status=status_map.get(feed.source_definition_id),
        ))
    return result


def discard_feed(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
) -> FeedResponse:
    feed = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    if feed.status == "discarded":
        raise AuthApiError("already_discarded", "Feed is already discarded.", 409)

    active_run = db.scalars(
        select(RunRecord).where(
            RunRecord.source_definition_reference == source_definition_id,
            RunRecord.status.in_(["running", "awaiting_approval"]),
        ).limit(1)
    ).first()
    if active_run is not None:
        raise AuthApiError(
            "run_in_progress",
            "Cannot discard a feed while a run is active or awaiting approval.",
            409,
        )

    # Cascade to mapping snapshots
    snapshots = db.scalars(
        select(MappingSnapshot).where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id == source_definition_id,
        )
    ).all()
    for snap in snapshots:
        snap.status = "discarded"

    # Cascade to fibers
    fibers = db.scalars(
        select(ProjectFiber).where(
            ProjectFiber.project_id == project_id,
            ProjectFiber.feed_id == source_definition_id,
        )
    ).all()
    for fiber in fibers:
        fiber.status = "discarded"

    # Cascade to lookup value maps — only if not shared with another active feed
    feed_lookup_names = _lookup_names_for_feed(list(snapshots))
    shared = _shared_lookup_names(
        db, project_id=project_id,
        excluding_feed_id=source_definition_id,
        candidate_names=feed_lookup_names,
    )
    exclusive_lookups = feed_lookup_names - shared
    if exclusive_lookups:
        lvms = db.scalars(
            select(LookupValueMap).where(
                LookupValueMap.project_id == project_id,
                LookupValueMap.lookup_name.in_(exclusive_lookups),
            )
        ).all()
        for lvm in lvms:
            lvm.status = "discarded"

    feed.status = "discarded"
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="source.feed.discarded",
        payload={"source_definition_id": source_definition_id},
    )
    db.commit()
    db.refresh(feed)
    return _source_contract_response(feed, db=db)


def _lookup_names_for_feed(snapshots: list[MappingSnapshot]) -> set[str]:
    names: set[str] = set()
    for snap in snapshots:
        for b in (snap.field_bindings or []):
            if b.get("binding_type") == "lookup_fk" and b.get("lookup_name"):
                names.add(b["lookup_name"])
    return names


def _shared_lookup_names(
    db: Session,
    *,
    project_id: str,
    excluding_feed_id: str,
    candidate_names: set[str],
) -> set[str]:
    if not candidate_names:
        return set()
    other_snapshots = db.scalars(
        select(MappingSnapshot).where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id != excluding_feed_id,
            MappingSnapshot.source_definition_id.isnot(None),
        )
    ).all()
    feed_ids = {s.source_definition_id for s in other_snapshots}
    if not feed_ids:
        return set()
    active_feed_ids = set(db.scalars(
        select(Feed.source_definition_id).where(
            Feed.source_definition_id.in_(feed_ids),
            Feed.status != "discarded",
        )
    ).all())
    active_other = [s for s in other_snapshots if s.source_definition_id in active_feed_ids]
    return candidate_names & _lookup_names_for_feed(active_other)


def get_source_contract(db: Session, *, project_id: str, source_definition_id: str) -> FeedResponse:
    source_definition = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    return _source_contract_response(source_definition, db=db)


def upload_copybook(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    raw_bytes: bytes,
) -> FeedResponse:
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
    return _source_contract_response(source_definition, db=db)


def upload_source_slice(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    raw_bytes: bytes,
) -> FeedSliceResponse:
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


def list_source_slices(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    masked: bool = True,
) -> list[FeedSliceResponse]:
    _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    rows = db.scalars(
        select(FeedSlice)
        .where(FeedSlice.source_definition_id == source_definition_id)
        .order_by(FeedSlice.created_at.asc())
    ).all()
    return [_source_slice_response(db, row, masked=masked) for row in rows]


def get_source_slice(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
    masked: bool = True,
) -> FeedSliceResponse:
    _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    source_slice = db.get(FeedSlice, source_slice_id)
    if source_slice is None or source_slice.source_definition_id != source_definition_id:
        raise AuthApiError("source_slice_not_found", "Source slice not found.", 404)
    return _source_slice_response(db, source_slice, masked=masked)





def approve_source_slice(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
) -> FeedSliceResponse:
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
    body: FeedSliceRejectRequest,
) -> FeedSliceResponse:
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
    body: FeedSliceResubmitRequest,
) -> FeedSliceResponse:
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
        select(FeedSlice).where(
            FeedSlice.source_definition_id == source_definition_id,
            FeedSlice.status == "pending_approval",
            FeedSlice.source_slice_id != source_slice_id,
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


def _dedup_snapshots(
    snapshots: list[MappingSnapshot],
) -> list[MappingSnapshot]:
    """Dedup to latest snapshot per (source_definition_id, destination_object_name).

    Caller must ORDER BY destination_object_name ASC, created_at DESC.
    Mirrors the pattern in review.py:189 and sign_offs.py:185.

    Keys on both source_definition_id and destination_object_name so it's safe
    to call with snapshots from multiple feeds at once (batch mode).
    """
    seen: set[tuple[str, str]] = set()
    unique: list[MappingSnapshot] = []
    for s in snapshots:
        key = (s.source_definition_id, s.destination_object_name)
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def _compute_status_from_snapshots(
    deduped: list[MappingSnapshot],
) -> Literal["draft", "partial", "approved"] | None:
    """Compute summary from deduped snapshots.

    "rejected" pulls toward "partial" — a rejected table needs rework and
    should not be silently ignored. Dedup already drops stale history,
    so this function only sees one row per table.
    """
    if not deduped:
        return None
    statuses: set[str] = {s.status for s in deduped}
    if statuses == {"approved"}:
        return "approved"
    if statuses == {"draft"}:
        return "draft"
    if statuses == {"rejected"}:
        return "draft"
    return "partial"


def _compute_mapping_status(
    db: Session, project_id: str, feed_id: str
) -> Literal["draft", "partial", "approved"] | None:
    snapshots = db.scalars(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id == feed_id,
        )
        .order_by(MappingSnapshot.destination_object_name.asc(), MappingSnapshot.created_at.desc())
    ).all()
    deduped = _dedup_snapshots(snapshots)
    return _compute_status_from_snapshots(deduped)


def _batch_mapping_status(
    db: Session, project_id: str, feed_ids: set[str]
) -> dict[str, Literal["draft", "partial", "approved"] | None]:
    if not feed_ids:
        return {}
    snapshots = db.scalars(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id.in_(feed_ids),
        )
        .order_by(MappingSnapshot.destination_object_name.asc(), MappingSnapshot.created_at.desc())
    ).all()
    deduped = _dedup_snapshots(snapshots)
    per_feed: dict[str, list[MappingSnapshot]] = {}
    for s in deduped:
        per_feed.setdefault(s.source_definition_id, []).append(s)
    result: dict[str, Literal["draft", "partial", "approved"] | None] = {}
    for fid, snaps in per_feed.items():
        result[fid] = _compute_status_from_snapshots(snaps)
    return result


def _source_contract_response(
    source_definition: Feed, db: Session | None = None
) -> FeedResponse:
    details = source_definition.source_details or {}
    label = cast(str, details.get("label", source_definition.source_type))
    encoding = cast(str, details.get("encoding", "utf-8"))
    mapping_status = None
    if db is not None:
        mapping_status = _compute_mapping_status(
            db,
            project_id=source_definition.project_id,
            feed_id=source_definition.source_definition_id,
        )
    return FeedResponse(
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
        mapping_hints=source_definition.mapping_hints,
        transformation_instructions=source_definition.transformation_instructions,
        mapping_status=mapping_status,
    )


def _parse_csv_row(value: str | None) -> list[str]:
    if not value:
        return []
    import csv
    return next(csv.reader([value]))


def _source_slice_response(db: Session, source_slice: FeedSlice, *, masked: bool = True) -> FeedSliceResponse:
    row_count = db.scalar(
        select(func.count(FeedSliceRow.id)).where(FeedSliceRow.source_slice_id == source_slice.source_slice_id)
    ) or 0

    preview_rows = []
    if not masked and source_slice.file_storage_path:
        try:
            import os
            import csv
            import io
            source_definition = db.get(Feed, source_slice.source_definition_id)
            if source_definition and os.path.exists(source_slice.file_storage_path):
                if source_definition.source_type == "csv":
                    with open(source_slice.file_storage_path, "r", encoding="utf-8") as f:
                        reader = csv.reader(f)
                        next(reader, None)  # skip header
                        for i, values in enumerate(reader):
                            if i >= 10:
                                break
                            buffer = io.StringIO()
                            csv.writer(buffer).writerow(values)
                            preview_rows.append(buffer.getvalue().rstrip("\r\n"))
                elif source_definition.source_type == "fixed_length_file" and source_definition.layout_information:
                    from ..intake.copybook import parse_copybook
                    from ..intake.fixed_intake import _iter_non_empty_lines
                    fields = parse_copybook(source_definition.layout_information)
                    total_width = fields[-1].offset + fields[-1].width
                    with open(source_slice.file_storage_path, "r", encoding="utf-8") as f:
                        text = f.read()
                        for i, line in enumerate(_iter_non_empty_lines(text)):
                            if i >= 10:
                                break
                            normalized_line = line.rstrip("\r\n")
                            padded_line = normalized_line[:total_width].ljust(total_width)
                            values = [padded_line[field.offset : field.offset + field.width].strip() for field in fields]
                            buffer = io.StringIO()
                            csv.writer(buffer).writerow(values)
                            preview_rows.append(buffer.getvalue().rstrip("\r\n"))
        except Exception:
            pass

    if not preview_rows:
        preview_rows = db.scalars(
            select(FeedSliceRow.row_csv)
            .where(FeedSliceRow.source_slice_id == source_slice.source_slice_id)
            .order_by(FeedSliceRow.row_index.asc())
            .limit(10)
        ).all()

    if masked and source_slice.header_csv:
        from ..intake.masking import mask_row
        headers = _parse_csv_row(source_slice.header_csv)
        masked_rows = []
        for row_csv in preview_rows:
            values = _parse_csv_row(row_csv)
            masked_rows.append(mask_row(headers, values))
        preview_rows = masked_rows
    return FeedSliceResponse(
        source_slice_id=source_slice.source_slice_id,
        source_definition_id=source_slice.source_definition_id,
        source_slice_version=source_slice.source_slice_version,
        header_csv=source_slice.header_csv,
        row_count=row_count,
        status=source_slice.status,
        approval_rejection_reason=source_slice.approval_rejection_reason,
        parse_warnings=source_slice.parse_warnings,
        preview_rows=preview_rows,
        created_at=source_slice.created_at,
    )


def _get_source_definition(db: Session, *, project_id: str, source_definition_id: str) -> Feed:
    source_definition = db.get(Feed, source_definition_id)
    if source_definition is None or source_definition.project_id != project_id:
        raise AuthApiError("source_not_found", "Source contract not found.", 404)
    return source_definition


def _get_source_definition_and_slice(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
) -> tuple[Feed, FeedSlice]:
    source_definition = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    source_slice = db.get(FeedSlice, source_slice_id)
    if source_slice is None or source_slice.source_definition_id != source_definition_id:
        raise AuthApiError("slice_not_found", "Source slice not found.", 404)
    return source_definition, source_slice


def _encoding_for_source(source_definition: Feed) -> str:
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


def _staging_table_name(feed_label: str) -> str:
    sanitized = re.sub(r'[^a-z0-9_]', '_', feed_label.lower())[:59]
    return f"stg_{sanitized if sanitized else 'source'}"


def _read_retained_file(file_storage_path: str) -> bytes:
    with open(file_storage_path, "rb") as handle:
        return handle.read()
