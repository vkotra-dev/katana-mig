from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from ..api.deps import AuthApiError
from ..api.schemas import (
    DestinationMappingGroup,
    LookupSnapshotGenerateRequest,
    LookupSnapshotResponse,
    LookupValueMapCreateRequest,
    LookupValueMapPatchRequest,
    LookupValueMapResponse,
    MappingSnapshotResponse,
)
from ..db.models import LookupSnapshot, LookupValueMap, Feed, FeedSlice, User, new_id, ProjectFiber
from ..mapping.snapshots import select_latest_approved_mapping_snapshot
from ..mapping.exceptions import SnapshotNotFoundError
from .platform import record_management_audit
from .source_analysis import list_source_value_summaries

_SNAPSHOT_VERSION_RE = re.compile(r"^v(?P<number>\d+)$")


def create_lookup_value_map(
    db: Session,
    *,
    actor: User,
    project_id: str,
    body: LookupValueMapCreateRequest,
) -> LookupValueMapResponse:
    lookup_name = body.lookup_name.strip()
    destination_mappings = []
    if body.destination_mappings:
        destination_mappings = [
            {
                "dest_id": g.dest_id,
                "dest_label": g.dest_label,
                "dest_row": g.dest_row,
                "source_values": g.source_values,
                "status": g.status,
            }
            for g in body.destination_mappings
        ]
    destination_table = [_normalize_destination_row(row) for row in body.destination_table]
    source_value_map = {key.strip(): value.strip() for key, value in body.source_value_map.items() if key.strip() and value.strip()}
    draft = LookupValueMap(
        lookup_value_map_id=new_id(),
        project_id=project_id,
        lookup_name=lookup_name,
        destination_table=destination_table,
        source_value_map=source_value_map,
        destination_mappings=destination_mappings,
        status="draft",
    )
    db.add(draft)

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="lookup_value_map_saved",
        payload={
            "project_id": project_id,
            "lookup_name": lookup_name,
            "destination_row_count": len(destination_table),
            "mapped_value_count": len(source_value_map),
        },
    )
    db.commit()
    db.refresh(draft)
    return _lookup_value_map_response(draft)


