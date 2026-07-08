# Plan: 001ca — Lookup Fiber → LookupValueMap Bridge

- **Task Link:** [tasks/001ca-lookup-fiber-bridge.md](../tasks/001ca-lookup-fiber-bridge.md)

## Current State

`approve_fiber` sets `fiber.status = "business_approved"` and commits. Nothing else happens. `LookupValueMap` is only populated if the operator manually calls `POST /lookup-maps`. `generate_lookup_snapshot` then reads `LookupValueMap.source_value_map` and raises `409` when it's empty.

## Objective

When `approve_fiber` is called for a lookup fiber, automatically compile the confirmed `LookupMapping` rows into a `LookupValueMap` row — one per `lookup_name` on the fiber. This makes `generate_lookup_snapshot` work without any manual intervention.

## Blast Radius

| File | Change |
|---|---|
| `engine/src/migrations_engine/management/fibers.py` | Only file changed |
| `engine/src/migrations_engine/management/lookup_mapping.py` | Import `_extract_destination_id` from here (or inline) |

No migrations, no schema changes, no frontend changes.

## File Changes

### `engine/src/migrations_engine/management/fibers.py`

**Step 1 — Add imports**

```python
from ..db.models import (
    ...existing...,
    LookupDestEntry,
    LookupDestFeed,
    LookupMapping,
    LookupValueMap,
)
from .lookup_mapping import _extract_destination_id
```

**Step 2 — Add helper `_bridge_lookup_fiber_to_value_map`**

Insert above `approve_fiber`:

```python
def _bridge_lookup_fiber_to_value_map(db: Session, fiber: ProjectFiber) -> None:
    """
    After a lookup fiber is approved, compile confirmed LookupMapping rows
    into LookupValueMap so generate_lookup_snapshot can proceed.
    One LookupValueMap upserted per lookup_name on the fiber.
    """
    confirmed_mappings = db.scalars(
        select(LookupMapping).where(
            LookupMapping.fiber_id == fiber.fiber_id,
            LookupMapping.status == "confirmed",
        )
    ).all()

    if not confirmed_mappings:
        return

    # Group by lookup_name (a fiber may cover multiple lookup columns)
    by_name: dict[str, list[LookupMapping]] = {}
    for m in confirmed_mappings:
        by_name.setdefault(m.lookup_name, []).append(m)

    # Fetch destination reference rows for this fiber (one LookupDestFeed per fiber)
    dest_feed = db.scalar(
        select(LookupDestFeed).where(LookupDestFeed.fiber_id == fiber.fiber_id)
    )
    dest_entries: list[dict] = []
    if dest_feed:
        dest_entries = [
            row.row_data
            for row in db.scalars(
                select(LookupDestEntry).where(
                    LookupDestEntry.dest_feed_id == dest_feed.dest_feed_id
                )
            ).all()
        ]

    for lookup_name, mappings in by_name.items():
        source_value_map = {}
        for m in mappings:
            if m.dest_row:
                dest_id = _extract_destination_id(m.dest_row)
                if dest_id:
                    source_value_map[m.source_value] = dest_id

        # Find existing draft for this feed + lookup_name and replace it
        existing = db.scalar(
            select(LookupValueMap).where(
                LookupValueMap.source_definition_id == fiber.feed_id,
                LookupValueMap.lookup_name == lookup_name,
                LookupValueMap.status == "draft",
            ).order_by(LookupValueMap.created_at.desc())
        )
        if existing:
            # Only add source values not already in the map.
            # Values from previously approved fibers are never overwritten —
            # first business-approved fiber wins per source value.
            for src, dest in source_value_map.items():
                if src not in existing.source_value_map:
                    existing.source_value_map[src] = dest
            # Merge destination rows (add any new rows not already present)
            existing_dest_ids = {_extract_destination_id(r) for r in existing.destination_table}
            for row in dest_entries:
                if _extract_destination_id(row) not in existing_dest_ids:
                    existing.destination_table = existing.destination_table + [row]
        else:
            db.add(LookupValueMap(
                source_definition_id=fiber.feed_id,
                lookup_name=lookup_name,
                destination_table=dest_entries,
                source_value_map=source_value_map,
                status="draft",
            ))
```

**Step 3 — Call it in `approve_fiber`**

```python
def approve_fiber(...) -> FiberResponse:
    ...
    fiber.status = "business_approved"
    if fiber.fiber_type == "lookup":
        _bridge_lookup_fiber_to_value_map(db, fiber)   # add this line
    db.commit()
    db.refresh(fiber)
    return _fiber_response(fiber)
```

## Pitfalls

- `_extract_destination_id` is a private function in `lookup_mapping.py`. Importing private helpers across management modules is acceptable here; the alternative (inlining the 5-line function) is also fine if cross-module import feels wrong.
- If `confirmed_mappings` is empty (operator approved but had no confirmed rows — edge case), the helper returns early and no `LookupValueMap` is written. `generate_lookup_snapshot` will still raise `409`, which is correct — there's nothing to snapshot.
- `LookupDestFeed` has `unique=True` on `fiber_id`, so the `db.scalar(select(LookupDestFeed)...)` returns exactly one row or `None`.
- `dest_entries` may be empty if the dest feed was never populated. The `LookupValueMap` is still written with `destination_table=[]`; `generate_lookup_snapshot` will reject it only if `source_value_map` has values pointing to IDs not in `destination_table` — valid, recoverable error for the operator.

## Verification

1. Create a lookup fiber, run AI analysis, confirm mappings, submit for business approval
2. Approve the fiber → check DB: `LookupValueMap` row exists with `source_value_map` populated
3. Call `generate_lookup_snapshot` — succeeds without manual `LookupValueMap` creation
4. Repeat with a fiber that has zero confirmed mappings — approval succeeds, no `LookupValueMap` written, no 500

## Commit

- `fix(001ca): bridge confirmed lookup fiber mappings into LookupValueMap on approval`
