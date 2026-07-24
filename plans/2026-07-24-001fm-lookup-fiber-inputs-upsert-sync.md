# Plan: Task 001fm — Fix Lookup Fiber Source & Destination Values Upsert and Pre-fill

**Status**: ✅ All 5 steps implemented and verified.

- **Task**: [001fm-lookup-fiber-inputs-upsert-sync.md](file:///Users/vjkotra/projects/katana/tasks/001fm-lookup-fiber-inputs-upsert-sync.md)

---

## Goal Description

When AI Analyze is triggered on the Feed Page (`/projects/[id]/feeds/[feedId]`), source values and destination CSV are sent to `POST /projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs` (`submit_lookup_inputs`).

Currently:
1. **Backend**: `submit_lookup_inputs()` updates `fiber.proposed_mappings`, but **fails to upsert/sync `LookupValueMap`**. Draft `LookupValueMap` instances stay stale with empty or outdated mappings.
2. **Frontend**: When the page loads or refreshes, `lookupDrafts` state defaults `sourceText` and `destText` to empty strings `""`, wiping out the displayed source & destination input textareas.

This task fixes both backend `LookupValueMap` upsert/sync AND frontend textarea pre-fill from existing `LookupValueMap` data.

---

## Step-by-Step Build Instructions (Agent Executable)

---

### Step 1: Add `_sync_lookup_value_map_from_proposed_mappings()` helper in `fibers.py`

**File**: [engine/src/migrations_engine/management/fibers.py](file:///Users/vjkotra/projects/katana/engine/src/migrations_engine/management/fibers.py)  
**Location**: Insert at line 345 before `_bridge_lookup_fiber_to_value_map`.

#### Exact Code to Add:

```python
def _sync_lookup_value_map_from_proposed_mappings(
    db: Session,
    *,
    project_id: str,
    lookup_name: str,
    proposed_mappings: list[dict[str, Any]],
) -> LookupValueMap:
    """
    Synchronize or create a draft LookupValueMap from fiber proposed_mappings.
    Populates source_value_map, destination_table, AND structured destination_mappings.
    """
    source_value_map: dict[str, str] = {}
    destination_table: list[dict[str, Any]] = []
    seen_dest_ids: set[str] = set()
    dest_mappings_by_id: dict[str, dict[str, Any]] = {}

    for pm in proposed_mappings:
        src_val = pm.get("source_value")
        dest_row_data = pm.get("dest_row")
        dest_entry_id = pm.get("dest_entry_id")
        if src_val:
            business_key = (
                dest_row_data and (dest_row_data.get("id") or dest_row_data.get("destination_id"))
            ) or (dest_entry_id and str(dest_entry_id))
            if business_key:
                dest_id = str(business_key)
                source_value_map[src_val] = dest_id
                if dest_id not in dest_mappings_by_id:
                    dest_label = _extract_destination_label(dest_row_data) if dest_row_data else ""
                    dest_mappings_by_id[dest_id] = {
                        "dest_id": dest_id,
                        "dest_label": dest_label,
                        "dest_row": dest_row_data or {},
                        "source_values": [],
                        "status": "proposed" if src_val else "unmapped",
                    }
                if src_val not in dest_mappings_by_id[dest_id]["source_values"]:
                    dest_mappings_by_id[dest_id]["source_values"].append(src_val)
        if dest_row_data:
            row_id = dest_row_data.get("id") or dest_row_data.get("destination_id")
            if row_id and str(row_id) not in seen_dest_ids:
                seen_dest_ids.add(str(row_id))
                destination_table.append(dest_row_data)

    destination_mappings = list(dest_mappings_by_id.values()) if dest_mappings_by_id else []

    val_map = db.scalar(
        select(LookupValueMap).where(
            LookupValueMap.project_id == project_id,
            LookupValueMap.lookup_name == lookup_name,
            LookupValueMap.status == "draft",
        ).order_by(LookupValueMap.created_at.desc(), LookupValueMap.lookup_value_map_id.desc())
    )

    if val_map:
        val_map.source_value_map = source_value_map
        val_map.destination_table = destination_table
        val_map.destination_mappings = destination_mappings
    else:
        val_map = LookupValueMap(
            lookup_value_map_id=new_id(),
            project_id=project_id,
            lookup_name=lookup_name,
            destination_table=destination_table,
            source_value_map=source_value_map,
            destination_mappings=destination_mappings,
            status="draft",
        )
        db.add(val_map)

    return val_map
```

---

### Step 2: Refactor `_bridge_lookup_fiber_to_value_map()`

**File**: [engine/src/migrations_engine/management/fibers.py](file:///Users/vjkotra/projects/katana/engine/src/migrations_engine/management/fibers.py)  
**Lines**: 346–407

#### Exact Code Diff to Apply:

```diff
 def _bridge_lookup_fiber_to_value_map(db: Session, fiber: ProjectFiber) -> None:
-    """
-    After a lookup fiber is approved, compile fiber.proposed_mappings JSON
-    into LookupValueMap so generate_lookup_snapshot can proceed.
-    One LookupValueMap upserted per lookup_name on the fiber.
-    """
     if not fiber.proposed_mappings:
         return
 
-    source_value_map: dict[str, str] = {}
-    seen_dest_ids: set[str] = set()
-    dest_entries: list[dict[str, Any]] = []
-
-    for pm in fiber.proposed_mappings:
-        src_val = pm.get("source_value")
-        dest_row = pm.get("dest_row") or {}
-        dest_id = dest_row.get("id")
-
-        if src_val and dest_id:
-            source_value_map[src_val] = str(dest_id)
-
-        if dest_id and str(dest_id) not in seen_dest_ids:
-            seen_dest_ids.add(str(dest_id))
-            dest_entries.append({
-                "id": str(dest_id),
-                "label": dest_row.get("label") or str(dest_id),
-            })
-
-    # Find existing draft for this project + lookup_name and merge
-    existing = db.scalar(
-        select(LookupValueMap).where(
-            LookupValueMap.project_id == fiber.project_id,
-            LookupValueMap.lookup_name == fiber.fiber_key,
-            LookupValueMap.status == "draft",
-        ).order_by(LookupValueMap.created_at.desc())
-    )
-    if existing:
-        new_source_value_map = dict(existing.source_value_map)
-        for src, dest in source_value_map.items():
-            if src not in new_source_value_map:
-                new_source_value_map[src] = dest
-        existing.source_value_map = new_source_value_map
-
-        existing_dest_ids = {
-            r.get("id") for r in existing.destination_table if r.get("id")
-        }
-        new_dest_table = list(existing.destination_table)
-        for row in dest_entries:
-            row_id = row.get("id")
-            if row_id not in existing_dest_ids:
-                new_dest_table.append(row)
-        existing.destination_table = new_dest_table
-    else:
-        db.add(LookupValueMap(
-            lookup_value_map_id=new_id(),
-            project_id=fiber.project_id,
-            lookup_name=fiber.fiber_key,
-            destination_table=dest_entries,
-            source_value_map=source_value_map,
-            status="draft",
-        ))
+    _sync_lookup_value_map_from_proposed_mappings(
+        db,
+        project_id=fiber.project_id,
+        lookup_name=fiber.fiber_key,
+        proposed_mappings=fiber.proposed_mappings,
+    )
```

---

### Step 3: Wire helper into `submit_lookup_inputs()`

**File**: [engine/src/migrations_engine/management/fibers.py](file:///Users/vjkotra/projects/katana/engine/src/migrations_engine/management/fibers.py)  
**Lines**: 849–853

#### Exact Code Diff to Apply:

```diff
     fiber.proposed_mappings = proposals_for_denorm
     fiber.status = "mapped"
+    _sync_lookup_value_map_from_proposed_mappings(
+        db,
+        project_id=project_id,
+        lookup_name=fiber.fiber_key,
+        proposed_mappings=proposals_for_denorm,
+    )
     db.commit()
     db.refresh(fiber)
     return _fiber_response(fiber)
```

---

### Step 4: Add Frontend Pre-fill Helpers in `web/app/projects/[id]/feeds/[feedId]/page.tsx`

**File**: [web/app/projects/[id]/feeds/[feedId]/page.tsx](file:///Users/vjkotra/projects/katana/web/app/projects/%5Bid%5D/feeds/%5BfeedId%5D/page.tsx)  
**Lines**: 885–888

#### Exact Code Diff to Apply:

```diff
                       const lookupMap = lookupMaps.find((m) => m.lookupName === lName);

+                      const defaultSourceText = lookupMap?.sourceValueMap
+                        ? Object.keys(lookupMap.sourceValueMap).join("\n")
+                        : fiber?.proposed_mappings
+                        ? Array.from(new Set(fiber.proposed_mappings.map((pm: any) => pm.source_value).filter(Boolean))).join("\n")
+                        : "";
+
+                      const defaultDestText = lookupMap?.destinationTable && lookupMap.destinationTable.length > 0
+                        ? (() => {
+                            const keys = Array.from(new Set(lookupMap.destinationTable.flatMap((r) => Object.keys(r))));
+                            const header = keys.join(",");
+                            const rows = lookupMap.destinationTable.map((r) => keys.map((k) => {
+                              const val = r[k];
+                              if (val === null || val === undefined) return "";
+                              const str = String(val);
+                              return str.includes(",") || str.includes("\"") || str.includes("\n")
+                                ? `"${str.replace(/"/g, '""')}"`
+                                : str;
+                            }).join(","));
+                            return [header, ...rows].join("\n");
+                          })()
+                        : "";

