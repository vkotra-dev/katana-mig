from __future__ import annotations

import csv
import io
import json
import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from ..ai.factory import get_adapter
from ..ai.logging import log_ai_call, backfill_artifact_id
from ..ai.adapter import AIResponseValidationError
from ..api.deps import AuthApiError
from ..api.schemas import (
    FiberActionRequest,
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
from ..codegen.lookup_upsert import generate_lookup_upsert_sql
from ..db.models import (
    CodeGenerationArtifact,
    Feed,
    LookupDestEntry,
    LookupDestFeed,
    LookupMapping,
    LookupSourceEntry,
    LookupValueMap,
    ProjectDefinition,
    ProjectFiber,
    ProjectRegistry,
    User,
    new_id,
)
from ..mapping.exceptions import SnapshotNotFoundError
from ..mapping.snapshots import select_latest_approved_lookup_snapshot
from ..management.access import require_project_access
from ..roles import PROJECT_STAKEHOLDER_ROLE
from ..management.source_analysis import (
    _build_sample_text,
    _load_slice_rows,
    _parse_csv_row,
)


logger = logging.getLogger(__name__)


from typing import Literal

class _LookupIdentified(BaseModel):
    column_name: str
    lookup_name: str
    sample_values: list[str] = []


class _DomainObject(BaseModel):
    destination_table: str


class _FeedAnalysisResult(BaseModel):
    lookups: list[_LookupIdentified]
    domain_objects: list[_DomainObject]
    unmatched_columns: list[str] = []


class _FieldBinding(BaseModel):
    source_field: str | None
    destination_field: str
    lookup_name: str | None
    binding_type: Literal["direct", "lookup_fk", "detail_fk"] = "direct"
    reference_table_name: str | None = None
    destination_data_type: str | None = None


class _FieldMappingResult(BaseModel):
    field_bindings: list[_FieldBinding]
    unmatched_source_fields: list[str] = []


class _LookupProposal(BaseModel):
    dest_id: str  # business key from destination row (e.g. "3")
    dest_value: str  # human-readable label (e.g. "Approved")
    source_value: str | None  # matched source value, or None if no confident match
    confidence_score: float


class _LookupMappingResult(BaseModel):
    proposals: list[_LookupProposal]
    unmatched_source_values: list[str] = []


def create_fiber(
    db: Session,
    *,
    actor: User,
    project_id: str,
    feed_id: str,
    body: FiberCreateRequest,
) -> FiberResponse:
    feed = _get_feed(db, project_id=project_id, feed_id=feed_id)
    status = "deferred" if body.fiber_type == "lookup" else "created"
    fiber = ProjectFiber(
        fiber_id=new_id(),
        feed_id=feed.source_definition_id,
        project_id=project_id,
        fiber_type=body.fiber_type,
        fiber_key=body.fiber_key,
        source=body.source,
        status=status,
    )
    db.add(fiber)
    db.commit()
    db.refresh(fiber)
    return _fiber_response(fiber)


def list_fibers(db: Session, *, project_id: str, feed_id: str) -> list[FiberResponse]:
    _get_feed(db, project_id=project_id, feed_id=feed_id)
    
    # Auto-heal missing fibers from existing snapshots
    from ..db.models import MappingSnapshot, LookupValueMap
    snapshots = db.scalars(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id == feed_id,
        )
    ).all()
    
    existing_fibers = db.scalars(
        select(ProjectFiber)
        .where(ProjectFiber.project_id == project_id)
        .where(ProjectFiber.feed_id == feed_id)
    ).all()
    
    existing_keys = {(f.fiber_type, f.fiber_key) for f in existing_fibers}
    healed = False
    
    for snapshot in snapshots:
        # 1. Ensure domain_object fiber exists for the destination table
        tbl_name = snapshot.destination_object_name
        expected_status = "mapped"
        if snapshot.status == "approved":
            expected_status = "business_approved"
        elif snapshot.current_ball_role == "project_stakeholder":
            expected_status = "operator_assigned"

        if ("domain_object", tbl_name) not in existing_keys:
            fiber = ProjectFiber(
                project_id=project_id,
                feed_id=feed_id,
                fiber_type="domain_object",
                fiber_key=tbl_name,
                status=expected_status,
                source="auto",
            )
            db.add(fiber)
            existing_keys.add(("domain_object", tbl_name))
            healed = True
            
        # 2. Ensure lookup fiber exists for any lookup_fk bindings
        for binding in (snapshot.field_bindings or []):
            if binding.get("binding_type") == "lookup_fk" and binding.get("lookup_name"):
                l_name = binding["lookup_name"]
                if ("lookup", l_name) not in existing_keys:
                    fiber = ProjectFiber(
                        project_id=project_id,
                        feed_id=feed_id,
                        fiber_type="lookup",
                        fiber_key=l_name,
                        status="deferred",
                        source="auto",
                    )
                    db.add(fiber)
                    existing_keys.add(("lookup", l_name))
                    healed = True

    # Refresh list of existing fibers after addition to sync status
    if healed:
        db.flush()
        existing_fibers = db.scalars(
            select(ProjectFiber)
            .where(ProjectFiber.project_id == project_id)
            .where(ProjectFiber.feed_id == feed_id)
        ).all()

    # Auto-sync existing fiber statuses
    for f in existing_fibers:
        if f.fiber_type == "domain_object":
            snap = next((s for s in snapshots if s.destination_object_name == f.fiber_key), None)
            if snap:
                expected = f.status
                if snap.status == "approved":
                    if f.status not in ("operator_triggered", "codegen_complete"):
                        expected = "business_approved"
                elif snap.current_ball_role == "project_stakeholder":
                    expected = "operator_assigned"
                else:
                    expected = "mapped"
                
                # Check sign-off status to see if it's already signed by both
                if expected == "mapped" or expected == "operator_assigned":
                    from ..management.sign_offs import get_sign_off_status
                    sig_status = get_sign_off_status(db, project_id=project_id, source_definition_id=feed_id)
                    table_fields = sig_status.get("bindings", {}).get(f.fiber_key, {})
                    if table_fields:
                        all_stakeholder_signed = all(
                            dest_st["project_stakeholder"]["signed"] 
                            for sf_dests in table_fields.values() 
                            for dest_st in sf_dests.values()
                        )
                        all_operator_signed = all(
                            dest_st["central_team"]["signed"] 
                            for sf_dests in table_fields.values() 
                            for dest_st in sf_dests.values()
                        )
                        if all_stakeholder_signed and all_operator_signed:
                            # It is fully approved by business, but overall snapshot approval has not been clicked yet
                            # However, since both roles signed all columns, it's essentially business_approved / operator_assigned
                            pass
                
                if f.status != expected:
                    f.status = expected
                    healed = True
        elif f.fiber_type == "lookup":
            val_map = db.scalar(
                select(LookupValueMap)
                .where(
                    LookupValueMap.project_id == project_id,
                    LookupValueMap.lookup_name == f.fiber_key,
                )
                .order_by(LookupValueMap.created_at.desc(), LookupValueMap.lookup_value_map_id.desc())
            )
            if not val_map:
                # If there's no lookup value map, but we have proposed mappings, auto-create a draft value map
                if f.proposed_mappings:
                    source_value_map = {}
                    destination_table = []
                    seen_dest_ids = set()
                    for pm in f.proposed_mappings:
                        src_val = pm.get("source_value")
                        dest_row_data = pm.get("dest_row")
                        dest_entry_id = pm.get("dest_entry_id")
                        if src_val:
                            # Prefer business key from dest_row; fall back to UUID from dest_entry_id
                            business_key = (dest_row_data and (dest_row_data.get("id") or dest_row_data.get("destination_id"))) or (dest_entry_id and str(dest_entry_id))
                            if business_key:
                                source_value_map[src_val] = business_key
                        if dest_row_data:
                            row_id = dest_row_data.get("id") or dest_row_data.get("destination_id")
                            if row_id and row_id not in seen_dest_ids:
                                seen_dest_ids.add(row_id)
                                destination_table.append(dest_row_data)
                    val_map = LookupValueMap(
                        lookup_value_map_id=new_id(),
                        project_id=project_id,
                        lookup_name=f.fiber_key,
                        destination_table=destination_table,
                        source_value_map=source_value_map,
                        status="draft",
                    )
                    db.add(val_map)
                    healed = True

            if val_map:
                expected = f.status
                if val_map.status == "approved":
                    if f.status not in ("operator_triggered", "codegen_complete"):
                        expected = "business_approved"
                elif val_map.status == "draft":
                    from ..management.sign_offs import get_sign_off_status
                    sig_status = get_sign_off_status(db, project_id=project_id, source_definition_id=feed_id)
                    lookup_status = sig_status.get("lookups", {}).get(val_map.lookup_value_map_id)
                    if lookup_status:
                        if lookup_status["project_stakeholder"]["signed"]:
                            expected = "business_approved"
                        elif lookup_status["central_team"]["signed"]:
                            expected = "operator_assigned"
                        else:
                            expected = "deferred"
                if f.status != expected:
                    f.status = expected
                    healed = True
            else:
                if f.status != "deferred":
                    f.status = "deferred"
                    healed = True
                    
    if healed:
        db.commit()

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


