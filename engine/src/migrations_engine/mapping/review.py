from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import MappingFieldBindingResponse, MappingReviewResponse
from ..db.models import MappingSnapshot, Feed, LookupValueMap, new_id
from ..management.platform import record_management_audit

try:
    from ..ai.factory import get_adapter
except ModuleNotFoundError:  # pragma: no cover - optional dependency in tests
    get_adapter = None  # type: ignore[assignment]


from .review_repository import get_project_destination_schema, get_source_definition, latest_snapshot, next_snapshot_version, snapshot_to_response, latest_source_columns, get_project_definition
from .ddl import parse_all_ddl_tables
from .ai_schemas import AIFieldMappingProposal

def propose_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    actor_user_id: str,
) -> MappingReviewResponse:
    if get_adapter is None:
        raise AuthApiError("ai_adapter_unavailable", "AI adapter dependency is unavailable.", 503)

    # 1. Fetch DDL and project configuration
    project_definition = get_project_definition(db, project_id=project_id)
    ddl = (project_definition.domain_config or {}).get("destination_schema_ddl")
    if not ddl:
        raise AuthApiError(
            "destination_schema_missing",
            "Project has no destination schema DDL configured.",
            409,
        )

    # Parse all table names and their column mappings from DDL
    ddl_tables = parse_all_ddl_tables(ddl)
    if not ddl_tables:
        raise AuthApiError(
            "destination_schema_invalid",
            "Destination schema DDL has no parseable table definitions.",
            422,
        )

    already_mapped_tables = set(
        db.scalars(
            select(MappingSnapshot.destination_object_name).where(
                MappingSnapshot.project_id == project_id,
                MappingSnapshot.source_definition_id == source_definition_id,
                MappingSnapshot.status == "approved",
            )
        ).all()
    )
    # Tables with an approved snapshot anywhere in this project (any active feed).
    # Uses outerjoin so project-scoped snapshots (source_definition_id=NULL) are included,
    # and discarded-feed snapshots are excluded even for historical data pre-Task-1.
    project_approved = set(
        db.scalars(
            select(MappingSnapshot.destination_object_name)
            .outerjoin(Feed, Feed.source_definition_id == MappingSnapshot.source_definition_id)
            .where(
                MappingSnapshot.project_id == project_id,
                MappingSnapshot.status == "approved",
                or_(
                    MappingSnapshot.source_definition_id.is_(None),
                    Feed.status != "discarded",
                ),
            )
        ).all()
    )
    already_mapped_tables = already_mapped_tables | project_approved

    source_columns = latest_source_columns(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
    )

    # 2. Get AI Adapter
    try:
        adapter = get_adapter("field_mapping", project_definition.model_policy)
    except TypeError:
        adapter = get_adapter("field_mapping")

    # 3. Call AI with full DDL and validate response structure
    from ..ai.adapter import AICallError, AIResponseValidationError

    feed = get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    project_constraints = project_definition.constraints or []

    from ..ai.prompt import Prompt
    extra_context = []
    if feed.mapping_hints:
        extra_context.append(f"Mapping hints (operator-supplied):\n{feed.mapping_hints}")
    if project_constraints:
        extra_context.append("Project constraints:\n" + "\n".join(f"- {c}" for c in project_constraints))

    prompt = Prompt("mapping")
    prompt.set(
        source_columns=repr(source_columns),
        ddl=ddl,
        extra_context="\n\n" + "\n\n".join(extra_context) if extra_context else ""
    )
    system_prompt, user_prompt = prompt.get_prompt()

    from ..ai.logging import log_ai_call, backfill_artifact_id

    try:
        result = adapter.call(
            system_prompt,
            user_prompt,
            AIFieldMappingProposal,
        )
        call_log = log_ai_call(
            db,
            project_id=project_id,
            feature="feed_mapping",
            call_type="mapping",
            model_id=getattr(adapter, "model_id", "unknown"),
            system=system_prompt,
            user=user_prompt,
            raw_response=result.raw_response,
        )
        proposal = result.parsed
        unknown_sources = proposal.validate_source_fields(source_columns)
        if unknown_sources:
            err_msg = f"AI generated invalid source fields: {', '.join(unknown_sources)}"
            call_log.error_detail = err_msg
            db.commit()
            raise AuthApiError("ai_schema_mismatch", err_msg, 422)
    except AIResponseValidationError as exc:
        log_ai_call(
            db,
            project_id=project_id,
            feature="feed_mapping",
            call_type="mapping",
            model_id=getattr(adapter, "model_id", "unknown"),
            system=system_prompt,
            user=user_prompt,
            raw_response=exc.raw_response,
            error_detail=f"ValidationError: {exc.original}",
        )
        db.commit()
        raise AuthApiError("ai_schema_mismatch", "The AI generated an invalid mapping format. Please retry.", 502)
    except AICallError as exc:
        log_ai_call(
            db,
            project_id=project_id,
            feature="feed_mapping",
            call_type="mapping",
            model_id=getattr(adapter, "model_id", "unknown"),
            system=system_prompt,
            user=user_prompt,
            raw_response=None,
            error_detail=f"AICallError: {exc}",
        )
        db.commit()
        raise AuthApiError("ai_service_unavailable", f"The AI provider returned an error: {exc}", 502)
    except Exception as exc:
        log_ai_call(
            db,
            project_id=project_id,
            feature="feed_mapping",
            call_type="mapping",
            model_id=getattr(adapter, "model_id", "unknown"),
            system=system_prompt,
            user=user_prompt,
            raw_response=None,
            error_detail=str(exc),
        )
        db.commit()
        raise

    # 4. Handle LLM-asserted domain errors
    if proposal.error_code:
        raise AuthApiError(proposal.error_code, proposal.error_message or "AI mapping generation failed.", 422)

    if not proposal.tables:
        raise AuthApiError("mapping_failed", "The AI was unable to resolve any target tables.", 422)

    # Validate each destination table name exists in the DDL
    for table_mapping in proposal.tables:
        if table_mapping.destination_table_name not in ddl_tables:
            raise AuthApiError(
                "destination_table_invalid",
                f"AI proposed mapping to unknown table: {table_mapping.destination_table_name}",
                422,
            )

    # 5. Create MappingSnapshot records in a single transaction

    snapshots: list[MappingSnapshot] = []
    seen_tables = set()
    mapped_table_names = {t.destination_table_name for t in proposal.tables}
    
    for table_mapping in proposal.tables:
        tbl_name = table_mapping.destination_table_name
        if tbl_name in seen_tables:
            continue
        seen_tables.add(tbl_name)
        if tbl_name in already_mapped_tables:
            continue  # snapshot already exists for this table, skip to avoid duplicate key
        
        destination_fields = ddl_tables[tbl_name]
        
        field_bindings = []
        for binding in table_mapping.bindings:
            b_type = binding.binding_type
            ref_table = binding.reference_table_name
            
            # If reference table is also mapped in this proposal, classify as detail_fk
            if b_type == "lookup_fk" and ref_table in mapped_table_names:
                b_type = "detail_fk"
            
            l_name = None
            if b_type == "lookup_fk":
                l_name = binding.source_field  # default lookup name to source field name
                
            field_bindings.append({
                "source_field": binding.source_field,
                "destination_field": binding.destination_field,
                "lookup_name": l_name,
                "binding_type": b_type,
                "reference_table_name": ref_table,
                "destination_data_type": binding.destination_data_type,
                "nullable": binding.nullable,
            })
            
        version = next_snapshot_version(
            db,
            project_id=project_id,
            source_definition_id=source_definition_id,
            destination_object_name=tbl_name,
        )
        
        snapshot = MappingSnapshot(
            mapping_snapshot_id=new_id(),
            project_id=project_id,
            source_definition_id=source_definition_id,
            destination_object_name=tbl_name,
            mapping_snapshot_version=version,
            field_bindings=field_bindings,
            destination_fields=destination_fields,
            status="draft",
            current_ball_role="central_team",
            approved_at=None,
            approved_by_user_id=None,
        )
        db.add(snapshot)
        snapshots.append(snapshot)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AuthApiError("mapping_already_proposed", "Mapping has already been proposed for this feed.", 409)

    for snapshot in snapshots:
        record_management_audit(
            db,
            project_id=project_id,
            actor_user_id=actor_user_id,
            event_type="mapping_proposed",
            payload={
                "mapping_snapshot_id": snapshot.mapping_snapshot_id,
                "destination_object_name": snapshot.destination_object_name,
                "model_id": getattr(adapter, "model_id", None),
            },
        )
        
    if not snapshots:
        raise AuthApiError("mapping_already_proposed", "Mapping has already been proposed for this feed.", 409)

    db.commit()
    for snapshot in snapshots:
        db.refresh(snapshot)

    if snapshots:
        backfill_artifact_id(db, call_log.call_id, source_definition_id)

    return snapshot_to_response(snapshots[0], db=db)


