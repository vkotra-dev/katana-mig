# Plan: 001bp — Bulk Approve/Reject All Snapshots on Review Page

- **Task Link:** [001bp-review-bulk-approve-reject.md](file:///Users/vjkotra/projects/katana/tasks/001bp-review-bulk-approve-reject.md)
- **Domain Link:** [source-model.md](file:///Users/vjkotra/projects/katana/docs/domain/source-model.md)

## Current State

`approve_mapping` and `reject_mapping` in `review.py` each resolve `destination_object_name` via `_get_project_destination_schema` (returns the first DDL table name) when none is passed, then call `_latest_snapshot` for that single table. With two destination tables per feed (`policy_master`, `policy_claims`), a single Approve/Reject call changes exactly one snapshot. After reload, if `mappingSnapshots[0]` is already approved, `showControls` becomes false and the stakeholder cannot act on the remaining draft — it is permanently stuck.

The frontend `showControls` check (`representativeSnapshot?.status === "draft"`) and status badge (`representativeSnapshot.status`) both use only the first snapshot, so they lie once partial approval occurs.

## Objective

One Approve click approves ALL draft snapshots for the feed. One Reject click rejects ALL draft snapshots. Status badge and `showControls` reflect the aggregate state across all snapshots.

## Out of Scope

- Per-table individual approve/reject
- Notifications to operations after rejection
- New Alembic migrations (status is a column value change, not schema change)

## Blast Radius

- `engine/src/migrations_engine/mapping/review.py` — `approve_mapping`, `reject_mapping`
- `engine/src/migrations_engine/routes/mapping.py` — approve/reject route handlers (route file, not `mapping_snapshots.py`)
- `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` — `showControls`, status badge
- `web/app/projects/[id]/feeds/[feedId]/review/page.test.tsx` — add aggregate status badge + controls visibility tests

## File Changes

### `engine/src/migrations_engine/mapping/review.py`

**`approve_mapping`:** Replace the single-snapshot lookup with a bulk query over all draft snapshots for the feed. Approve each and collect approved table names for `destination_object_references`.

```python
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

    current_refs = source_definition.destination_object_references or []
    new_refs = current_refs + [t for t in approved_tables if t not in current_refs]
    source_definition.destination_object_references = new_refs

    db.commit()
    db.refresh(drafts[-1])
    return _snapshot_to_response(drafts[-1])
```

**`reject_mapping`:** Same bulk pattern — query all drafts for the feed, reject each.

```python
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
    return _snapshot_to_response(drafts[-1])
```

### `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`

**`showControls`:** Replace single-snapshot check with `any()` over all snapshots:
```ts
const showControls = role === "project_stakeholder" && mappingSnapshots.some(s => s.status === "draft");
```

**Status badge:** Derive aggregate status:
```ts
const aggregateStatus = mappingSnapshots.length === 0
  ? null
  : mappingSnapshots.every(s => s.status === "approved")
  ? "approved"
  : mappingSnapshots.some(s => s.status === "rejected")
  ? "rejected"
  : "draft";
```

Replace `representativeSnapshot.status` with `aggregateStatus` in the badge JSX. Keep `representativeSnapshot` for the null-check guard on the ReviewGrid.

## Tests

Add to `web/app/projects/[id]/feeds/[feedId]/review/page.test.tsx`:

- **Aggregate status badge:** render with two snapshots (one approved, one draft) → badge shows "draft"; both approved → badge shows "approved"; any rejected → badge shows "rejected"
- **`showControls` visibility:** `project_stakeholder` + any snapshot draft → Approve/Reject buttons rendered; all approved → buttons absent; `operations` role → buttons always absent regardless of status

## Verification

1. Analyze a feed → two draft snapshots created (`policy_master`, `policy_claims`)
2. Navigate to the review page as `project_stakeholder`
3. Status badge shows "draft", Approve button is visible
4. Click Approve — both snapshots become "approved" in one call
5. Status badge shows "approved", Approve button disappears
6. Repeat with Reject: both snapshots become "rejected", badge shows "rejected"
7. Single-table feeds (if any exist) continue to work identically

## Pitfalls

- The bulk query orders by `destination_object_name asc, created_at desc` then deduplicates in Python to get the latest draft per table. This mirrors `select_all_feed_mapping_snapshots` in `snapshots.py`.
- `db.refresh(drafts[-1])` only refreshes the last snapshot for the route return value — the frontend ignores this return and reloads via `getAllApprovedMappingSnapshots`, so refreshing all N is unnecessary.
- The `destination_object_name` explicit parameter path is kept for backward compatibility with any direct callers that pass a table name.

## Commit

- `fix(001bp): approve and reject all draft snapshots for a feed in one action`