def assign_fiber(
    db: Session,
    *,
    actor: User,
    project_id: str,
    feed_id: str,
    fiber_id: str,
    body: FiberActionRequest,
) -> FiberResponse:
    del actor, body
    fiber = _require_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    if fiber.status != "mapped":
        raise AuthApiError("fiber_not_ready", "Fiber is not in the expected state.", 409)
    fiber.status = "operator_assigned"
    db.commit()
    db.refresh(fiber)
    return _fiber_response(fiber)


def _bridge_lookup_fiber_to_value_map(db: Session, fiber: ProjectFiber) -> None:
    """
    After a lookup fiber is approved, compile fiber.proposed_mappings JSON
    into LookupValueMap so generate_lookup_snapshot can proceed.
    One LookupValueMap upserted per lookup_name on the fiber.
    """
    if not fiber.proposed_mappings:
        return

    source_value_map: dict[str, str] = {}
    seen_dest_ids: set[str] = set()
    dest_entries: list[dict[str, Any]] = []

    for pm in fiber.proposed_mappings:
        src_val = pm.get("source_value")
        dest_row = pm.get("dest_row") or {}
        dest_id = dest_row.get("id")

        if src_val and dest_id:
            source_value_map[src_val] = str(dest_id)

        if dest_id and str(dest_id) not in seen_dest_ids:
            seen_dest_ids.add(str(dest_id))
            dest_entries.append({
                "id": str(dest_id),
                "label": dest_row.get("label") or str(dest_id),
            })

    # Find existing draft for this project + lookup_name and merge
    existing = db.scalar(
        select(LookupValueMap).where(
            LookupValueMap.project_id == fiber.project_id,
            LookupValueMap.lookup_name == fiber.fiber_key,
            LookupValueMap.status == "draft",
        ).order_by(LookupValueMap.created_at.desc())
    )
    if existing:
        new_source_value_map = dict(existing.source_value_map)
        for src, dest in source_value_map.items():
            if src not in new_source_value_map:
                new_source_value_map[src] = dest
        existing.source_value_map = new_source_value_map

        existing_dest_ids = {
            r.get("id") for r in existing.destination_table if r.get("id")
        }
        new_dest_table = list(existing.destination_table)
        for row in dest_entries:
            row_id = row.get("id")
            if row_id not in existing_dest_ids:
                new_dest_table.append(row)
        existing.destination_table = new_dest_table
    else:
        db.add(LookupValueMap(
            lookup_value_map_id=new_id(),
            project_id=fiber.project_id,
            lookup_name=fiber.fiber_key,
            destination_table=dest_entries,
            source_value_map=source_value_map,
            status="draft",
        ))


