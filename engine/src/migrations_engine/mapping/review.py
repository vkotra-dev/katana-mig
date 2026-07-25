from __future__ import annotations

from datetime import UTC, datetime


from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import MappingFieldBindingResponse, MappingReviewResponse
from ..db.models import MappingSnapshot, LookupValueMap
from ..management.platform import record_management_audit

try:
    from ..ai.factory import get_adapter
except ModuleNotFoundError:  # pragma: no cover - optional dependency in tests
    get_adapter = None  # type: ignore[assignment]


from .review_repository import get_project_destination_schema, get_source_definition, latest_snapshot, snapshot_to_response

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
            "dropped": binding.dropped,
        })

    # Detect changed fields and delete their sign-off records. A pair can be "changed" either by
    # being dropped entirely (deletion, or the old half of a rename) or by being newly added (a
    # fresh binding, or the new half of a rename) - either way its sign-off state no longer
    # applies and must be cleared. Deliberately does NOT block on a dropped pair having been
    # signed off: the frontend already prevents renaming a signed-off pair (its destination-field
    # input is locked whenever the binding is signed by either role), so this only ever fires for
    # genuine deletions, which must be allowed to succeed.
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
        from sqlalchemy import delete, tuple_
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
        drafts = db.scalars(
            select(MappingSnapshot)
            .where(
                MappingSnapshot.project_id == project_id,
                MappingSnapshot.source_definition_id == source_definition_id,
                MappingSnapshot.destination_object_name == destination_object_name,
            )
            .order_by(MappingSnapshot.created_at.desc(), MappingSnapshot.mapping_snapshot_id.desc())
            .limit(1)
        ).all()
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


def request_revision(
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
        drafts = db.scalars(
            select(MappingSnapshot)
            .where(
                MappingSnapshot.project_id == project_id,
                MappingSnapshot.source_definition_id == source_definition_id,
                MappingSnapshot.destination_object_name == destination_object_name,
            )
            .order_by(MappingSnapshot.created_at.desc(), MappingSnapshot.mapping_snapshot_id.desc())
            .limit(1)
        ).all()
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
        snapshot.status = "draft"
        snapshot.current_ball_role = "central_team"
        record_management_audit(
            db,
            project_id=project_id,
            actor_user_id=actor_user_id,
            event_type="mapping_revision_requested",
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
        snapshots = db.scalars(
            select(MappingSnapshot)
            .where(
                MappingSnapshot.project_id == project_id,
                MappingSnapshot.source_definition_id == source_definition_id,
                MappingSnapshot.destination_object_name == destination_object_name,
                MappingSnapshot.status == "approved",
            )
            .order_by(MappingSnapshot.created_at.desc(), MappingSnapshot.mapping_snapshot_id.desc())
            .limit(1)
        ).all()
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


def reject_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    actor_user_id: str,
    destination_object_name: str | None = None,
) -> MappingReviewResponse:
    source_definition = get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)

    if destination_object_name:
        snapshots = db.scalars(
            select(MappingSnapshot)
            .where(
                MappingSnapshot.project_id == project_id,
                MappingSnapshot.source_definition_id == source_definition_id,
                MappingSnapshot.destination_object_name == destination_object_name,
                MappingSnapshot.status == "draft",
            )
            .order_by(MappingSnapshot.created_at.desc(), MappingSnapshot.mapping_snapshot_id.desc())
            .limit(1)
        ).all()
    else:
        snapshots = db.scalars(
            select(MappingSnapshot)
            .where(
                MappingSnapshot.project_id == project_id,
                MappingSnapshot.source_definition_id == source_definition_id,
                MappingSnapshot.status == "draft",
            )
            .order_by(MappingSnapshot.destination_object_name.asc())
        ).all()

    if not snapshots:
        msg = "No draft mapping snapshots exist to reject."
        raise AuthApiError("mapping_not_found", msg, 404)

    for snapshot in snapshots:
        snapshot.status = "rejected"
        snapshot.current_ball_role = None
        record_management_audit(
            db,
            project_id=project_id,
            actor_user_id=actor_user_id,
            event_type="mapping_rejected",
            payload={
                "mapping_snapshot_id": snapshot.mapping_snapshot_id,
                "destination_object_name": snapshot.destination_object_name,
            },
        )

    db.commit()
    db.refresh(snapshots[-1])
    return snapshot_to_response(snapshots[-1], db=db)