def update_lookup_value_map(
    db: Session,
    *,
    project_id: str,
    lookup_value_map_id: str,
    body: LookupValueMapPatchRequest,
) -> LookupValueMapResponse:
    lookup_map = db.scalar(
        select(LookupValueMap).where(
            LookupValueMap.lookup_value_map_id == lookup_value_map_id,
            LookupValueMap.project_id == project_id,
        ),
    )
    if lookup_map is None:
        raise AuthApiError("lookup_map_not_found", "Lookup value map not found.", 404)
    if lookup_map.status == "approved":
        raise AuthApiError("lookup_map_approved", "Cannot edit an approved lookup value map. Revert to draft first.", 409)

    # Handle explicit source_value_map overwrite (full replacement)
    if body.source_value_map is not None:
        source_value_map = {key.strip(): value.strip() for key, value in body.source_value_map.items() if key.strip() and value.strip()}
        lookup_map.source_value_map = source_value_map
    # Handle add_source_value action
    if body.add_source_value:
        dest_id = body.add_source_value.get("dest_id", "")
        src_val = body.add_source_value.get("source_value", "")
        if dest_id and src_val:
            _add_source_value_action(lookup_map, dest_id, src_val)

    # Handle remove_source_value action
    if body.remove_source_value:
        dest_id = body.remove_source_value.get("dest_id", "")
        src_val = body.remove_source_value.get("source_value", "")
        if dest_id and src_val:
            mappings = _reconcile_destination_mappings(lookup_map)
            found = False
            for group in mappings:
                if str(group.get("dest_id", "")) == str(dest_id):
                    group["source_values"] = [s for s in group.get("source_values", []) if s != src_val]
                    found = True
                    break
            if not found:
                # Group may not exist yet (e.g. legacy maps without destination_mappings)
                label, dest_row_data = _lookup_dest_label(lookup_map, dest_id)
                mappings.append({
                    "dest_id": dest_id,
                    "dest_label": label,
                    "dest_row": dest_row_data,
                    "source_values": [],
                    "status": "draft",
                })
            lookup_map.destination_mappings = mappings
            flag_modified(lookup_map, "destination_mappings")
            # Also remove from flat source_value_map
            svm = dict(lookup_map.source_value_map or {})
            svm.pop(src_val, None)
            lookup_map.source_value_map = svm

    # Handle full destination_mappings overwrite
    if body.destination_mappings is not None:
        lookup_map.destination_mappings = [
            {
                "dest_id": str(g.dest_id),
                "dest_label": str(g.dest_label),
                "dest_row": g.dest_row if isinstance(g.dest_row, dict) else dict(g.dest_row) if g.dest_row else {},
                "source_values": list(g.source_values) if g.source_values else [],
                "status": str(g.status),
            }
            for g in body.destination_mappings
        ]
        # Rebuild flat source_value_map from destination_mappings
        svm: dict[str, str] = {}
        for group in lookup_map.destination_mappings:
            for src_val in group.get("source_values", []):
                svm[src_val] = str(group.get("dest_id", ""))
        lookup_map.source_value_map = svm

    # Handle move_source_value action
    if body.move_source_value:
        src_val = body.move_source_value.get("source_value", "")
        old_dest_id = body.move_source_value.get("old_dest_id", "")
        new_dest_id = body.move_source_value.get("new_dest_id", "")
        if src_val and old_dest_id and new_dest_id:
            mappings = _reconcile_destination_mappings(lookup_map)
            src_moved = False
            for group in mappings:
                if str(group.get("dest_id", "")) == str(old_dest_id):
                    svs = group.get("source_values", [])
                    if src_val in svs:
                        group["source_values"] = [s for s in svs if s != src_val]
                        src_moved = True
                    break
            if src_moved:
                found_new = False
                for group in mappings:
                    if str(group.get("dest_id", "")) == str(new_dest_id):
                        svs = group.setdefault("source_values", [])
                        if src_val not in svs:
                            svs.append(src_val)
                        found_new = True
                        break
                if not found_new:
                    label, dest_row_data = _lookup_dest_label(lookup_map, new_dest_id)
                    mappings.append({
                        "dest_id": new_dest_id,
                        "dest_label": label,
                        "dest_row": dest_row_data,
                        "source_values": [src_val],
                        "status": "draft",
                    })
            lookup_map.destination_mappings = mappings
            flag_modified(lookup_map, "destination_mappings")
            # Sync flat source_value_map
            svm = dict(lookup_map.source_value_map or {})
            svm.pop(src_val, None)
            svm[src_val] = new_dest_id
            lookup_map.source_value_map = svm

    # Reset related lookup snapshots to draft (sign-off invalidation)
    snapshots = db.scalars(
        select(LookupSnapshot).where(
            LookupSnapshot.project_id == project_id,
            LookupSnapshot.lookup_name == lookup_map.lookup_name,
        ),
    ).all()
    for snapshot in snapshots:
        if snapshot.status == "approved":
            snapshot.status = "draft"
            snapshot.approved_at = None
            snapshot.approved_by_user_id = None

    db.flush()
    db.commit()
    db.refresh(lookup_map)
    return _lookup_value_map_response(lookup_map)