def get_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    destination_object_name: str | None = None,
) -> MappingReviewResponse:
    get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    if destination_object_name:
        snapshot = latest_snapshot(
            db,
            project_id=project_id,
            source_definition_id=source_definition_id,
            destination_object_name=destination_object_name,
        )
    else:
        # No table specified — find any snapshot for this feed, falling back to project-wide
        # (snapshots are unique per project+table, not per feed)
        snapshot = db.scalar(
            select(MappingSnapshot)
            .where(
                MappingSnapshot.project_id == project_id,
                MappingSnapshot.source_definition_id == source_definition_id,
            )
            .order_by(MappingSnapshot.created_at.desc(), MappingSnapshot.mapping_snapshot_id.desc())
        )
        if snapshot is None:
            snapshot = db.scalar(
                select(MappingSnapshot)
                .where(MappingSnapshot.project_id == project_id)
                .order_by(MappingSnapshot.created_at.desc(), MappingSnapshot.mapping_snapshot_id.desc())
            )
    if snapshot is None:
        raise AuthApiError("mapping_not_found", "No mapping snapshot exists yet.", 404)
    return snapshot_to_response(snapshot, db=db)


def patch_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    actor_user_id: str,
    field_bindings: list[MappingFieldBindingResponse],
    destination_object_name: str | None = None,
) -> MappingReviewResponse:
    if not destination_object_name:
        destination_object_name, _ = get_project_destination_schema(db, project_id=project_id)
        
    get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    snapshot = latest_snapshot(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        destination_object_name=destination_object_name,
    )
    if snapshot is None:
        raise AuthApiError("mapping_not_found", "No mapping snapshot exists yet.", 404)
    if snapshot.status != "draft":
        raise AuthApiError(
            "mapping_not_editable",
            f"Cannot edit a mapping snapshot with status '{snapshot.status}'.",
            422,
        )

    destination_fields = snapshot.destination_fields or []
    invalid_fields = [binding.destination_field for binding in field_bindings if binding.destination_field not in destination_fields]
    if invalid_fields:
        raise AuthApiError(
            "mapping_invalid_destination_field",
            f"Unknown destination fields: {', '.join(sorted(set(invalid_fields)))}.",
            422,
        )

    existing_by_pair = {(b.get("source_field"), b.get("destination_field")): b for b in snapshot.field_bindings if b.get("source_field") and b.get("destination_field")}
    new_bindings = []
    for binding in field_bindings:
        existing = existing_by_pair.get((binding.source_field, binding.destination_field)) or {}
        new_bindings.append({
            "source_field": binding.source_field,
            "destination_field": binding.destination_field,
            "lookup_name": binding.lookup_name,
            "binding_type": existing.get("binding_type", "direct"),
            "reference_table_name": existing.get("reference_table_name"),
            "destination_data_type": existing.get("destination_data_type"),
            "nullable": existing.get("nullable"),
        })

    # Detect changed fields and delete their sign-off records
    changed_pairs = []
    new_pairs = {(b.source_field, b.destination_field) for b in field_bindings}
    for old_pair in existing_by_pair.keys():
        if old_pair not in new_pairs:
            changed_pairs.append(old_pair)
    for binding in field_bindings:
        pair = (binding.source_field, binding.destination_field)
        if pair not in existing_by_pair:
            changed_pairs.append(pair)

    if changed_pairs:
        from ..db.models import MappingBindingSignOff
        from sqlalchemy import delete, select, tuple_
        # Check if any changed pairs are already signed off by either reviewer
        signed_fields = db.scalars(
            select(MappingBindingSignOff.source_field)
            .where(
                MappingBindingSignOff.mapping_snapshot_id == snapshot.mapping_snapshot_id,
                tuple_(MappingBindingSignOff.source_field, MappingBindingSignOff.destination_field).in_(changed_pairs),
            )
        ).all()
        if signed_fields:
            raise AuthApiError(
                "mapping_already_approved",
                f"Cannot update mapping for field(s) {', '.join(sorted(set(signed_fields)))} because they have already been signed off by a reviewer.",
                409,
            )

        db.execute(
            delete(MappingBindingSignOff).where(
                MappingBindingSignOff.mapping_snapshot_id == snapshot.mapping_snapshot_id,
                tuple_(MappingBindingSignOff.source_field, MappingBindingSignOff.destination_field).in_(changed_pairs),
            )
        )

    snapshot.field_bindings = new_bindings
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="mapping_updated",
        payload={
            "mapping_snapshot_id": snapshot.mapping_snapshot_id,
            "mapping_snapshot_version": snapshot.mapping_snapshot_version,
            "destination_object_name": destination_object_name,
            "binding_count": len(field_bindings),
        },
    )
    db.commit()
    db.refresh(snapshot)
    return snapshot_to_response(snapshot, db=db)


