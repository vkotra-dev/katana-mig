from __future__ import annotations

import csv
import io
import json
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import (
    FiberCreateRequest,
    FiberResponse,
    LookupDestEntryResponse,
    LookupDestFeedCreateRequest,
    LookupDestFeedResponse,
    LookupInputsRequest,
    LookupMappingPatchRequest,
    LookupMappingResponse,
    LookupSourceEntriesCreateRequest,
    LookupSourceEntryResponse,
)
from ..db.models import (
    Feed,
    FeedSlice,
    LookupDestEntry,
    LookupDestFeed,
    LookupMapping,
    LookupSourceEntry,
    ProjectDefinition,
    ProjectFiber,
    ProjectRegistry,
    User,
    new_id,
)

try:
    from ..ai.factory import get_adapter
except ModuleNotFoundError:  # pragma: no cover - optional SDK dependency may be absent in tests
    get_adapter = None  # type: ignore[assignment]


_LOOKUP_MAPPING_SYSTEM_PROMPT = (
    "You are a lookup value mapper. Given a list of source values and "
    "destination reference rows, propose the best match for each source value. "
    "Return a JSON array."
)


class _LookupProposal(BaseModel):
    source_value: str
    dest_entry_id: str
    confidence_score: float


class _LookupMappingResult(BaseModel):
    proposals: list[_LookupProposal]


_FEED_ANALYSIS_SYSTEM_PROMPT = (
    "You are a data migration analyst. "
    "Given CSV column headers and a destination schema DDL, "
    "identify all lookup columns and domain objects. Return JSON."
)

_FIELD_MAPPING_SYSTEM_PROMPT = (
    "You are a field mapper. "
    "Given source columns and destination DDL, propose field bindings. Return JSON."
)


class _LookupIdentified(BaseModel):
    column_name: str
    lookup_name: str


class _DomainObject(BaseModel):
    destination_table: str


class _FeedAnalysisResult(BaseModel):
    lookups: list[_LookupIdentified]
    domain_objects: list[_DomainObject]


class _FieldBinding(BaseModel):
    source_field: str | None
    destination_field: str
    lookup_name: str | None


class _FieldMappingResult(BaseModel):
    field_bindings: list[_FieldBinding]


def create_fiber(
    db: Session,
    *,
    actor: User,
    project_id: str,
    feed_id: str,
    body: FiberCreateRequest,
) -> FiberResponse:
    feed = _get_feed(db, project_id=project_id, feed_id=feed_id)
    fiber = ProjectFiber(
        fiber_id=new_id(),
        feed_id=feed.source_definition_id,
        project_id=project_id,
        fiber_type=body.fiber_type,
        fiber_key=body.fiber_key,
        status="deferred" if body.fiber_type == "lookup" else "created",
        source=body.source,
    )
    db.add(fiber)
    db.commit()
    db.refresh(fiber)
    return _fiber_response(fiber)


def list_fibers(db: Session, *, project_id: str, feed_id: str) -> list[FiberResponse]:
    _get_feed(db, project_id=project_id, feed_id=feed_id)
    rows = db.scalars(
        select(ProjectFiber)
        .where(ProjectFiber.project_id == project_id)
        .where(ProjectFiber.feed_id == feed_id)
        .order_by(ProjectFiber.created_at.asc())
    ).all()
    return [_fiber_response(row) for row in rows]


def get_fiber(db: Session, *, project_id: str, feed_id: str, fiber_id: str) -> FiberResponse:
    _get_feed(db, project_id=project_id, feed_id=feed_id)
    fiber = db.get(ProjectFiber, fiber_id)
    if fiber is None or fiber.project_id != project_id or fiber.feed_id != feed_id:
        raise AuthApiError("fiber_not_found", "Fiber not found.", 404)
    return _fiber_response(fiber)