def list_lookup_value_maps(
    db: Session,
    *,
    project_id: str,
    feed_id: str | None = None,
) -> list[LookupValueMapResponse]:
    stmt = select(LookupValueMap).where(LookupValueMap.project_id == project_id)

    if feed_id:
        fiber_keys = db.scalars(
            select(ProjectFiber.fiber_key).where(
                ProjectFiber.project_id == project_id,
                ProjectFiber.feed_id == feed_id,
                ProjectFiber.fiber_type == "lookup",
            )
        ).all()
        stmt = stmt.where(LookupValueMap.lookup_name.in_(fiber_keys))

    rows = db.scalars(
        stmt.order_by(LookupValueMap.created_at.asc(), LookupValueMap.lookup_value_map_id.asc())
    ).all()

    # Find the latest approved FeedSlice with data_profile for this project
    data_profile: dict[str, dict[str, int]] | None = None
    if feed_id:
        source_definition = db.scalar(
            select(Feed).where(Feed.source_definition_id == feed_id)
        )
        if source_definition:
            slice_record = db.scalar(
                select(FeedSlice)
                .where(
                    FeedSlice.source_definition_id == source_definition.source_definition_id,
                    FeedSlice.status == "approved",
                    FeedSlice.data_profile.isnot(None),
                )
                .order_by(FeedSlice.created_at.desc())
                .limit(1)
            )
            if slice_record and slice_record.data_profile:
                data_profile = slice_record.data_profile  # type: ignore[assignment]

    def _compute_unmapped_count(lookup_map: LookupValueMap) -> int:
        if not data_profile:
            return 0
        unmapped_keys = {k for k, v in lookup_map.source_value_map.items() if not v or (isinstance(v, str) and not v.strip())}
        if not unmapped_keys:
            return 0
        unmapped_count = 0
        for col_profile in data_profile.values():
            if isinstance(col_profile, dict):
                for u_key in unmapped_keys:
                    unmapped_count += col_profile.get(u_key, 0)
        return unmapped_count

    return [_lookup_value_map_response(row, _compute_unmapped_count(row)) for row in rows]


def generate_lookup_snapshot(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    body: LookupSnapshotGenerateRequest,
) -> LookupSnapshotResponse:
    source_definition = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    lookup_name = body.lookup_name.strip()
    lookup_map = _latest_lookup_value_map(
        db,
        project_id=project_id,
        lookup_name=lookup_name,
    )
    mapping_snapshot = _latest_mapping_snapshot_for_lookup(
        db,
        project_id=project_id,
        source_definition=source_definition,
        lookup_name=lookup_name,
    )
    source_field = _source_field_for_lookup(mapping_snapshot, lookup_name=lookup_name)

    source_values = list_source_value_summaries(
        db,
        project_id=project_id,
        source_definition_id=source_definition.source_definition_id,
        field_name=source_field,
    )
    if not source_values:
        raise AuthApiError("source_analysis_not_found", "Source analysis has not been run for this lookup field.", 404)

    destination_ids = {
        _extract_destination_id(row)
        for row in lookup_map.destination_table
        if _extract_destination_id(row)
    }
    value_map = {key: value.strip() for key, value in lookup_map.source_value_map.items() if key.strip() and value.strip()}
    source_value_keys = sorted({key for summary in source_values for key in summary.value_counts.keys()})

    unmapped_values = [value for value in source_value_keys if value not in value_map]
    invalid_destination_values = sorted(
        {
            destination_id
            for destination_id in value_map.values()
            if destination_id not in destination_ids
        }
    )
    if unmapped_values or invalid_destination_values:
        parts: list[str] = []
        if unmapped_values:
            parts.append(f"unmapped values: {', '.join(unmapped_values)}")
        if invalid_destination_values:
            parts.append(f"invalid destination ids: {', '.join(invalid_destination_values)}")
        message = "Lookup values must be mapped before a snapshot can be generated."
        if parts:
            message = f"{message} {'; '.join(parts)}"
        raise AuthApiError("lookup_values_unmapped", message, 409)

    snapshot = LookupSnapshot(
        lookup_snapshot_id=new_id(),
        project_id=project_id,
        lookup_name=lookup_name,
        lookup_snapshot_version=_next_snapshot_version(
            db,
            project_id=project_id,
            lookup_name=lookup_name,
        ),
        value_map=value_map,
        status="draft",
        approved_at=None,
        approved_by_user_id=None,
    )
    db.add(snapshot)
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="lookup_snapshot.generated",
        payload={
            "source_definition_id": source_definition_id,
            "lookup_name": lookup_name,
            "source_field": source_field,
            "lookup_snapshot_id": snapshot.lookup_snapshot_id,
            "lookup_snapshot_version": snapshot.lookup_snapshot_version,
            "value_count": len(value_map),
        },
    )
    db.commit()
    db.refresh(snapshot)
    return _lookup_snapshot_response(snapshot)