def approve_fiber(
    db: Session,
    *,
    actor: User,
    project_id: str,
    feed_id: str,
    fiber_id: str,
    body: FiberActionRequest,
) -> FiberResponse:
    del body
    require_project_access(db, user=actor, project_id=project_id)
    if actor.role != PROJECT_STAKEHOLDER_ROLE:
        raise AuthApiError(
            "forbidden",
            "Business approval requires project_stakeholder role.",
            403,
        )
    fiber = _require_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    if fiber.status != "operator_assigned":
        raise AuthApiError("fiber_not_ready", "Fiber is not in the expected state.", 409)
    fiber.status = "business_approved"
    if fiber.fiber_type == "lookup":
        _bridge_lookup_fiber_to_value_map(db, fiber)
    db.commit()
    db.refresh(fiber)
    return _fiber_response(fiber)


def trigger_fiber(
    db: Session,
    *,
    actor: User,
    project_id: str,
    feed_id: str,
    fiber_id: str,
    body: FiberActionRequest,
) -> FiberResponse:
    del actor, body
    fiber = _require_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    if fiber.status != "business_approved":
        raise AuthApiError("fiber_not_ready", "Fiber is not in the expected state.", 409)

    if fiber.fiber_type == "lookup":
        try:
            snapshot = select_latest_approved_lookup_snapshot(
                db,
                project_id=project_id,
                lookup_name=fiber.fiber_key,
            )
        except SnapshotNotFoundError:
            logger.warning("Skipping lookup codegen for %s: no approved snapshot found.", fiber.fiber_key)
            fiber.status = "operator_triggered"
            db.commit()
            db.refresh(fiber)
            return _fiber_response(fiber)

        target_db_engine = _get_target_db_engine(db, project_id=project_id)
        sql_bundle = generate_lookup_upsert_sql(
            fiber.fiber_key,
            snapshot.value_map or {},
            target_db_engine,
        )
        destination_object_name = f"0000_{fiber.fiber_key}"
        _supersede_lookup_artifact(
            db,
            project_id=project_id,
            destination_object_name=destination_object_name,
        )
        db.add(
            CodeGenerationArtifact(
                codegen_artifact_id=new_id(),
                project_id=project_id,
                destination_object_name=destination_object_name,
                run_id=None,
                source_slice_version=None,
                mapping_snapshot_version=None,
                lookup_snapshot_version=snapshot.lookup_snapshot_version,
                sql_bundle=sql_bundle,
                status="active",
            )
        )
        fiber.output_sql = sql_bundle
        fiber.status = "codegen_complete"
    else:
        fiber.status = "operator_triggered"

        fiber_key = fiber.fiber_key
        db.flush()

        remaining = db.scalar(
            select(func.count(ProjectFiber.fiber_id)).where(
                ProjectFiber.project_id == project_id,
                ProjectFiber.fiber_key == fiber_key,
                ProjectFiber.status != "operator_triggered",
            )
        )
        should_queue = (remaining or 0) == 0

        if should_queue:
            logger.info("codegen queued for %s", fiber_key)

    db.commit()
    db.refresh(fiber)

    return _fiber_response(fiber)