def analyze_feed(
    db: Session,
    *,
    feed_id: str,
    project_id: str,
    actor: User,
) -> list[FiberResponse]:
    del actor

    _get_feed(db, project_id=project_id, feed_id=feed_id)

    registry = db.get(ProjectRegistry, project_id)
    if registry is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)

    project_definition = db.get(ProjectDefinition, registry.definition_id)
    domain_config = project_definition.domain_config if project_definition is not None else {}
    destination_schema_ddl = ""
    if isinstance(domain_config, dict):
        ddl_value = domain_config.get("destination_schema_ddl", "")
        if isinstance(ddl_value, str):
            destination_schema_ddl = ddl_value

    feed_slice = db.scalar(
        select(FeedSlice)
        .where(
            FeedSlice.source_definition_id == feed_id,
            FeedSlice.status == "approved",
        )
        .order_by(FeedSlice.approved_at.desc().nullslast(), FeedSlice.created_at.desc())
    )
    if feed_slice is None:
        raise AuthApiError(
            "feed_slice_not_ready",
            "An approved FeedSlice is required before AI analysis.",
            409,
        )

    source_headers = _parse_header_csv(feed_slice.header_csv)

    if get_adapter is None:
        raise AuthApiError("ai_adapter_unavailable", "AI adapter dependency is unavailable.", 503)

    feed_analysis_payload = json.dumps(
        {
            "source_headers": source_headers,
            "destination_schema_ddl": destination_schema_ddl,
        }
    )
    feed_analysis_adapter = get_adapter("feed_analysis")
    analysis_result = feed_analysis_adapter.call(
        _FEED_ANALYSIS_SYSTEM_PROMPT,
        feed_analysis_payload,
        _FeedAnalysisResult,
    )

    created_fibers: list[ProjectFiber] = []
    domain_fibers: list[ProjectFiber] = []

    for lookup in analysis_result.lookups:
        fiber = ProjectFiber(
            feed_id=feed_id,
            project_id=project_id,
            fiber_type="lookup",
            fiber_key=lookup.lookup_name,
            status="deferred",
            source="auto",
        )
        db.add(fiber)
        created_fibers.append(fiber)

    for domain_object in analysis_result.domain_objects:
        fiber = ProjectFiber(
            feed_id=feed_id,
            project_id=project_id,
            fiber_type="domain_object",
            fiber_key=domain_object.destination_table,
            status="ai_running",
            source="auto",
        )
        db.add(fiber)
        created_fibers.append(fiber)
        domain_fibers.append(fiber)

    db.flush()

    for fiber in domain_fibers:
        field_mapping_payload = json.dumps(
            {
                "source_columns": source_headers,
                "destination_table": fiber.fiber_key,
                "destination_schema_ddl": destination_schema_ddl,
            }
        )
        field_mapping_adapter = get_adapter("field_mapping")
        field_mapping_result = field_mapping_adapter.call(
            _FIELD_MAPPING_SYSTEM_PROMPT,
            field_mapping_payload,
            _FieldMappingResult,
        )
        fiber.field_bindings = [
            binding.model_dump(mode="python") for binding in field_mapping_result.field_bindings
        ]
        fiber.status = "mapped"

    db.commit()

    for fiber in created_fibers:
        db.refresh(fiber)

    return [_fiber_response(fiber) for fiber in created_fibers]


def submit_lookup_inputs(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    project_id: str,
    body: LookupInputsRequest,
) -> FiberResponse:
    fiber = _require_lookup_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    if fiber.status != "deferred":
        raise AuthApiError("fiber_not_deferred", "Fiber must be in 'deferred' status.", 409)

    columns, dest_rows = _parse_destination_csv(body.destination_lookup_csv)
    dest_feed = LookupDestFeed(
        fiber_id=fiber.fiber_id,
        lookup_name=fiber.fiber_key,
        columns=columns,
    )
    db.add(dest_feed)
    db.flush()

    dest_entries: list[LookupDestEntry] = []
    for row in dest_rows:
        entry = LookupDestEntry(dest_feed_id=dest_feed.dest_feed_id, row_data=row)
        db.add(entry)
        dest_entries.append(entry)
    db.flush()

    source_entries: list[LookupSourceEntry] = []
    for value in body.source_values:
        entry = LookupSourceEntry(
            fiber_id=fiber.fiber_id,
            lookup_name=fiber.fiber_key,
            source_value=value,
            discovery_type="sample",
        )
        db.add(entry)
        source_entries.append(entry)
    db.flush()

    fiber.status = "inputs_ready"
    db.flush()

    adapter = get_adapter("lookup_mapping")
    user_message = json.dumps(
        {
            "source_values": [entry.source_value for entry in source_entries],
            "destination_rows": [
                {"entry_id": entry.entry_id, "row_data": entry.row_data}
                for entry in dest_entries
            ],
        }
    )
    ai_result = adapter.call(_LOOKUP_MAPPING_SYSTEM_PROMPT, user_message, _LookupMappingResult)

    source_entry_by_value = {entry.source_value: entry for entry in source_entries}
    dest_entry_by_id = {entry.entry_id: entry for entry in dest_entries}
    proposals_for_denorm: list[dict[str, Any]] = []

    for proposal in ai_result.proposals:
        source_entry = source_entry_by_value.get(proposal.source_value)
        if source_entry is None:
            continue
        dest_entry = dest_entry_by_id.get(proposal.dest_entry_id)
        mapping = LookupMapping(
            fiber_id=fiber.fiber_id,
            lookup_name=fiber.fiber_key,
            source_entry_id=source_entry.entry_id,
            source_value=proposal.source_value,
            dest_entry_id=proposal.dest_entry_id if dest_entry is not None else None,
            dest_row=dest_entry.row_data if dest_entry is not None else None,
            confidence_score=proposal.confidence_score,
            status="proposed",
            mapped_by="ai",
        )
        db.add(mapping)
        proposals_for_denorm.append(
            {
                "source_value": proposal.source_value,
                "dest_entry_id": proposal.dest_entry_id,
                "dest_row": dest_entry.row_data if dest_entry is not None else None,
                "confidence_score": proposal.confidence_score,
            }
        )

    fiber.proposed_mappings = proposals_for_denorm
    fiber.status = "mapped"

    db.commit()
    db.refresh(fiber)
    return _fiber_response(fiber)


