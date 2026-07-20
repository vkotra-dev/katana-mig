from __future__ import annotations

from datetime import datetime, UTC
from typing import Any
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..db.models import (
    MappingSnapshot,
    MappingBindingSignOff,
    LookupSignOff,
    LookupValueMap,
    User,
    ProjectMembership,
)
from ..roles import ADMIN_ROLE, PM_ROLE, CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE
from ..management.notifications import create_notification


def sign_binding(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    destination_object_name: str,
    source_field: str,
) -> Any:
    if actor.role not in {CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE}:
        raise AuthApiError("forbidden", "Only central team or project stakeholders can sign off.", 403)

    # Resolve latest draft snapshot
    snapshot = db.scalar(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id == source_definition_id,
            MappingSnapshot.destination_object_name == destination_object_name,
            MappingSnapshot.status == "draft",
        )
        .order_by(MappingSnapshot.created_at.desc())
    )
    if snapshot is None:
        raise AuthApiError("snapshot_not_found", "No draft mapping snapshot found to sign off.", 404)

    # Check if field actually exists in bindings
    binding_exists = any(b.get("source_field") == source_field for b in snapshot.field_bindings)
    if not binding_exists:
        raise AuthApiError("invalid_field", f"Field '{source_field}' is not part of this mapping snapshot.", 400)

    # Upsert MappingBindingSignOff
    sign_off = db.scalar(
        select(MappingBindingSignOff)
        .where(
            MappingBindingSignOff.mapping_snapshot_id == snapshot.mapping_snapshot_id,
            MappingBindingSignOff.destination_object_name == destination_object_name,
            MappingBindingSignOff.source_field == source_field,
            MappingBindingSignOff.user_id == actor.user_id,
        )
    )
    if sign_off is None:
        sign_off = MappingBindingSignOff(
            mapping_snapshot_id=snapshot.mapping_snapshot_id,
            destination_object_name=destination_object_name,
            source_field=source_field,
            user_id=actor.user_id,
            role=actor.role,
        )
        db.add(sign_off)
    else:
        sign_off.signed_at = datetime.now(UTC)

    db.commit()
    return get_sign_off_status(db, project_id=project_id, source_definition_id=source_definition_id)


def unsign_binding(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    destination_object_name: str,
    source_field: str,
) -> Any:
    # Delete caller's sign-off row only
    snapshot = db.scalar(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id == source_definition_id,
            MappingSnapshot.destination_object_name == destination_object_name,
            MappingSnapshot.status == "draft",
        )
        .order_by(MappingSnapshot.created_at.desc())
    )
    if snapshot is not None:
        db.execute(
            delete(MappingBindingSignOff).where(
                MappingBindingSignOff.mapping_snapshot_id == snapshot.mapping_snapshot_id,
                MappingBindingSignOff.destination_object_name == destination_object_name,
                MappingBindingSignOff.source_field == source_field,
                MappingBindingSignOff.user_id == actor.user_id,
            )
        )
        db.commit()

    return get_sign_off_status(db, project_id=project_id, source_definition_id=source_definition_id)


def sign_lookup(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    lookup_value_map_id: str,
) -> Any:
    if actor.role not in {CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE}:
        raise AuthApiError("forbidden", "Only central team or project stakeholders can sign off.", 403)

    # Upsert LookupSignOff
    sign_off = db.scalar(
        select(LookupSignOff)
        .where(
            LookupSignOff.lookup_value_map_id == lookup_value_map_id,
            LookupSignOff.user_id == actor.user_id,
        )
    )
    if sign_off is None:
        sign_off = LookupSignOff(
            lookup_value_map_id=lookup_value_map_id,
            user_id=actor.user_id,
            role=actor.role,
        )
        db.add(sign_off)
    else:
        sign_off.signed_at = datetime.now(UTC)

    db.commit()
    return get_sign_off_status(db, project_id=project_id, source_definition_id=source_definition_id)


def unsign_lookup(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    lookup_value_map_id: str,
) -> Any:
    db.execute(
        delete(LookupSignOff).where(
            LookupSignOff.lookup_value_map_id == lookup_value_map_id,
            LookupSignOff.user_id == actor.user_id,
        )
    )
    db.commit()
    return get_sign_off_status(db, project_id=project_id, source_definition_id=source_definition_id)