def _get_target_db_engine(db: Session, *, project_id: str) -> str | None:
    registry = db.get(ProjectRegistry, project_id)
    if registry is None:
        return None
    definition = db.get(ProjectDefinition, registry.definition_id)
    if definition is None:
        return None
    domain_config = definition.domain_config or {}
    return domain_config.get("target_db_engine")


def _supersede_lookup_artifact(db: Session, *, project_id: str, destination_object_name: str) -> None:
    now = datetime.now(UTC)
    db.execute(
        update(CodeGenerationArtifact)
        .where(
            CodeGenerationArtifact.project_id == project_id,
            CodeGenerationArtifact.destination_object_name == destination_object_name,
            CodeGenerationArtifact.status == "active",
        )
        .values(status="superseded", superseded_at=now)
    )


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
        .order_by(FeedSlice.approved_at.is_(None), FeedSlice.approved_at.desc(), FeedSlice.created_at.desc())
    )
    if approved_slice is None:
        raise AuthApiError(
            "feed_slice_not_ready",
            "An approved FeedSlice is required before AI analysis.",
            409,
        )

    source_headers = _parse_header_csv(approved_slice.header_csv)

    _policy = feed.sample_policy or {}
    _limit = int(_policy.get("max_rows") or 10)
    raw_rows = _load_slice_rows(db, source_slice_id=approved_slice.source_slice_id, limit=_limit)
    if approved_slice.header_csv and raw_rows:
        from ..intake.masking import mask_row
        _headers = _parse_csv_row(approved_slice.header_csv)
        raw_rows = [mask_row(_headers, _parse_csv_row(r)) for r in raw_rows]
    sample_text = _build_sample_text(header_csv=approved_slice.header_csv, rows=raw_rows)

    try:
        feed_analysis_adapter = get_adapter("feed_analysis", project_definition.model_policy)
    except TypeError:
        feed_analysis_adapter = get_adapter("feed_analysis")
    n_rows = len(raw_rows)
    from ..ai.prompt import Prompt
    prompt1 = Prompt("feed_domain_object_analysis")
    prompt1.set(
        feed_id=feed.source_definition_id,
        n_rows=str(n_rows),
        sample_text=sample_text,
        destination_schema_ddl=destination_schema_ddl,
    )
    system_prompt, user_prompt = prompt1.get_prompt()
    try:
        result = feed_analysis_adapter.call(
            system_prompt,
            user_prompt,
            _FeedAnalysisResult,
        )
        call_log1 = log_ai_call(
            db,
            project_id=project_id,
            feature="feed_mapping",
            call_type="feed_analysis",
            model_id=feed_analysis_adapter.model_id,
            system=system_prompt,
            user=user_prompt,
            raw_response=result.raw_response,
        )
        backfill_artifact_id(db, call_log1.call_id, feed.source_definition_id)
        feed_analysis_result = result.parsed
    except AIResponseValidationError as exc:
        log_ai_call(
            db,
            project_id=project_id,
            feature="feed_mapping",
            call_type="feed_analysis",
            model_id=feed_analysis_adapter.model_id,
            system=system_prompt,
            user=user_prompt,
            raw_response=exc.raw_response,
            error_detail=f"ValidationError: {exc.original}",
        )
        db.commit()
        raise exc
    except Exception as exc:
        log_ai_call(
            db,
            project_id=project_id,
            feature="feed_mapping",
            call_type="feed_analysis",
            model_id=feed_analysis_adapter.model_id,
            system=system_prompt,
            user=user_prompt,
            raw_response=None,
            error_detail=str(exc),
        )
        db.commit()
        raise

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
        try:
            field_mapping_adapter = get_adapter("field_mapping", project_definition.model_policy)
        except TypeError:
            field_mapping_adapter = get_adapter("field_mapping")
        prompt2 = Prompt("feed_field_mapping")
        prompt2.set(
            feed_id=feed.source_definition_id,
            fiber_key=fiber.fiber_key,
            n_rows=str(n_rows),
            sample_text=sample_text,
            destination_schema_ddl=destination_schema_ddl,
        )
        system_prompt2, user_prompt2 = prompt2.get_prompt()
        try:
            result2 = field_mapping_adapter.call(
                system_prompt2,
                user_prompt2,
                _FieldMappingResult,
            )
            call_log2 = log_ai_call(
                db,
                project_id=project_id,
                feature="feed_mapping",
                call_type="feed_analysis",
                model_id=field_mapping_adapter.model_id,
                system=system_prompt2,
                user=user_prompt2,
                raw_response=result2.raw_response,
            )
            field_mapping_result = result2.parsed
            backfill_artifact_id(db, call_log2.call_id, fiber.feed_id)
        except AIResponseValidationError as exc:
            log_ai_call(
                db,
                project_id=project_id,
                feature="feed_mapping",
                call_type="feed_analysis",
                model_id=field_mapping_adapter.model_id,
                system=system_prompt2,
                user=user_prompt2,
                raw_response=exc.raw_response,
                error_detail=f"ValidationError: {exc.original}",
            )
            db.commit()
            raise exc
        except Exception as exc:
            log_ai_call(
                db,
                project_id=project_id,
                feature="feed_mapping",
                call_type="feed_analysis",
                model_id=field_mapping_adapter.model_id,
                system=system_prompt2,
                user=user_prompt2,
                raw_response=None,
                error_detail=str(exc),
            )
            db.commit()
            raise
        fiber.field_bindings = [binding.model_dump(mode="python") for binding in field_mapping_result.field_bindings]
        fiber.status = "mapped"

    db.commit()
    for fiber in all_fibers:
        db.refresh(fiber)
    return [_fiber_response(fiber) for fiber in all_fibers]
