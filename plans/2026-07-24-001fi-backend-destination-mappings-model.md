# Plan: Task 001fi — Backend DB Schema & API Endpoints for `destination_mappings` 1-to-Many Model

- **Task**: [001fi-backend-destination-mappings-model.md](file:///Users/vjkotra/projects/katana/tasks/001fi-backend-destination-mappings-model.md)
- **Domain**: [governance.md](file:///Users/vjkotra/projects/katana/docs/domain/governance.md)

---

## Current State
`LookupValueMap` stores separate `destination_table` (`list[dict]`) and flat `source_value_map` (`dict[str, str]`). This forces the UI to pivot data on the client side to render a 1-to-Many Destination-Anchored table.

---

## Objective
Update `db/models.py`, `api/schemas.py`, `lookup_mapping.py`, `fibers.py`, and `lookup_upsert.py` to natively store, serve, and patch 1-to-Many Destination-Anchored mappings in `destination_mappings` (`JSON list[dict]`).

---

## Blast Radius
- `engine/src/migrations_engine/db/models.py`
- `engine/src/migrations_engine/api/schemas.py`
- `engine/src/migrations_engine/management/lookup_mapping.py`
- `engine/src/migrations_engine/management/fibers.py`
- `engine/src/migrations_engine/codegen/lookup_upsert.py`
- `engine/tests/test_lookup_mapping_api.py`

---

## Detailed Implementation Instructions for Local LLM Agent

### Step 1: Update `LookupValueMap` in `db/models.py` (Line 405)
Add `destination_mappings` JSON column with default helper properties:

```python
class LookupValueMap(Base):
    __tablename__ = "lookup_value_maps"

    lookup_value_map_id = Column(String(36), primary_key=True)
    project_id = Column(String(36), ForeignKey("project_registries.project_id"), nullable=False)
    lookup_name = Column(String(128), nullable=False)
    destination_table = Column(JSON, nullable=False, default=list)
    source_value_map = Column(JSON, nullable=False, default=dict)
    destination_mappings = Column(JSON, nullable=False, default=list)
    status = Column(String(16), nullable=False, default="draft")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

### Step 2: Update Pydantic Schemas in `api/schemas.py` (Lines 480–500)
Add `DestinationMappingGroup` schema and update `LookupValueMapPatchRequest`:

```python
class DestinationMappingGroup(BaseModel):
    dest_id: str
    dest_label: str
    dest_row: dict[str, Any] = Field(default_factory=dict)
    source_values: list[str] = Field(default_factory=list)
    status: str = "draft"

class LookupValueMapPatchRequest(BaseModel):
    source_value_map: dict[str, str] | None = None
    destination_mappings: list[DestinationMappingGroup] | None = None
    add_source_value: dict[str, str] | None = None  # {"dest_id": "3", "source_value": "NEW"}
    remove_source_value: dict[str, str] | None = None  # {"dest_id": "3", "source_value": "OLD"}
```

### Step 3: Update PATCH Handler in `lookup_mapping.py` (Lines 70–100)
Handle discrete 1-to-Many actions (`add_source_value`, `remove_source_value`, `destination_mappings` overwrite):

```python
def patch_lookup_value_map(db: Session, *, actor: User, project_id: str, lookup_value_map_id: str, body: LookupValueMapPatchRequest) -> LookupValueMapResponse:
    # Existing lookup fetching logic...
    lookup_map = ...

    if body.add_source_value:
        dest_id = body.add_source_value.get("dest_id")
        src_val = body.add_source_value.get("source_value")
        if dest_id and src_val:
            mappings = list(lookup_map.destination_mappings or [])
            for group in mappings:
                if String(group.get("dest_id")) == String(dest_id):
                    if src_val not in group.get("source_values", []):
                        group.setdefault("source_values", []).append(src_val)
                    break
            lookup_map.destination_mappings = mappings
            # Also sync flat source_value_map for backward compat
            svm = dict(lookup_map.source_value_map or {})
            svm[src_val] = dest_id
            lookup_map.source_value_map = svm

    if body.remove_source_value:
        dest_id = body.remove_source_value.get("dest_id")
        src_val = body.remove_source_value.get("source_value")
        if dest_id and src_val:
            mappings = list(lookup_map.destination_mappings or [])
            for group in mappings:
                if String(group.get("dest_id")) == String(dest_id):
                    group["source_values"] = [s for s in group.get("source_values", []) if s != src_val]
                    break
            lookup_map.destination_mappings = mappings
            svm = dict(lookup_map.source_value_map or {})
            svm.pop(src_val, None)
            lookup_map.source_value_map = svm

    db.commit()
    db.refresh(lookup_map)
    return _map_response(lookup_map)
```

### Step 4: Update `_bridge_lookup_fiber_to_value_map` in `fibers.py` (Line 329)
Group proposals into `destination_mappings` array directly:

```python
dest_mappings_by_id: dict[str, dict[str, Any]] = {}
for pm in fiber.proposed_mappings:
    src_val = pm.get("source_value")
    dest_row = pm.get("dest_row") or {}
    dest_id = str(dest_row.get("id") or pm.get("dest_entry_id") or "")

    if dest_id:
        if dest_id not in dest_mappings_by_id:
            dest_mappings_by_id[dest_id] = {
                "dest_id": dest_id,
                "dest_label": dest_row.get("label") or dest_id,
                "dest_row": dest_row,
                "source_values": [],
                "status": "proposed" if src_val else "unmapped",
            }
        if src_val and src_val not in dest_mappings_by_id[dest_id]["source_values"]:
            dest_mappings_by_id[dest_id]["source_values"].append(src_val)

destination_mappings = list(dest_mappings_by_id.values())
```

### Step 5: Update `lookup_upsert.py` (Line 14)
Flatten `destination_mappings` or `value_map` into SQL clauses:

```python
def _values_clause_from_dest_mappings(destination_mappings: list[dict]) -> str:
    rows = []
    for group in destination_mappings:
        dest_id = group.get("dest_id") or ""
        for src in group.get("source_values", []):
            rows.append(f"('{_escape(src)}', '{_escape(dest_id)}')")
    return ", ".join(sorted(rows))
```

---

## Tests
```bash
cd engine && source ../.venv/bin/activate && pytest -v
```

---

## Verification Checklist
- [ ] `LookupValueMap` stores `destination_mappings` natively.
- [ ] Backend PATCH supports `add_source_value` and `remove_source_value`.
- [ ] Backend test suite passes 100%.

---

## Commit
`feat(lookup): add destination_mappings 1-to-many model and backend API actions (001fi)`