def get_sign_off_status(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
) -> dict[str, Any]:
    # 1. Resolve draft snapshots for the feed
    snapshots = db.scalars(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id == source_definition_id,
            MappingSnapshot.status == "draft",
        )
        .order_by(MappingSnapshot.destination_object_name.asc(), MappingSnapshot.created_at.desc())
    ).all()

    # Dedup to latest snapshot per destination object name
    seen_tables = set()
    latest_snapshots: list[MappingSnapshot] = []
    for s in snapshots:
        if s.destination_object_name not in seen_tables:
            seen_tables.add(s.destination_object_name)
            latest_snapshots.append(s)

    # 2. Get current ball role (from the first draft snapshot, default to central_team if none)
    current_ball_role = "central_team"
    if latest_snapshots:
        current_ball_role = latest_snapshots[0].current_ball_role or "central_team"

    # 3. Resolve active lookups in those snapshots
    lookup_names = set()
    for snapshot in latest_snapshots:
        for binding in snapshot.field_bindings:
            if binding.get("binding_type") == "lookup_fk" and binding.get("lookup_name"):
                lookup_names.add(binding.get("lookup_name"))

    # Resolve latest LookupValueMap per lookup name
    all_maps = db.scalars(
        select(LookupValueMap)
        .where(LookupValueMap.project_id == project_id)
        .order_by(LookupValueMap.created_at.desc(), LookupValueMap.lookup_value_map_id.desc())
    ).all()

    latest_lookup_maps: dict[str, LookupValueMap] = {}
    for m in all_maps:
        if m.lookup_name in lookup_names and m.lookup_name not in latest_lookup_maps:
            latest_lookup_maps[m.lookup_name] = m

    # 4. Fetch sign-offs
    snapshot_ids = [s.mapping_snapshot_id for s in latest_snapshots]
    binding_sign_offs: list[MappingBindingSignOff] = []
    if snapshot_ids:
        binding_sign_offs = list(
            db.scalars(
                select(MappingBindingSignOff).where(
                    MappingBindingSignOff.mapping_snapshot_id.in_(snapshot_ids)
                )
            ).all()
        )

    lookup_map_ids = [m.lookup_value_map_id for m in latest_lookup_maps.values()]
    lookup_sign_offs: list[LookupSignOff] = []
    if lookup_map_ids:
        lookup_sign_offs = list(
            db.scalars(
                select(LookupSignOff).where(LookupSignOff.lookup_value_map_id.in_(lookup_map_ids))
            ).all()
        )

    # Build sign-off maps
    # snapshot_id -> destination_object_name -> source_field -> role -> entry
    b_map: dict[str, dict[str, dict[str, Any]]] = {}
    for snapshot in latest_snapshots:
        obj_name = snapshot.destination_object_name
        if obj_name not in b_map:
            b_map[obj_name] = {}
        for binding in snapshot.field_bindings:
            sf = binding.get("source_field")
            if not sf:
                continue
            b_map[obj_name][sf] = {
                "central_team": {"signed": False, "signed_at": None, "user_id": None},
                "project_stakeholder": {"signed": False, "signed_at": None, "user_id": None},
            }

    for bso in binding_sign_offs:
        obj_name = bso.destination_object_name
        sf = bso.source_field
        if obj_name in b_map and sf in b_map[obj_name] and bso.role in b_map[obj_name][sf]:
            b_map[obj_name][sf][bso.role] = {
                "signed": True,
                "signed_at": bso.signed_at,
                "user_id": bso.user_id,
            }

    # lookup_map_id -> role -> entry
    l_map: dict[str, dict[str, Any]] = {}
    for l_map_id in lookup_map_ids:
        l_map[l_map_id] = {
            "central_team": {"signed": False, "signed_at": None, "user_id": None},
            "project_stakeholder": {"signed": False, "signed_at": None, "user_id": None},
        }

    for lso in lookup_sign_offs:
        l_map_id = lso.lookup_value_map_id
        if l_map_id in l_map and lso.role in l_map[l_map_id]:
            l_map[l_map_id][lso.role] = {
                "signed": True,
                "signed_at": lso.signed_at,
                "user_id": lso.user_id,
            }

    # Check completeness
    complete = True
    # If no draft mapping snapshots exist, it's not complete
    if not latest_snapshots:
        complete = False

    for obj_name, fields in b_map.items():
        for sf, status in fields.items():
            if not status["central_team"]["signed"] or not status["project_stakeholder"]["signed"]:
                complete = False

    for l_map_id, status in l_map.items():
        if not status["central_team"]["signed"] or not status["project_stakeholder"]["signed"]:
            complete = False

    return {
        "complete": complete,
        "current_ball_role": current_ball_role,
        "bindings": b_map,
        "lookups": l_map,
    }