def submit_lookup_inputs(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    project_id: str,
    body: LookupInputsRequest,
) -> FiberResponse:
    fiber = _require_lookup_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    if fiber.status not in ("deferred", "mapped", "inputs_ready"):
        raise AuthApiError(
            "fiber_not_deferred",
            "Fiber must be in 'deferred', 'inputs_ready', or 'mapped' status.",
            409,
        )

    # Clean up source entries for this fiber to allow re-analysis
    db.execute(
        delete(LookupSourceEntry).where(
            LookupSourceEntry.fiber_id == fiber.fiber_id,
        )
    )
    db.flush()

    columns, dest_rows = _parse_destination_csv(body.destination_lookup_csv)
    
    # Use existing dest feed if it exists, otherwise create a new one
    existing_dest_feed = db.scalar(select(LookupDestFeed).where(LookupDestFeed.fiber_id == fiber.fiber_id))
    if existing_dest_feed is None:
        dest_feed = LookupDestFeed(
            fiber_id=fiber.fiber_id,
            lookup_name=fiber.fiber_key,
            columns=columns,
        )
        db.add(dest_feed)
        db.flush()
    else:
        dest_feed = existing_dest_feed

    dest_entries: list[LookupDestEntry] = []
    for row in dest_rows:
        entry = LookupDestEntry(dest_feed_id=dest_feed.dest_feed_id, row_data=row)
        db.add(entry)
        dest_entries.append(entry)
    db.flush()

    source_entries: list[LookupSourceEntry] = []
    for source_value in body.source_values:
        entry = LookupSourceEntry(
            fiber_id=fiber.fiber_id,
            lookup_name=fiber.fiber_key,
            source_value=source_value,
            discovery_type="sample",
        )
        db.add(entry)
        source_entries.append(entry)
    db.flush()

    fiber.status = "inputs_ready"
    db.flush()

    registry = db.get(ProjectRegistry, project_id)
    if registry is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)
    project_definition = db.get(ProjectDefinition, registry.definition_id)
    if project_definition is None:
        raise AuthApiError("project_definition_not_found", "Project definition not found.", 404)
    model_policy = project_definition.model_policy

    try:
        adapter = get_adapter("lookup_mapping", model_policy)
    except TypeError:
        adapter = get_adapter("lookup_mapping")

    # Deduplicate destination rows by content before sending to AI
    seen_sigs: set[str] = set()
    deduped_dest_entries: list[LookupDestEntry] = []
    for entry in dest_entries:
        sig = json.dumps(entry.row_data, sort_keys=True)
        if sig not in seen_sigs:
            seen_sigs.add(sig)
            deduped_dest_entries.append(entry)

    payload = json.dumps(
        {
            "source_values": [entry.source_value for entry in source_entries],
            "destination_rows": [entry.row_data for entry in deduped_dest_entries],
        }
    )
    from ..ai.prompt import Prompt
    prompt3 = Prompt("lookup_mapping")
    prompt3.set(payload=payload)
    system_prompt3, user_prompt3 = prompt3.get_prompt()
    try:
        result3 = adapter.call(
            system_prompt3,
            user_prompt3,
            _LookupMappingResult,
        )
        call_log3 = log_ai_call(
            db,
            project_id=project_id,
            feature="feed_mapping",
            call_type="lookup_mapping",
            model_id=adapter.model_id,
            system=system_prompt3,
            user=user_prompt3,
            raw_response=result3.raw_response,
        )
        ai_result = result3.parsed
        backfill_artifact_id(db, call_log3.call_id, fiber.feed_id)
    except AIResponseValidationError as exc:
        log_ai_call(
            db,
            project_id=project_id,
            feature="feed_mapping",
            call_type="lookup_mapping",
            model_id=adapter.model_id,
            system=system_prompt3,
            user=user_prompt3,
            raw_response=exc.raw_response,
            error_detail=f"ValidationError: {exc.original}",
        )
        db.commit()
        raise exc
    except Exception as exc:
        log_ai_call(
            db,
            project_id=project_id,
            feature="feed_mapping",
            call_type="lookup_mapping",
            model_id=adapter.model_id,
            system=system_prompt3,
            user=user_prompt3,
            raw_response=None,
            error_detail=str(exc),
        )
        db.commit()
        raise

    proposals_for_denorm: list[dict[str, Any]] = []

    for proposal in ai_result.proposals:
        dest_row = {
            "id": proposal.dest_id,
            "label": proposal.dest_value,
        }
        proposals_for_denorm.append(
            {
                "source_value": proposal.source_value,
                "dest_row": dest_row,
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
    entries: list[LookupSourceEntry] = []
    for source_value in body.values:
        entry = LookupSourceEntry(
            fiber_id=fiber.fiber_id,
            lookup_name=fiber.fiber_key,
            source_value=source_value,
            discovery_type=body.discovery_type,
        )
        db.add(entry)
        entries.append(entry)
    db.commit()
    for entry in entries:
        db.refresh(entry)
    return [_source_entry_response(entry) for entry in entries]


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

    dest_feed = LookupDestFeed(fiber_id=fiber.fiber_id, lookup_name=fiber.fiber_key, columns=body.columns)
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
    dest_feed = db.scalar(select(LookupDestFeed).where(LookupDestFeed.fiber_id == fiber.fiber_id))
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
    # Check if this lookup has already been signed off by either reviewer
    from ..db.models import LookupValueMap, LookupSignOff
    value_map = db.scalar(
        select(LookupValueMap)
        .where(
            LookupValueMap.project_id == project_id,
            LookupValueMap.lookup_name == fiber.fiber_key,
        )
        .order_by(LookupValueMap.created_at.desc(), LookupValueMap.lookup_value_map_id.desc())
    )
    if value_map is not None:
        has_sign_off = db.scalar(
            select(LookupSignOff)
            .where(LookupSignOff.lookup_value_map_id == value_map.lookup_value_map_id)
            .limit(1)
        ) is not None
        if has_sign_off:
            raise AuthApiError(
                "lookup_already_approved",
                f"Cannot update mappings for lookup '{fiber.fiber_key}' because it has already been signed off by a reviewer.",
                409,
            )

    mapping = db.scalar(
        select(LookupMapping).where(
            LookupMapping.mapping_id == mapping_id,
            LookupMapping.fiber_id == fiber.fiber_id,
        )
    )
    if mapping is None:
        raise AuthApiError("mapping_not_found", "Mapping not found.", 404)

    dest_entry = db.get(LookupDestEntry, body.dest_entry_id)

    # If source_value explicitly provided and no source_entry exists, create one
    if body.is_source_value_set() and body.source_value is not None and mapping.source_entry_id is None:
        src_entry = LookupSourceEntry(
            fiber_id=fiber.fiber_id,
            lookup_name=fiber.fiber_key,
            source_value=body.source_value,
            discovery_type="manual",
        )
        db.add(src_entry)
        db.flush()
        mapping.source_entry_id = src_entry.entry_id

    if body.is_source_value_set():
        mapping.source_value = body.source_value
    mapping.dest_entry_id = body.dest_entry_id
    mapping.status = body.status if body.status else ("confirmed" if body.source_value else "unmatched")
    if dest_entry is not None:
        from .lookup_mapping import _extract_destination_label
        row_data = dest_entry.row_data or {}
        mapping.dest_row = {
            "id": str(row_data.get("id", dest_entry.entry_id)),
            "label": _extract_destination_label(row_data),
        }
    else:
        mapping.dest_row = None
    mapping.mapped_by = "operator"

    db.commit()
    db.refresh(mapping)
    return _mapping_response(mapping)


def _get_feed(db: Session, *, project_id: str, feed_id: str) -> Feed:
    feed = db.get(Feed, feed_id)
    if feed is None or feed.project_id != project_id:
        raise AuthApiError("feed_not_found", "Feed not found.", 404)
    return feed


def _require_fiber(
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
            ProjectFiber.project_id == project_id,
        )
    )
    if fiber is None:
        raise AuthApiError("fiber_not_found", "Fiber not found.", 404)
    return fiber


def _parse_header_csv(header_csv: str | None) -> list[str]:
    if not header_csv:
        return []
    return next(csv.reader([header_csv]))


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
            ProjectFiber.project_id == project_id,
        )
    )
    if fiber is None:
        raise AuthApiError("fiber_not_found", "Fiber not found.", 404)
    if fiber.fiber_type != "lookup":
        raise AuthApiError("fiber_not_lookup", "Fiber is not a lookup fiber.", 409)
    return fiber


def _parse_destination_csv(csv_text: str) -> tuple[list[str], list[dict[str, Any]]]:
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    columns = list(reader.fieldnames or [])
    rows = [dict(row) for row in reader]
    return columns, rows


def _source_entry_response(entry: LookupSourceEntry) -> LookupSourceEntryResponse:
    return LookupSourceEntryResponse(
        entry_id=entry.entry_id,
        fiber_id=entry.fiber_id,
        lookup_name=entry.lookup_name,
        source_value=entry.source_value,
        discovery_type=entry.discovery_type,
        created_at=entry.created_at,
    )


def _dest_feed_response(dest_feed: LookupDestFeed) -> LookupDestFeedResponse:
    return LookupDestFeedResponse(
        dest_feed_id=dest_feed.dest_feed_id,
        fiber_id=dest_feed.fiber_id,
        lookup_name=dest_feed.lookup_name,
        columns=dest_feed.columns,
        created_at=dest_feed.created_at,
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
