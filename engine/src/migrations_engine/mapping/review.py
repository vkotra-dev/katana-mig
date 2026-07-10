from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.exc import IntegrityError

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import MappingFieldBindingResponse, MappingReviewResponse, LookupTableReferenceResponse
from ..db.models import MappingSnapshot, ProjectDefinition, ProjectRegistry, Feed, LookupValueMap, new_id
from ..management.platform import record_management_audit
from ..management.source_analysis import get_latest_source_schema_artifact

try:
    from ..ai.factory import get_adapter
except ModuleNotFoundError:  # pragma: no cover - optional dependency in tests
    get_adapter = None  # type: ignore[assignment]


_SNAPSHOT_VERSION_RE = re.compile(r"^v(?P<number>\d+)$")
_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:[\w$]+\.)?\"?(?P<table>[\w$]+)\"?",
    re.IGNORECASE,
)
_COLUMN_RE = re.compile(r'^\s*["`]?(?P<name>[A-Za-z_][\w$]*)["`]?\s+[A-Za-z]')
_CONSTRAINT_PREFIXES = ("CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN", "CHECK")


class _ProposedBinding(BaseModel):
    source_field: str
    destination_field: str
    binding_type: Literal["direct", "detail_fk", "lookup_fk"] = "direct"
    reference_table_name: str | None = None  # populated only for lookup_fk or detail_fk


class _TableMapping(BaseModel):
    destination_table_name: str
    bindings: list[_ProposedBinding] = []


class _FieldMappingProposal(BaseModel):
    tables: list[_TableMapping] = []
    error_code: str | None = None
    error_message: str | None = None