def approve_lookup_snapshot(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str | None = None,
    lookup_snapshot_id: str,
) -> LookupSnapshotResponse:
    snapshot = db.get(LookupSnapshot, lookup_snapshot_id)
    if snapshot is None or snapshot.project_id != project_id or snapshot.lookup_name is None:
        raise AuthApiError("lookup_snapshot_not_found", "Lookup snapshot not found.", 404)
    if snapshot.status == "approved":
        return _lookup_snapshot_response(snapshot)

    snapshot.status = "approved"
    snapshot.approved_at = datetime.now(UTC)
    snapshot.approved_by_user_id = actor.user_id
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="lookup_snapshot.approved",
        payload={
            "lookup_name": snapshot.lookup_name,
            "lookup_snapshot_id": snapshot.lookup_snapshot_id,
            "lookup_snapshot_version": snapshot.lookup_snapshot_version,
        },
    )
    db.commit()
    db.refresh(snapshot)
    return _lookup_snapshot_response(snapshot)


def _get_source_definition(db: Session, *, project_id: str, source_definition_id: str) -> Feed:
    source_definition = db.get(Feed, source_definition_id)
    if source_definition is None or source_definition.project_id != project_id:
        raise AuthApiError("source_not_found", "Source contract not found.", 404)
    return source_definition


def _latest_lookup_value_map(
    db: Session,
    *,
    project_id: str,
    lookup_name: str,
) -> LookupValueMap:
    lookup_map = db.scalar(
        select(LookupValueMap)
        .where(
            LookupValueMap.project_id == project_id,
            LookupValueMap.lookup_name == lookup_name,
            LookupValueMap.status == "draft",
        )
        .order_by(LookupValueMap.created_at.desc(), LookupValueMap.lookup_value_map_id.desc())
    )
    if lookup_map is None:
        raise AuthApiError("lookup_map_not_found", "Lookup draft has not been created.", 404)
    return lookup_map


def _latest_mapping_snapshot_for_lookup(
    db: Session,
    *,
    project_id: str,
    source_definition: Feed,
    lookup_name: str,
) -> MappingSnapshotResponse:
    destination_object_names = source_definition.destination_object_references
    if not destination_object_names:
        raise AuthApiError("mapping_snapshot_not_found", "Source contract has no destination object reference.", 404)

    snapshot = None
    for tbl in destination_object_names:
        tbl_name = str(tbl).strip()
        if not tbl_name:
            continue
        try:
            candidate = select_latest_approved_mapping_snapshot(
                db,
                project_id=project_id,
                destination_object_name=tbl_name,
                source_definition_id=source_definition.source_definition_id,
            )
            if any(str(binding.get("lookup_name")) == lookup_name for binding in candidate.field_bindings):
                snapshot = candidate
                break
        except SnapshotNotFoundError:
            continue

    if snapshot is None:
        raise AuthApiError(
            "mapping_snapshot_not_found",
            "Approved mapping snapshot does not define this lookup field.",
            404,
        )
    return _mapping_snapshot_response(snapshot)


def _source_field_for_lookup(snapshot: MappingSnapshotResponse, *, lookup_name: str) -> str:
    for binding in snapshot.field_bindings:
        if binding.lookup_name == lookup_name:
            return binding.source_field
    raise AuthApiError("mapping_snapshot_not_found", "Approved mapping snapshot does not define this lookup field.", 404)


