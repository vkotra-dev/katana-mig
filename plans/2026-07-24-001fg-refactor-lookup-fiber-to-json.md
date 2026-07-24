# Plan: Task 001fg — Refactor Fiber AI Discovery to ProjectFiber.proposed_mappings JSON

- **Task**: [001fg-refactor-lookup-fiber-to-json.md](file:///Users/vjkotra/projects/katana/tasks/001fg-refactor-lookup-fiber-to-json.md)
- **Domain**: [governance.md](file:///Users/vjkotra/projects/katana/docs/domain/governance.md)

---

## Current State
Currently, `_analyze_lookup_fiber()` in `engine/src/migrations_engine/management/fibers.py` writes ~100–200 transient SQL rows per AI run across 4 relational tables (`LookupSourceEntry`, `LookupDestFeed`, `LookupDestEntry`, `LookupMapping`).

---

## Objective
Refactor `fibers.py` to write AI lookup proposals directly into `ProjectFiber.proposed_mappings` (`JSON list[dict]`), eliminating SQL inserts into the 4 transient tables.

---

## Out of Scope
- Dropping ORM models from `db/models.py` (handled in Task 001fh).
- Alembic database migration (handled in Task 001fh).

---

## Blast Radius
- `engine/src/migrations_engine/management/fibers.py`
- `engine/src/migrations_engine/routes/fibers.py`
- `engine/tests/test_lookup_fiber_api.py`

---

## Detailed Implementation Instructions for Local LLM Agent

### Step 1: Update `_analyze_lookup_fiber` in `fibers.py` (Lines 938–970)
Replace the creation of `LookupMapping`, `LookupSourceEntry`, `LookupDestFeed`, and `LookupDestEntry` DB objects with direct JSON construction:

```python
# Build JSON proposed_mappings payload directly from LLM result
proposals_for_denorm: list[dict[str, Any]] = []

for proposal in ai_result.proposals:
    dest_entry = dest_entry_by_pk.get(proposal.dest_id) if proposal.dest_id else None
    dest_row = {
        "id": proposal.dest_id,
        "label": proposal.dest_value,
    }
    proposals_for_denorm.append(
        {
            "source_value": proposal.source_value,
            "dest_entry_id": dest_entry.entry_id if dest_entry else None,
            "dest_row": dest_row,
            "confidence_score": proposal.confidence_score,
            "status": "proposed" if proposal.source_value else "unmatched",
        }
    )

fiber.proposed_mappings = proposals_for_denorm
fiber.status = "mapped"
db.commit()
db.refresh(fiber)
return _fiber_response(fiber)
```

### Step 2: Update `_bridge_lookup_fiber_to_value_map` in `fibers.py` (Lines 347–380)
Construct `source_value_map` and `destination_table` directly from `fiber.proposed_mappings`:

```python
def _bridge_lookup_fiber_to_value_map(db: Session, fiber: ProjectFiber) -> None:
    if not fiber.proposed_mappings:
        return

    source_value_map: dict[str, str] = {}
    dest_entries: list[dict[str, Any]] = []
    seen_dest_ids: set[str] = set()

    for pm in fiber.proposed_mappings:
        src_val = pm.get("source_value")
        dest_row = pm.get("dest_row") or {}
        dest_id = dest_row.get("id") or pm.get("dest_entry_id")

        if src_val and dest_id:
            source_value_map[src_val] = str(dest_id)

        if dest_id and str(dest_id) not in seen_dest_ids:
            seen_dest_ids.add(str(dest_id))
            dest_entries.append({
                "id": str(dest_id),
                "label": dest_row.get("label") or str(dest_id),
            })

    # Upsert into LookupValueMap (draft)
    existing = db.scalar(
        select(LookupValueMap).where(
            LookupValueMap.project_id == fiber.project_id,
            LookupValueMap.lookup_name == fiber.fiber_key,
            LookupValueMap.status == "draft",
        ).order_by(LookupValueMap.created_at.desc())
    )
    if existing:
        merged_map = dict(existing.source_value_map)
        merged_map.update(source_value_map)
        existing.source_value_map = merged_map
    else:
        db.add(LookupValueMap(
            lookup_value_map_id=new_id(),
            project_id=fiber.project_id,
            lookup_name=fiber.fiber_key,
            destination_table=dest_entries,
            source_value_map=source_value_map,
            status="draft",
        ))
    db.commit()
```

### Step 3: Update `test_lookup_fiber_api.py` (Lines 40–90)
Update test assertions from `db.scalars(select(LookupMapping))` to `fiber.proposed_mappings`:

```python
# Assert proposed_mappings array length and structure
assert fiber.proposed_mappings is not None
assert len(fiber.proposed_mappings) > 0
assert fiber.proposed_mappings[0]["source_value"] is not None
```

---

## Tests
```bash
cd engine && source ../.venv/bin/activate && pytest -v
```

---

## Verification Checklist
- [ ] `_analyze_lookup_fiber()` writes directly to `fiber.proposed_mappings` without touching `LookupMapping` or `LookupSourceEntry`.
- [ ] `_bridge_lookup_fiber_to_value_map()` populates `LookupValueMap` directly from `fiber.proposed_mappings`.
- [ ] All 377 engine backend pytest tests pass 100%.

---

## Commit
`refactor(fibers): store lookup proposals directly in ProjectFiber proposed_mappings JSON (001fg)`