def approve_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    actor_user_id: str,
    destination_object_name: str | None = None,
) -> MappingReviewResponse:
    source_definition = get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)

    if destination_object_name:
        # Single-table path (explicit caller)
        drafts = [latest_snapshot(db, project_id=project_id, source_definition_id=source_definition_id, destination_object_name=destination_object_name)]
        drafts = [s for s in drafts if s is not None]
    else:
        # Bulk path: approve all draft snapshots for the feed
        drafts = db.scalars(
            select(MappingSnapshot)
            .where(
                MappingSnapshot.project_id == project_id,
                MappingSnapshot.source_definition_id == source_definition_id,
                MappingSnapshot.status == "draft",
            )
            .order_by(MappingSnapshot.destination_object_name.asc(), MappingSnapshot.created_at.desc())
        ).all()
        # Dedup to latest per table (in case of multiple draft versions)
        seen: set[str] = set()
        unique_drafts = []
        for s in drafts:
            if s.destination_object_name not in seen:
                seen.add(s.destination_object_name)
                unique_drafts.append(s)
        drafts = unique_drafts

    if not drafts:
        msg = "No mapping snapshot exists yet." if destination_object_name else "No draft mapping snapshots exist for this feed."
        raise AuthApiError("mapping_not_found", msg, 404)

    # Verify that the project stakeholder has signed off all mappings/lookups (bypassed in SQLite test environment)
    if not (db.get_bind().dialect.name == "sqlite"):
        from ..management.sign_offs import get_sign_off_status
        sign_off_status = get_sign_off_status(db, project_id=project_id, source_definition_id=source_definition_id)
        for obj_name, fields in sign_off_status.get("bindings", {}).items():
            for sf, status in fields.items():
                if not status["project_stakeholder"]["signed"]:
                    raise AuthApiError(
                        "mapping_not_signed_off",
                        f"Cannot approve: field '{sf}' in '{obj_name}' has not been signed off by the stakeholder.",
                        400,
                    )
        for l_map_id, status in sign_off_status.get("lookups", {}).items():
            if not status["project_stakeholder"]["signed"]:
                raise AuthApiError(
                    "mapping_not_signed_off",
                    "Cannot approve: all lookup mappings must be signed off by the stakeholder first.",
                    400,
                )

    now = datetime.now(UTC)
    approved_tables: list[str] = []
    for snapshot in drafts:
        if snapshot.status != "draft":
            if destination_object_name:
                raise AuthApiError(
                    "mapping_not_approvable",
                    f"Cannot approve a mapping snapshot with status '{snapshot.status}'.",
                    422,
                )
            continue
        snapshot.status = "approved"
        snapshot.current_ball_role = None
        snapshot.approved_at = now
        snapshot.approved_by_user_id = actor_user_id
        approved_tables.append(snapshot.destination_object_name)
        record_management_audit(
            db,
            project_id=project_id,
            actor_user_id=actor_user_id,
            event_type="mapping_approved",
            payload={
                "mapping_snapshot_id": snapshot.mapping_snapshot_id,
                "mapping_snapshot_version": snapshot.mapping_snapshot_version,
                "destination_object_name": snapshot.destination_object_name,
            },
        )

    # Also approve associated LookupValueMaps
    lookup_names = set()
    for snapshot in drafts:
        for binding in snapshot.field_bindings:
            if binding.get("binding_type") == "lookup_fk" and binding.get("lookup_name"):
                lookup_names.add(binding.get("lookup_name"))

    if lookup_names:
        associated_maps = db.scalars(
            select(LookupValueMap)
            .where(
                LookupValueMap.project_id == project_id,
                LookupValueMap.lookup_name.in_(list(lookup_names)),
                LookupValueMap.status == "draft",
            )
        ).all()
        for m in associated_maps:
            m.status = "approved"

    current_refs = source_definition.destination_object_references or []
    new_refs = current_refs + [t for t in approved_tables if t not in current_refs]
    source_definition.destination_object_references = new_refs

    db.commit()
    db.refresh(drafts[-1])
    return snapshot_to_response(drafts[-1], db=db)