def list_source_entries(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    project_id: str,
) -> list[LookupSourceEntryResponse]:
    fiber = _require_lookup_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    entries = db.scalars(
        select(LookupSourceEntry)
        .where(LookupSourceEntry.fiber_id == fiber.fiber_id)
        .order_by(LookupSourceEntry.created_at.asc())
    ).all()
    return [_source_entry_response(entry) for entry in entries]


def add_source_entries(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    project_id: str,
    body: LookupSourceEntriesCreateRequest,
) -> list[LookupSourceEntryResponse]:
    fiber = _require_lookup_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    new_entries: list[LookupSourceEntry] = []
    for value in body.values:
        entry = LookupSourceEntry(
            fiber_id=fiber.fiber_id,
            lookup_name=fiber.fiber_key,
            source_value=value,
            discovery_type=body.discovery_type,
        )
        db.add(entry)
        new_entries.append(entry)
    db.commit()
    for entry in new_entries:
        db.refresh(entry)
    return [_source_entry_response(entry) for entry in new_entries]


def create_or_replace_dest_feed(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    project_id: str,
    body: LookupDestFeedCreateRequest,
) -> LookupDestFeedResponse:
    fiber = _require_lookup_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    existing = db.scalar(select(LookupDestFeed).where(LookupDestFeed.fiber_id == fiber.fiber_id))
    if existing is not None:
        db.execute(delete(LookupDestEntry).where(LookupDestEntry.dest_feed_id == existing.dest_feed_id))
        db.delete(existing)
        db.flush()

    dest_feed = LookupDestFeed(
        fiber_id=fiber.fiber_id,
        lookup_name=fiber.fiber_key,
        columns=body.columns,
    )
    db.add(dest_feed)
    db.flush()

    for row in body.rows:
        db.add(LookupDestEntry(dest_feed_id=dest_feed.dest_feed_id, row_data=row))

    db.commit()
    db.refresh(dest_feed)
    return _dest_feed_response(dest_feed)


def list_dest_entries(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    project_id: str,
) -> list[LookupDestEntryResponse]:
    fiber = _require_lookup_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    dest_feed = _get_dest_feed(db, fiber_id=fiber.fiber_id)
    if dest_feed is None:
        return []
    entries = db.scalars(
        select(LookupDestEntry)
        .where(LookupDestEntry.dest_feed_id == dest_feed.dest_feed_id)
        .order_by(LookupDestEntry.created_at.asc())
    ).all()
    return [_dest_entry_response(entry) for entry in entries]


def list_mappings(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    project_id: str,
) -> list[LookupMappingResponse]:
    fiber = _require_lookup_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    mappings = db.scalars(
        select(LookupMapping)
        .where(LookupMapping.fiber_id == fiber.fiber_id)
        .order_by(LookupMapping.created_at.asc())
    ).all()
    return [_mapping_response(mapping) for mapping in mappings]