-                      const draft = lookupDrafts[lName] || { sourceText: "", destText: "", analyzing: false, error: null };
+                      const userDraft = lookupDrafts[lName];
+                      const draft = {
+                        sourceText: userDraft?.sourceText ?? defaultSourceText,
+                        destText: userDraft?.destText ?? defaultDestText,
+                        analyzing: userDraft?.analyzing ?? false,
+                        error: userDraft?.error ?? null,
+                      };
```

---

### Step 5: Add Backend Test in `test_lookup_fiber_api.py`

**File**: [engine/tests/test_lookup_fiber_api.py](file:///Users/vjkotra/projects/katana/engine/tests/test_lookup_fiber_api.py)

Add test asserting `LookupValueMap` and `destination_mappings` are created and updated after `submit_lookup_inputs`:

```python
def test_submit_lookup_inputs_upserts_lookup_value_map(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        headers={"Authorization": f"Bearer {_admin_token()}"},
        json={
            "source_values": ["A", "B"],
            "destination_lookup_csv": "id,label\n1,Active\n2,Blocked",
        },
    )
    assert response.status_code == 200, response.text

    from migrations_engine.db.models import LookupValueMap
    with SessionLocal() as db:
        lvm = db.scalar(
            select(LookupValueMap).where(
                LookupValueMap.project_id == project_id,
                LookupValueMap.lookup_name == "status_code",
                LookupValueMap.status == "draft",
            )
        )
        assert lvm is not None, "LookupValueMap must be created/upserted by submit_lookup_inputs"
        assert lvm.source_value_map == {"A": "1", "B": "2"}
        assert len(lvm.destination_mappings) == 2
        active_group = next(g for g in lvm.destination_mappings if g["dest_id"] == "1")
        assert active_group["dest_label"] == "Active"
        assert active_group["source_values"] == ["A"]
```

---

## Verification Plan

### Automated Tests

```bash
cd engine && source ../.venv/bin/activate
pytest tests/test_lookup_fiber_api.py -v
pytest -v

cd ../web
npm test -- --run
```

### Manual Verification

1. On the Feed Page (`/projects/[id]/feeds/[feedId]`), fill out source values and destination lookup CSV for a lookup fiber and click "AI Analyze".
2. Verify that `LookupValueMap` is immediately updated in the database and API responses with both `source_value_map` and structured `destination_mappings`.
3. Refresh the page: verify that the source values and destination CSV textareas remain pre-filled with the existing values instead of defaulting to empty textareas.