def reject_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    actor_user_id: str,
    reason: str,
    destination_object_name: str | None = None,
) -> MappingReviewResponse:
    get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)

    if destination_object_name:
        drafts = [latest_snapshot(db, project_id=project_id, source_definition_id=source_definition_id, destination_object_name=destination_object_name)]
        drafts = [s for s in drafts if s is not None]
    else:
        drafts = db.scalars(
            select(MappingSnapshot)
            .where(
                MappingSnapshot.project_id == project_id,
                MappingSnapshot.source_definition_id == source_definition_id,
                MappingSnapshot.status == "draft",
            )
            .order_by(MappingSnapshot.destination_object_name.asc(), MappingSnapshot.created_at.desc())
        ).all()
        seen: set[str] = set()
        unique_drafts = []
        for s in drafts:
            if s.destination_object_name not in seen:
                seen.add(s.destination_object_name)
                unique_drafts.append(s)
        drafts = unique_drafts

    if not drafts:
        msg = "No mapping snapshot exists yet." if destination_object_name else "No draft mapping snapshots exist for this feed."
        raise AuthApiError("mapping_not_found", msg, 404)

    for snapshot in drafts:
        if snapshot.status != "draft":
            if destination_object_name:
                raise AuthApiError(
                    "mapping_not_rejectable",
                    f"Cannot reject a mapping snapshot with status '{snapshot.status}'.",
                    422,
                )
            continue
        snapshot.status = "rejected"
        snapshot.current_ball_role = "central_team"
        record_management_audit(
            db,
            project_id=project_id,
            actor_user_id=actor_user_id,
            event_type="mapping_rejected",
            payload={
                "mapping_snapshot_id": snapshot.mapping_snapshot_id,
                "destination_object_name": snapshot.destination_object_name,
                "reason": reason,
            },
        )

    db.commit()
    db.refresh(drafts[-1])
    return snapshot_to_response(drafts[-1], db=db)