def patch_mapping(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    mapping_id: str,
    project_id: str,
    body: LookupMappingPatchRequest,
) -> LookupMappingResponse:
    fiber = _require_lookup_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    mapping = db.scalar(
        select(LookupMapping).where(
            LookupMapping.mapping_id == mapping_id,
            LookupMapping.fiber_id == fiber.fiber_id,
        )
    )
    if mapping is None:
        raise AuthApiError("mapping_not_found", "Mapping not found.", 404)

    dest_feed = _get_dest_feed(db, fiber_id=fiber.fiber_id)
    if dest_feed is None:
        raise AuthApiError("mapping_not_found", "Mapping not found.", 404)

    dest_entry = db.scalar(
        select(LookupDestEntry).where(
            LookupDestEntry.entry_id == body.dest_entry_id,
            LookupDestEntry.dest_feed_id == dest_feed.dest_feed_id,
        )
    )
    if dest_entry is None:
        raise AuthApiError("mapping_not_found", "Mapping not found.", 404)

    mapping.dest_entry_id = dest_entry.entry_id
    mapping.dest_row = dest_entry.row_data
    mapping.status = body.status
    mapping.mapped_by = "operator"

    db.commit()
    db.refresh(mapping)
    return _mapping_response(mapping)


def _require_lookup_fiber(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    project_id: str,
) -> ProjectFiber:
    _get_feed(db, project_id=project_id, feed_id=feed_id)
    fiber = db.scalar(
        select(ProjectFiber).where(
            ProjectFiber.fiber_id == fiber_id,
            ProjectFiber.feed_id == feed_id,
        )
    )
    if fiber is None:
        raise AuthApiError("fiber_not_found", "Fiber not found.", 404)
    if fiber.fiber_type != "lookup":
        raise AuthApiError("fiber_not_lookup", "Fiber is not a lookup fiber.", 409)
    return fiber


def _get_dest_feed(db: Session, *, fiber_id: str) -> LookupDestFeed | None:
    return db.scalar(select(LookupDestFeed).where(LookupDestFeed.fiber_id == fiber_id))


def _parse_destination_csv(csv_text: str) -> tuple[list[str], list[dict[str, Any]]]:
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    columns = list(reader.fieldnames or [])
    rows = [dict(row) for row in reader]
    return columns, rows


def _parse_header_csv(header_csv: str | None) -> list[str]:
    if not header_csv:
        return []
    return next(csv.reader([header_csv]), [])


def _get_feed(db: Session, *, project_id: str, feed_id: str) -> Feed:
    feed = db.get(Feed, feed_id)
    if feed is None or feed.project_id != project_id:
        raise AuthApiError("feed_not_found", "Feed not found.", 404)
    return feed


def _fiber_response(fiber: ProjectFiber) -> FiberResponse:
    return FiberResponse(
        fiber_id=fiber.fiber_id,
        feed_id=fiber.feed_id,
        project_id=fiber.project_id,
        fiber_type=fiber.fiber_type,
        fiber_key=fiber.fiber_key,
        status=fiber.status,
        source=fiber.source,
        proposed_mappings=fiber.proposed_mappings,
        field_bindings=fiber.field_bindings,
        output_sql=fiber.output_sql,
        created_at=fiber.created_at,
        updated_at=fiber.updated_at,
    )


def _source_entry_response(entry: LookupSourceEntry) -> LookupSourceEntryResponse:
    return LookupSourceEntryResponse(
        entry_id=entry.entry_id,
        fiber_id=entry.fiber_id,
        lookup_name=entry.lookup_name,
        source_value=entry.source_value,
        discovery_type=entry.discovery_type,
        created_at=entry.created_at,
    )


def _dest_feed_response(feed: LookupDestFeed) -> LookupDestFeedResponse:
    return LookupDestFeedResponse(
        dest_feed_id=feed.dest_feed_id,
        fiber_id=feed.fiber_id,
        lookup_name=feed.lookup_name,
        columns=feed.columns,
        created_at=feed.created_at,
    )


def _dest_entry_response(entry: LookupDestEntry) -> LookupDestEntryResponse:
    return LookupDestEntryResponse(
        entry_id=entry.entry_id,
        dest_feed_id=entry.dest_feed_id,
        row_data=entry.row_data,
        created_at=entry.created_at,
    )


def _mapping_response(mapping: LookupMapping) -> LookupMappingResponse:
    return LookupMappingResponse(
        mapping_id=mapping.mapping_id,
        fiber_id=mapping.fiber_id,
        lookup_name=mapping.lookup_name,
        source_entry_id=mapping.source_entry_id,
        source_value=mapping.source_value,
        dest_entry_id=mapping.dest_entry_id,
        dest_row=mapping.dest_row,
        confidence_score=mapping.confidence_score,
        status=mapping.status,
        mapped_by=mapping.mapped_by,
        created_at=mapping.created_at,
        updated_at=mapping.updated_at,
    )
