from __future__ import annotations

import csv as _csv
import json as _json

from pydantic import BaseModel as _BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import FiberCreateRequest, FiberResponse
from ..db.models import Feed, ProjectFiber, new_id
from ..db.models import User

try:
    from ..ai.factory import get_adapter
except ModuleNotFoundError:  # pragma: no cover - optional SDK dependency may be absent in tests
    get_adapter = None  # type: ignore[assignment]


_FEED_ANALYSIS_SYSTEM = (
    "You are a data migration analyst. "
    "Given CSV column headers and a destination schema DDL, "
    "identify all lookup columns and domain objects. Return JSON."
)

_FIELD_MAPPING_SYSTEM = (
    "You are a field mapper. "
    "Given source columns and destination DDL, propose field bindings. Return JSON."
)


class _LookupIdentified(_BaseModel):
    column_name: str
    lookup_name: str


class _DomainObject(_BaseModel):
    destination_table: str


class _FeedAnalysisResult(_BaseModel):
    lookups: list[_LookupIdentified]
    domain_objects: list[_DomainObject]


class _FieldBinding(_BaseModel):
    source_field: str | None
    destination_field: str
    lookup_name: str | None


class _FieldMappingResult(_BaseModel):
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
        source=body.source,
        status="created",
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


def analyze_feed(db: Session, *, feed_id: str, project_id: str, actor: User) -> list[FiberResponse]:
    feed = _get_feed(db, project_id=project_id, feed_id=feed_id)

    from ..db.models import FeedSlice, ProjectDefinition, ProjectRegistry

    registry = db.get(ProjectRegistry, project_id)
    if registry is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)

    project_definition = db.get(ProjectDefinition, registry.definition_id)
    destination_schema_ddl = ""
    if project_definition is not None and project_definition.domain_config:
        destination_schema_ddl = str(project_definition.domain_config.get("destination_schema_ddl", ""))

    approved_slice = db.scalar(
        select(FeedSlice)
        .where(FeedSlice.source_definition_id == feed.source_definition_id)
        .where(FeedSlice.status == "approved")
        .order_by(FeedSlice.approved_at.desc().nullslast(), FeedSlice.created_at.desc())
    )
    if approved_slice is None:
        raise AuthApiError(
            "feed_slice_not_ready",
            "An approved FeedSlice is required before AI analysis.",
            409,
        )

    source_headers = _parse_header_csv(approved_slice.header_csv)
    if get_adapter is None:
        raise AuthApiError("ai_adapter_unavailable", "AI adapter dependency is unavailable.", 503)

    feed_analysis_adapter = get_adapter("feed_analysis")
    feed_analysis_result = feed_analysis_adapter.call(
        _FEED_ANALYSIS_SYSTEM,
        _json.dumps(
            {
                "source_headers": source_headers,
                "destination_schema_ddl": destination_schema_ddl,
            },
            ensure_ascii=False,
        ),
        _FeedAnalysisResult,
    )

    all_fibers: list[ProjectFiber] = []

    for lookup in feed_analysis_result.lookups:
        fiber = ProjectFiber(
            feed_id=feed.source_definition_id,
            project_id=project_id,
            fiber_type="lookup",
            fiber_key=lookup.lookup_name,
            status="deferred",
            source="auto",
        )
        db.add(fiber)
        all_fibers.append(fiber)

    domain_fibers: list[ProjectFiber] = []
    for domain_object in feed_analysis_result.domain_objects:
        fiber = ProjectFiber(
            feed_id=feed.source_definition_id,
            project_id=project_id,
            fiber_type="domain_object",
            fiber_key=domain_object.destination_table,
            status="ai_running",
            source="auto",
        )
        db.add(fiber)
        domain_fibers.append(fiber)
        all_fibers.append(fiber)

    db.flush()

    for fiber in domain_fibers:
        field_mapping_adapter = get_adapter("field_mapping")
        field_mapping_result = field_mapping_adapter.call(
            _FIELD_MAPPING_SYSTEM,
            _json.dumps(
                {
                    "source_columns": source_headers,
                    "destination_table": fiber.fiber_key,
                    "destination_schema_ddl": destination_schema_ddl,
                },
                ensure_ascii=False,
            ),
            _FieldMappingResult,
        )
        fiber.field_bindings = [binding.model_dump(mode="python") for binding in field_mapping_result.field_bindings]
        fiber.status = "mapped"

    db.commit()
    for fiber in all_fibers:
        db.refresh(fiber)
    return [_fiber_response(fiber) for fiber in all_fibers]


def _get_feed(db: Session, *, project_id: str, feed_id: str) -> Feed:
    feed = db.get(Feed, feed_id)
    if feed is None or feed.project_id != project_id:
        raise AuthApiError("feed_not_found", "Feed not found.", 404)
    return feed


def _parse_header_csv(header_csv: str | None) -> list[str]:
    if not header_csv:
        return []
    return next(_csv.reader([header_csv]))


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