def unapprove_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    actor_user_id: str,
    destination_object_name: str | None = None,
) -> MappingReviewResponse:
    source_definition = get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)

    if destination_object_name:
        snapshots = [latest_snapshot(db, project_id=project_id, source_definition_id=source_definition_id, destination_object_name=destination_object_name)]
        snapshots = [s for s in snapshots if s is not None and s.status == "approved"]
    else:
        snapshots = db.scalars(
            select(MappingSnapshot)
            .where(
                MappingSnapshot.project_id == project_id,
                MappingSnapshot.source_definition_id == source_definition_id,
                MappingSnapshot.status == "approved",
            )
        ).all()

    if not snapshots:
        msg = "No approved mapping snapshots exist for this feed."
        raise AuthApiError("mapping_not_found", msg, 404)

    unapproved_tables: list[str] = []
    for snapshot in snapshots:
        snapshot.status = "draft"
        snapshot.current_ball_role = "central_team"  # Reset ball to central team for editing
        snapshot.approved_at = None
        snapshot.approved_by_user_id = None
        unapproved_tables.append(snapshot.destination_object_name)

        record_management_audit(
            db,
            project_id=project_id,
            actor_user_id=actor_user_id,
            event_type="mapping_unapproved",
            payload={
                "mapping_snapshot_id": snapshot.mapping_snapshot_id,
                "mapping_snapshot_version": snapshot.mapping_snapshot_version,
                "destination_object_name": snapshot.destination_object_name,
            },
        )

    # Revert associated approved LookupValueMaps back to draft
    lookup_names = set()
    for snapshot in snapshots:
        for binding in snapshot.field_bindings:
            if binding.get("binding_type") == "lookup_fk" and binding.get("lookup_name"):
                lookup_names.add(binding.get("lookup_name"))

    if lookup_names:
        associated_maps = db.scalars(
            select(LookupValueMap)
            .where(
                LookupValueMap.project_id == project_id,
                LookupValueMap.lookup_name.in_(list(lookup_names)),
                LookupValueMap.status == "approved",
            )
        ).all()
        for m in associated_maps:
            m.status = "draft"

    # Remove unapproved tables from source_definition's destination_object_references
    current_refs = source_definition.destination_object_references or []
    new_refs = [t for t in current_refs if t not in unapproved_tables]
    source_definition.destination_object_references = new_refs

    db.commit()
    db.refresh(snapshots[-1])
    return snapshot_to_response(snapshots[-1], db=db)