def _next_snapshot_version(
    db: Session,
    *,
    project_id: str,
    lookup_name: str,
) -> str:
    versions = db.scalars(
        select(LookupSnapshot.lookup_snapshot_version)
        .where(
            LookupSnapshot.project_id == project_id,
            LookupSnapshot.lookup_name == lookup_name,
        )
        .order_by(LookupSnapshot.created_at.asc(), LookupSnapshot.lookup_snapshot_id.asc())
    ).all()
    highest = 0
    for version in versions:
        match = _SNAPSHOT_VERSION_RE.match(version)
        if match is None:
            continue
        highest = max(highest, int(match.group("number")))
    return f"v{highest + 1}"


def _normalize_destination_row(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row)


def _extract_destination_id(row: dict[str, Any]) -> str:
    for key in ("destination_mapping_id", "id", "value", "code", "key", "destination_id"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key, value in row.items():
        if key.endswith("_id"):
            return str(value)
    for key, value in row.items():
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_destination_label(row: dict[str, Any]) -> str:
    # 1. Exact matches for common label keys
    for key in ("label", "name", "description", "desc", "val", "value", "display"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
            
    # 2. Substring matches (e.g. status_name, display_label)
    for key, value in row.items():
        key_lower = key.lower()
        if any(sub in key_lower for sub in ("name", "label", "desc", "display")):
            if isinstance(value, str) and value.strip():
                return value.strip()
                
    # 3. Fallback: concatenate all other string values (excluding IDs)
    pieces = []
    for key, value in row.items():
        if key in ("destination_mapping_id", "id", "destination_id", "entry_id", "uuid") or key.endswith("_id"):
            continue
        if isinstance(value, str) and value.strip():
            pieces.append(value.strip())
    if pieces:
        return " | ".join(pieces)
    return _extract_destination_id(row)


def _lookup_dest_label(lookup_map: LookupValueMap, dest_id: str) -> tuple[str, dict[str, Any]]:
    """Find the destination row in destination_table matching dest_id and return (label, dest_row)."""
    for row in (lookup_map.destination_table or []):
        row_id = row.get("id") or row.get("destination_id")
        if str(row_id) == str(dest_id):
            return (_extract_destination_label(row), row)
    return ("", {})


def _reconcile_destination_mappings(lookup_map: LookupValueMap) -> list[dict[str, Any]]:
    """Return the working copy of destination_mappings groups to mutate.

    If destination_mappings was never explicitly seeded (empty) but
    source_value_map already has entries, rebuild groups from source_value_map
    first — otherwise those source values would be silently dropped the
    moment a PATCH action rebuilds destination_mappings from an empty start.
    """
    mappings = list(lookup_map.destination_mappings or [])
    if not mappings and lookup_map.source_value_map:
        dest_groups: dict[str, dict[str, Any]] = {}
        for src_v, dest_v in lookup_map.source_value_map.items():
            did = str(dest_v)
            if did not in dest_groups:
                label, dest_row_data = _lookup_dest_label(lookup_map, did)
                dest_groups[did] = {
                    "dest_id": did,
                    "dest_label": label,
                    "dest_row": dest_row_data,
                    "source_values": [],
                    "status": "draft",
                }
            dest_groups[did]["source_values"].append(src_v)
        mappings = list(dest_groups.values())
    return mappings


def _add_source_value_action(
    lookup_map: LookupValueMap,
    dest_id: str,
    src_val: str,
) -> None:
    """Handle add_source_value with case-insensitive duplicate check and dest validation."""
    # 1. Case-insensitive lookup: find any existing key matching src_val
    src_lower = src_val.strip().lower()
    existing_key: str | None = None
    existing_dest: str | None = None
    for k, v in (lookup_map.source_value_map or {}).items():
        if k.strip().lower() == src_lower:
            existing_key = k
            existing_dest = str(v)
            break

    if existing_key:
        # 2. If same dest_id: harmless no-op, allow through
        if str(existing_dest) == str(dest_id):
            return
        # 2b. Different dest: reject with 409
        # Find the destination label for the existing mapping
        existing_label = "unknown"
        for row in (lookup_map.destination_table or []):
            rid = row.get("id") or row.get("destination_id")
            if str(rid) == str(existing_dest):
                existing_label = _extract_destination_label(row)
                break
        raise AuthApiError(
            "duplicate_source_value",
            f"'{src_val}' is already mapped to a different destination ({existing_label}).",
            409,
        )

    # 3. No case-insensitive match found — validate dest_id against known destinations
    valid_dest_ids = set()
    # Check existing destination_mappings groups
    for g in (lookup_map.destination_mappings or []):
        did = g.get("dest_id")
        if did:
            valid_dest_ids.add(str(did))
    # Check destination_table rows
    for row in (lookup_map.destination_table or []):
        rid = row.get("id") or row.get("destination_id")
        if rid:
            valid_dest_ids.add(str(rid))

    if dest_id not in valid_dest_ids:
        # 3b. Invalid dest_id — route to unmapped_source_values
        unmapped = list(lookup_map.unmapped_source_values or [])
        if src_val not in unmapped:
            unmapped.append(src_val)
        lookup_map.unmapped_source_values = unmapped
        flag_modified(lookup_map, "unmapped_source_values")
        return

    # 4. Valid dest_id — proceed with existing stack-or-create logic
    mappings = _reconcile_destination_mappings(lookup_map)
    found = False
    for group in mappings:
        if str(group.get("dest_id", "")) == str(dest_id):
            svs = group.setdefault("source_values", [])
            if src_val not in svs:
                svs.append(src_val)
            found = True
            break
    if not found:
        label, dest_row_data = _lookup_dest_label(lookup_map, dest_id)
        mappings.append({
            "dest_id": dest_id,
            "dest_label": label,
            "dest_row": dest_row_data,
            "source_values": [src_val],
            "status": "draft",
        })
    lookup_map.destination_mappings = mappings
    flag_modified(lookup_map, "destination_mappings")
    # Sync flat source_value_map for backward compat
    svm = dict(lookup_map.source_value_map or {})
    svm[src_val] = dest_id
    lookup_map.source_value_map = svm


def _lookup_value_map_response(row: LookupValueMap, unmapped_row_count: int = 0) -> LookupValueMapResponse:
    dest_mappings = row.destination_mappings or []
    return LookupValueMapResponse(
        lookup_value_map_id=row.lookup_value_map_id,
        project_id=row.project_id,
        lookup_name=row.lookup_name,
        destination_table=row.destination_table,
        source_value_map=row.source_value_map,
        destination_mappings=dest_mappings,
        unmapped_source_values=row.unmapped_source_values or [],
        status=row.status,
        unmapped_row_count=unmapped_row_count,
        created_at=row.created_at,
    )


def _mapping_snapshot_response(snapshot) -> MappingSnapshotResponse:
    return MappingSnapshotResponse(
        mapping_snapshot_id=snapshot.mapping_snapshot_id,
        project_id=snapshot.project_id,
        destination_object_name=snapshot.destination_object_name,
        mapping_snapshot_version=snapshot.mapping_snapshot_version,
        field_bindings=[
            {
                "source_field": str(binding.get("source_field", "")),
                "destination_field": str(binding.get("destination_field", "")),
                "lookup_name": binding.get("lookup_name"),
            }
            for binding in snapshot.field_bindings
        ],
        status=snapshot.status,
        approved_at=snapshot.approved_at,
        approved_by_user_id=snapshot.approved_by_user_id,
        created_at=snapshot.created_at,
    )


def _lookup_snapshot_response(row: LookupSnapshot) -> LookupSnapshotResponse:
    return LookupSnapshotResponse(
        lookup_snapshot_id=row.lookup_snapshot_id,
        project_id=row.project_id,
        lookup_name=row.lookup_name,
        lookup_snapshot_version=row.lookup_snapshot_version,
        value_map=row.value_map,
        status=row.status,
        approved_at=row.approved_at,
        approved_by_user_id=row.approved_by_user_id,
        created_at=row.created_at,
    )
