from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from ..db.models import Feed

from ..api.deps import AuthApiError
from ..api.schemas import MappingReviewResponse
from ..db.models import MappingSnapshot, new_id
from ..management.platform import record_management_audit

from .ai_schemas import AIFieldMappingProposal
from ..ai.prompt import Prompt


from .review_repository import (
    get_project_definition,
    get_source_definition,
    latest_source_columns,
    next_snapshot_version,
    snapshot_to_response,
)

try:
    from ..ai.factory import get_adapter
except ModuleNotFoundError:  # pragma: no cover - optional dependency in tests
    get_adapter = None  # type: ignore[assignment]


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
            artifact_id=source_definition_id,
        )
        db.commit()
        proposal = result.parsed
        unknown_sources = proposal.validate_source_fields(source_columns)
        if unknown_sources:
            err_msg = f"AI generated invalid source fields: {', '.join(unknown_sources)}"
            call_log.error_detail = err_msg
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

    # 5. Create or Patch MappingSnapshot records in a single transaction
    
    existing_drafts = {
        s.destination_object_name: s
        for s in db.scalars(
            select(MappingSnapshot).where(
                MappingSnapshot.project_id == project_id,
                MappingSnapshot.source_definition_id == source_definition_id,
                MappingSnapshot.status == "draft",
            )
        ).all()
    }
    
    draft_ids = [s.mapping_snapshot_id for s in existing_drafts.values()]
    signed_off_pairs = set()
    if draft_ids:
        from ..db.models import MappingBindingSignOff
        sign_offs = db.scalars(
            select(MappingBindingSignOff).where(
                MappingBindingSignOff.mapping_snapshot_id.in_(draft_ids)
            )
        ).all()
        for so in sign_offs:
            signed_off_pairs.add((so.mapping_snapshot_id, so.source_field, so.destination_field))

    from sqlalchemy.orm.attributes import flag_modified
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
        
        destination_columns = [c.model_dump() for c in table_mapping.all_columns]
        destination_fields = [c["name"] for c in destination_columns]
        
        fresh_bindings = []
        for binding in table_mapping.bindings:
            b_type = binding.binding_type
            ref_table = binding.reference_table_name
            
            # If reference table is also mapped in this proposal, classify as detail_fk
            if b_type == "lookup_fk" and ref_table in mapped_table_names:
                b_type = "detail_fk"
            
            l_name = None
            if b_type == "lookup_fk":
                l_name = binding.source_field  # default lookup name to source field name
                
            fresh_bindings.append({
                "source_field": binding.source_field,
                "destination_field": binding.destination_field,
                "lookup_name": l_name,
                "binding_type": b_type,
                "reference_table_name": ref_table,
                "destination_data_type": binding.destination_data_type,
                "nullable": binding.nullable,
            })
            
        existing_draft = existing_drafts.get(tbl_name)
        if existing_draft:
            # Patch existing draft
            old_bindings_map = {
                (b["source_field"], b["destination_field"]): b
                for b in existing_draft.field_bindings
            }
            
            merged_bindings = []
            for fresh_b in fresh_bindings:
                pair = (fresh_b["source_field"], fresh_b["destination_field"])
                is_signed_off = (existing_draft.mapping_snapshot_id, pair[0], pair[1]) in signed_off_pairs
                if is_signed_off and pair in old_bindings_map:
                    # Keep old binding for core fields, but overlay new keys for forward compatibility
                    merged_bindings.append({**fresh_b, **old_bindings_map[pair]})
                else:
                    # Carry forward the dropped flag even when not signed off — dropped
                    # (user soft-delete) and signed-off are independent state; a re-propose
                    # must not silently un-drop a field the user excluded.
                    if pair in old_bindings_map and "dropped" in old_bindings_map[pair]:
                        fresh_b = {**fresh_b, "dropped": old_bindings_map[pair]["dropped"]}
                    merged_bindings.append(fresh_b)
            
            # Keep signed-off bindings that the AI dropped
            fresh_pairs = {(b["source_field"], b["destination_field"]) for b in fresh_bindings}
            for pair, old_b in old_bindings_map.items():
                if pair not in fresh_pairs:
                    is_signed_off = (existing_draft.mapping_snapshot_id, pair[0], pair[1]) in signed_off_pairs
                    if is_signed_off:
                        merged_bindings.append(old_b)
                        
            existing_draft.field_bindings = merged_bindings
            existing_draft.destination_fields = destination_fields
            existing_draft.destination_columns = destination_columns
            flag_modified(existing_draft, "field_bindings")
            flag_modified(existing_draft, "destination_fields")
            flag_modified(existing_draft, "destination_columns")
            snapshots.append(existing_draft)
        else:
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
                field_bindings=fresh_bindings,
                destination_fields=destination_fields,
                destination_columns=destination_columns,
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
        existing = db.scalars(
            select(MappingSnapshot).where(
                MappingSnapshot.project_id == project_id,
                MappingSnapshot.source_definition_id == source_definition_id,
            ).order_by(MappingSnapshot.destination_object_name)
        ).all()
        per_table: dict[str, list[str]] = {}
        for s in existing:
            per_table.setdefault(s.destination_object_name, []).append(s.status)
        raise AuthApiError(
            "mapping_already_proposed",
            "Mapping has already been proposed for this feed.",
            409,
            {"per_table_status": {k: list(set(v)) for k, v in per_table.items()}},
        )

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
        raise AuthApiError(
            "mapping_already_proposed",
            "All proposed tables already have approved mappings. No changes to apply.",
            409,
        )

    db.commit()
    for snapshot in snapshots:
        db.refresh(snapshot)

    if snapshots:
        backfill_artifact_id(db, call_log.call_id, source_definition_id)

    return snapshot_to_response(snapshots[0], db=db)