def push_for_review(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
) -> dict[str, Any]:
    # 1. Resolve draft snapshots for the feed
    snapshots = db.scalars(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id == source_definition_id,
            MappingSnapshot.status == "draft",
        )
        .order_by(MappingSnapshot.destination_object_name.asc(), MappingSnapshot.created_at.desc())
    ).all()

    # Dedup to latest snapshot per destination object name
    seen_tables = set()
    latest_snapshots: list[MappingSnapshot] = []
    for s in snapshots:
        if s.destination_object_name not in seen_tables:
            seen_tables.add(s.destination_object_name)
            latest_snapshots.append(s)

    if not latest_snapshots:
        raise AuthApiError("snapshot_not_found", "No draft mapping snapshot found to push.", 404)

    # hard gate 1: 403 if actor.role !== snapshot.current_ball_role
    for snapshot in latest_snapshots:
        expected_role = snapshot.current_ball_role or "central_team"
        if actor.role != expected_role:
            raise AuthApiError(
                "forbidden",
                f"You do not hold the edit ball. Only {expected_role} can push.",
                403,
            )

    # hard gate 2: 422 if completeness fails for the actor's role
    status = get_sign_off_status(db, project_id=project_id, source_definition_id=source_definition_id)
    role_key = actor.role
    if role_key not in {"central_team", "project_stakeholder"}:
        role_key = "central_team"  # fallback

    actor_complete = True
    for obj_name, fields in status.get("bindings", {}).items():
        for sf, status_entry in fields.items():
            if not status_entry[role_key]["signed"]:
                actor_complete = False
    for lid, status_entry in status.get("lookups", {}).items():
        if not status_entry[role_key]["signed"]:
            actor_complete = False

    if not actor_complete:
        raise AuthApiError(
            "incomplete_sign_off",
            f"Completeness check failed. All bindings and lookups must be signed by {role_key}.",
            422,
        )

    # Flip ball role
    next_role = "project_stakeholder" if actor.role == "central_team" else "central_team"
    for snapshot in latest_snapshots:
        snapshot.current_ball_role = next_role

    # Create notifications to opposite role project members
    target_members = db.scalars(
        select(User)
        .join(ProjectMembership, ProjectMembership.user_id == User.user_id)
        .where(
            ProjectMembership.project_id == project_id,
            User.role == next_role,
        )
    ).all()

    deep_link = f"/projects/{project_id}/feeds/{source_definition_id}/review"
    for tm in target_members:
        create_notification(
            db,
            user_id=tm.user_id,
            project_id=project_id,
            event_type="review.sign_off_reminder",
            deep_link=deep_link,
            payload={
                "feed_id": source_definition_id,
                "project_id": project_id,
                "pushed_by": actor.user_id,
            },
        )

    # Mark caller's unread notifications for this feed's review as read
    from ..db.models import Notification
    unread_notifications = db.scalars(
        select(Notification).where(
            Notification.user_id == actor.user_id,
            Notification.project_id == project_id,
            Notification.read == False,
            Notification.deep_link.like(f"%{deep_link}%"),
        )
    ).all()

    now = datetime.now(UTC)
    for n in unread_notifications:
        n.read = True
        n.read_at = now

    db.commit()
    return get_sign_off_status(db, project_id=project_id, source_definition_id=source_definition_id)


def poke_reviewer(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    target_role: str,
) -> None:
    # validates actor is PM (or Admin)
    if actor.role not in {PM_ROLE, ADMIN_ROLE}:
        raise AuthApiError("forbidden", "Only project managers or administrators can send review pokes.", 403)

    # Create notifications to target_role project members
    target_members = db.scalars(
        select(User)
        .join(ProjectMembership, ProjectMembership.user_id == User.user_id)
        .where(
            ProjectMembership.project_id == project_id,
            User.role == target_role,
        )
    ).all()

    if not target_members:
        # Fallback: notify all active users with the target role
        target_members = db.scalars(
            select(User).where(
                User.role == target_role,
                User.status == "active",
            )
        ).all()

    deep_link = f"/projects/{project_id}/feeds/{source_definition_id}/review"
    for tm in target_members:
        create_notification(
            db,
            user_id=tm.user_id,
            project_id=project_id,
            event_type="review.sign_off_reminder",
            deep_link=deep_link,
            payload={
                "feed_id": source_definition_id,
                "project_id": project_id,
                "poked_by": actor.user_id,
            },
        )

    db.commit()