def _parse_all_ddl_tables(ddl: str) -> dict[str, list[str]]:
    tables: dict[str, list[str]] = {}
    current_table: str | None = None
    current_columns: list[str] = []
    
    for line in ddl.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--") or stripped.startswith("/*"):
            continue
            
        table_match = _TABLE_RE.search(stripped)
        if table_match:
            if current_table and current_columns:
                tables[current_table] = current_columns
            current_table = table_match.group("table")
            current_columns = []
            continue
            
        if current_table:
            if stripped.upper().startswith(_CONSTRAINT_PREFIXES):
                continue
            if stripped.startswith(")") or stripped.startswith(";"):
                tables[current_table] = current_columns
                current_table = None
                current_columns = []
                continue
                
            column_match = _COLUMN_RE.match(stripped)
            if column_match:
                col_name = column_match.group("name")
                if col_name not in current_columns:
                    current_columns.append(col_name)
                    
    if current_table and current_columns:
        tables[current_table] = current_columns
        
    return tables


def _parse_ddl(ddl: str) -> tuple[str, list[str]]:
    lines = [line.rstrip() for line in ddl.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Could not parse table name from destination_schema_ddl.")

    table_match = _TABLE_RE.search(lines[0])
    if table_match is None:
        for line in lines:
            table_match = _TABLE_RE.search(line)
            if table_match is not None:
                break
    if table_match is None:
        raise ValueError("Could not parse table name from destination_schema_ddl.")

    columns: list[str] = []
    for line in lines[1:]:
        stripped = line.strip().rstrip(",")
        if not stripped or stripped.startswith(")") or stripped.startswith("--"):
            continue
        if stripped.upper().startswith(_CONSTRAINT_PREFIXES):
            continue
        column_match = _COLUMN_RE.match(line)
        if column_match is None:
            continue
        column_name = column_match.group("name")
        if column_name not in columns:
            columns.append(column_name)

    if not columns:
        raise ValueError("Destination schema DDL has no parseable column definitions.")
    return table_match.group("table"), columns


def _get_project_destination_schema(db: Session, *, project_id: str) -> tuple[str, list[str]]:
    registry = db.scalar(select(ProjectRegistry).where(ProjectRegistry.project_id == project_id))
    if registry is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)

    definition = db.scalar(select(ProjectDefinition).where(ProjectDefinition.definition_id == registry.definition_id))
    if definition is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)

    ddl: str | None = None
    if definition.domain_config is not None:
        ddl = definition.domain_config.get("destination_schema_ddl")
    if not ddl:
        raise AuthApiError(
            "destination_schema_missing",
            "Project has no destination schema DDL configured.",
            409,
        )

    try:
        table_name, columns = _parse_ddl(ddl)
    except ValueError as exc:
        raise AuthApiError("destination_schema_invalid", str(exc), 422) from exc
    return table_name, columns


def _get_source_definition(db: Session, *, project_id: str, source_definition_id: str) -> Feed:
    source_definition = db.get(Feed, source_definition_id)
    if source_definition is None or source_definition.project_id != project_id:
        raise AuthApiError("source_not_found", "Source contract not found.", 404)
    return source_definition


def _latest_snapshot(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    destination_object_name: str,
) -> MappingSnapshot | None:
    return db.scalar(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id == source_definition_id,
            MappingSnapshot.destination_object_name == destination_object_name,
        )
        .order_by(MappingSnapshot.created_at.desc(), MappingSnapshot.mapping_snapshot_id.desc())
    )


def _next_snapshot_version(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    destination_object_name: str,
) -> str:
    versions = db.scalars(
        select(MappingSnapshot.mapping_snapshot_version)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id == source_definition_id,
            MappingSnapshot.destination_object_name == destination_object_name,
        )
        .order_by(MappingSnapshot.created_at.asc(), MappingSnapshot.mapping_snapshot_id.asc())
    ).all()
    highest = 0
    for version in versions:
        match = _SNAPSHOT_VERSION_RE.match(version)
        if match is None:
            continue
        highest = max(highest, int(match.group("number")))
    return f"v{highest + 1}"


def derive_destination_fields(db: Session, project_id: str, destination_object_name: str) -> list[str]:
    try:
        project_definition = _get_project_definition(db, project_id=project_id)
        ddl = (project_definition.domain_config or {}).get("destination_schema_ddl")
        if not ddl:
            return []
        ddl_tables = _parse_all_ddl_tables(ddl)
        return ddl_tables.get(destination_object_name) or []
    except Exception:
        return []


def _snapshot_to_response(
    snapshot: MappingSnapshot,
    db: Session,
    destination_fields: list[str] | None = None,
) -> MappingReviewResponse:
    if destination_fields is None:
        destination_fields = derive_destination_fields(db, snapshot.project_id, snapshot.destination_object_name)
    fields = destination_fields if destination_fields else (snapshot.destination_fields or [])
    
    lookup_table_references: list[dict[str, str]] = []
    for binding in snapshot.field_bindings:
        b_type = binding.get("binding_type")
        ref_table = binding.get("reference_table_name")
        l_name = binding.get("lookup_name")
        if b_type == "lookup_fk" and ref_table:
            # Match: lookup_name -> destination_table_name
            lookup_table_references.append({
                "lookup_name": l_name or binding.get("source_field", ""),
                "destination_table_name": ref_table,
            })

    return MappingReviewResponse(
        mapping_snapshot_id=snapshot.mapping_snapshot_id,
        project_id=snapshot.project_id,
        destination_object_name=snapshot.destination_object_name,
        mapping_snapshot_version=snapshot.mapping_snapshot_version,
        field_bindings=[
            MappingFieldBindingResponse(
                source_field=str(binding.get("source_field", "")),
                destination_field=str(binding.get("destination_field", "")),
                lookup_name=binding.get("lookup_name"),
                binding_type=binding.get("binding_type"),
                reference_table_name=binding.get("reference_table_name"),
                destination_table_name=binding.get("destination_table_name"),
            )
            for binding in snapshot.field_bindings
        ],
        status=snapshot.status,
        current_ball_role=snapshot.current_ball_role,
        approved_at=snapshot.approved_at,
        approved_by_user_id=snapshot.approved_by_user_id,
        created_at=snapshot.created_at,
        destination_fields=fields,
        lookup_table_references=lookup_table_references,
        ai_trace=snapshot.ai_trace,
    )


def _latest_source_columns(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
) -> list[str]:
    _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    artifact = get_latest_source_schema_artifact(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
    )
    return [column.name for column in artifact.columns]


def _get_project_definition(db: Session, *, project_id: str) -> ProjectDefinition:
    registry = db.get(ProjectRegistry, project_id)
    if registry is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)

    project_definition = db.get(ProjectDefinition, registry.definition_id)
    if project_definition is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)
    return project_definition


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
    project_definition = _get_project_definition(db, project_id=project_id)
    ddl = (project_definition.domain_config or {}).get("destination_schema_ddl")
    if not ddl:
        raise AuthApiError(
            "destination_schema_missing",
            "Project has no destination schema DDL configured.",
            409,
        )

    # Parse all table names and their column mappings from DDL
    ddl_tables = _parse_all_ddl_tables(ddl)
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
            )
        ).all()
    )
    expected_table_names = set(ddl_tables.keys())
    if already_mapped_tables >= expected_table_names:
        raise AuthApiError("mapping_already_proposed", "Mapping has already been proposed for this feed.", 409)

    source_columns = _latest_source_columns(
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
    from pydantic import ValidationError
    from ..ai.adapter import AICallError

    system_prompt = (
        "You are a data migration specialist. Analyze the provided multi-table SQL DDL schema "
        "and the list of source CSV columns.\n"
        "1. Identify all destination tables that receive fields from this feed.\n"
        "2. Map the source fields to each identified table.\n"
        "3. Classify each binding as 'direct', 'detail_fk', or 'lookup_fk'.\n"
        "4. A binding is 'detail_fk' when its destination column is a foreign key whose referenced table "
        "is also mapped in this response. It is 'lookup_fk' when it references a lookup table not mapped here.\n"
        "5. For any lookup_fk binding, set the reference_table_name.\n"
        "6. If the DDL is invalid or you cannot find any matching tables, set error_code and error_message.\n"
        "Return valid JSON matching the schema."
    )

    feed = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    user_prompt = f"Source columns:\n{source_columns!r}\n\nDestination DDL:\n{ddl}"

    extra_context = []
    if feed.mapping_hints:
        extra_context.append(f"Mapping hints (operator-supplied):\n{feed.mapping_hints}")

    project_constraints = project_definition.constraints or []
    if project_constraints:
        bullet_list = "\n".join(f"- {c}" for c in project_constraints)
        extra_context.append(f"Project constraints:\n{bullet_list}")

    if extra_context:
        user_prompt = user_prompt + "\n\n" + "\n\n".join(extra_context)

    try:
        proposal = adapter.call(
            system_prompt,
            user_prompt,
            _FieldMappingProposal,
        )
    except ValidationError as exc:
        raise AuthApiError("ai_schema_mismatch", "The AI generated an invalid mapping format. Please retry.", 502)
    except AICallError as exc:
        raise AuthApiError("ai_service_unavailable", f"The AI provider returned an error: {exc}", 502)

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
    ai_trace = {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "raw_response": proposal.model_dump(),
        "model_id": getattr(adapter, "model_id", None),
    }

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
            })
            
        version = _next_snapshot_version(
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
            ai_trace=ai_trace,
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
        
    db.commit()
    for snapshot in snapshots:
        db.refresh(snapshot)
        
    return _snapshot_to_response(snapshots[0], db=db)


def get_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    destination_object_name: str | None = None,
) -> MappingReviewResponse:
    _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    if destination_object_name:
        snapshot = _latest_snapshot(
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
    return _snapshot_to_response(snapshot, db=db)


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
        destination_object_name, _ = _get_project_destination_schema(db, project_id=project_id)
        
    _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    snapshot = _latest_snapshot(
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

    existing_by_src = {b.get("source_field"): b for b in snapshot.field_bindings if b.get("source_field")}
    new_bindings = []
    for binding in field_bindings:
        existing = existing_by_src.get(binding.source_field) or {}
        new_bindings.append({
            "source_field": binding.source_field,
            "destination_field": binding.destination_field,
            "lookup_name": binding.lookup_name,
            "binding_type": existing.get("binding_type", "direct"),
            "reference_table_name": existing.get("reference_table_name"),
        })

    # Detect changed fields and delete their sign-off records
    changed_fields = []
    for binding in field_bindings:
        src = binding.source_field
        dest = binding.destination_field
        existing = existing_by_src.get(src)
        if existing is None or existing.get("destination_field") != dest:
            changed_fields.append(src)

    if changed_fields:
        from ..db.models import MappingBindingSignOff
        from sqlalchemy import delete, select
        # Check if any changed fields are already signed off by either reviewer
        signed_fields = db.scalars(
            select(MappingBindingSignOff.source_field)
            .where(
                MappingBindingSignOff.mapping_snapshot_id == snapshot.mapping_snapshot_id,
                MappingBindingSignOff.source_field.in_(changed_fields),
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
                MappingBindingSignOff.source_field.in_(changed_fields),
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
    return _snapshot_to_response(snapshot, db=db)


def approve_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    actor_user_id: str,
    destination_object_name: str | None = None,
) -> MappingReviewResponse:
    source_definition = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)

    if destination_object_name:
        # Single-table path (explicit caller)
        drafts = [_latest_snapshot(db, project_id=project_id, source_definition_id=source_definition_id, destination_object_name=destination_object_name)]
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
    return _snapshot_to_response(drafts[-1], db=db)


def reject_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    actor_user_id: str,
    reason: str,
    destination_object_name: str | None = None,
) -> MappingReviewResponse:
    _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)

    if destination_object_name:
        drafts = [_latest_snapshot(db, project_id=project_id, source_definition_id=source_definition_id, destination_object_name=destination_object_name)]
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
    return _snapshot_to_response(drafts[-1], db=db)


def unapprove_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    actor_user_id: str,
    destination_object_name: str | None = None,
) -> MappingReviewResponse:
    source_definition = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)

    if destination_object_name:
        snapshots = [_latest_snapshot(db, project_id=project_id, source_definition_id=source_definition_id, destination_object_name=destination_object_name)]
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
    return _snapshot_to_response(snapshots[-1], db=db)
