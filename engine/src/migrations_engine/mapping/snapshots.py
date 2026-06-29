from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import LookupSnapshot, MappingSnapshot, new_id
from .constants import APPROVED_SNAPSHOT_STATUS
from .exceptions import SnapshotImmutableError, SnapshotNotFoundError


@dataclass(frozen=True)
class FieldBinding:
    source_field: str
    destination_field: str
    lookup_name: str


def create_approved_mapping_snapshot(
    db: Session,
    *,
    project_id: str,
    destination_object_name: str,
    mapping_snapshot_version: str,
    field_bindings: list[FieldBinding],
    approved_by_user_id: str | None = None,
) -> MappingSnapshot:
    serialized_bindings = [
        {
            "source_field": binding.source_field,
            "destination_field": binding.destination_field,
            "lookup_name": binding.lookup_name,
        }
        for binding in field_bindings
    ]
    snapshot = MappingSnapshot(
        mapping_snapshot_id=new_id(),
        project_id=project_id,
        destination_object_name=destination_object_name,
        mapping_snapshot_version=mapping_snapshot_version,
        field_bindings=serialized_bindings,
        status=APPROVED_SNAPSHOT_STATUS,
        approved_at=datetime.now(UTC),
        approved_by_user_id=approved_by_user_id,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def create_approved_lookup_snapshot(
    db: Session,
    *,
    project_id: str,
    lookup_name: str,
    lookup_snapshot_version: str,
    value_map: dict[str, str],
    approved_by_user_id: str | None = None,
) -> LookupSnapshot:
    snapshot = LookupSnapshot(
        lookup_snapshot_id=new_id(),
        project_id=project_id,
        lookup_name=lookup_name,
        lookup_snapshot_version=lookup_snapshot_version,
        value_map=value_map,
        status=APPROVED_SNAPSHOT_STATUS,
        approved_at=datetime.now(UTC),
        approved_by_user_id=approved_by_user_id,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def select_latest_approved_mapping_snapshot(
    db: Session,
    *,
    project_id: str,
    destination_object_name: str,
) -> MappingSnapshot:
    snapshots = db.scalars(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.destination_object_name == destination_object_name,
            MappingSnapshot.status == APPROVED_SNAPSHOT_STATUS,
        )
        .order_by(MappingSnapshot.created_at.desc())
    ).all()
    if not snapshots:
        raise SnapshotNotFoundError(
            f"No approved mapping snapshot for {destination_object_name!r} in project {project_id}."
        )
    return snapshots[0]


def select_latest_approved_lookup_snapshot(
    db: Session,
    *,
    project_id: str,
    lookup_name: str,
) -> LookupSnapshot:
    snapshots = db.scalars(
        select(LookupSnapshot)
        .where(
            LookupSnapshot.project_id == project_id,
            LookupSnapshot.lookup_name == lookup_name,
            LookupSnapshot.status == APPROVED_SNAPSHOT_STATUS,
        )
        .order_by(LookupSnapshot.created_at.desc())
    ).all()
    if not snapshots:
        raise SnapshotNotFoundError(
            f"No approved lookup snapshot for {lookup_name!r} in project {project_id}."
        )
    return snapshots[0]


def parse_primary_field_binding(snapshot: MappingSnapshot) -> FieldBinding:
    if not snapshot.field_bindings:
        raise SnapshotNotFoundError("Mapping snapshot has no field bindings.")
    binding = snapshot.field_bindings[0]
    return FieldBinding(
        source_field=str(binding["source_field"]),
        destination_field=str(binding["destination_field"]),
        lookup_name=str(binding["lookup_name"]),
    )


def guard_snapshot_immutable(snapshot: MappingSnapshot | LookupSnapshot, *, updates: dict[str, Any]) -> None:
    if snapshot.status == APPROVED_SNAPSHOT_STATUS and updates:
        raise SnapshotImmutableError("Approved snapshots are immutable.")
