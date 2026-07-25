# Plan: Task 001gu — Wire `unmatched_source_values` Through, Reject Cross-Destination Duplicates

- **Task**: [001gu-lookup-unmapped-source-values-and-case-insensitive-add.md](file:///Users/vjkotra/projects/katana/tasks/001gu-lookup-unmapped-source-values-and-case-insensitive-add.md)

---

## Goal Description

Two independent fixes, sharing one new DB column:

1. `_LookupMappingResult.unmatched_source_values` (the AI's own "I couldn't confidently match these" list) is computed correctly today and then discarded — wire it through `submit_lookup_inputs` → `_sync_lookup_value_map_from_proposed_mappings` → the new `LookupValueMap.unmapped_source_values` column → the API response → the UI (same visual pattern as `ReviewGrid.tsx`'s existing `unmappedSourceFields`).
2. `add_source_value` must do a case-insensitive check against already-mapped source values before doing anything else: same destination → no-op; **different** destination → **reject with an error**, do not silently succeed and do not fabricate a new destination group. Only a value with no case-insensitive match at all, and a `dest_id` that doesn't correspond to anything real, gets routed into the same `unmapped_source_values` bucket from point 1.

**Hard constraint, applies to Steps 9-11 (the frontend steps): this is a backend-only decision.** All of the case-insensitive matching, the no-op/reject/unmapped routing decision, and the `dest_id` validation live exclusively in Step 6's backend handler. The frontend steps in this plan are display-only — rendering the `unmapped_source_values` list and letting the existing generic error-catch surface a 409 message. Do not add any client-side "is this a duplicate" or "is this dest_id valid" check anywhere in `LookupMappingTable.tsx`, `ReviewGrid.tsx`, or `review/page.tsx` while executing this plan, even if it seems like a small UX improvement (e.g. disabling the Add button, greying out a value) — a second copy of this logic in JS is exactly the kind of frontend/backend drift that caused the original incident (the UI and the persisted record disagreeing about what a row's real `dest_id` was).

---

## Step 0: Environment

Use `.venv/bin/python` for everything backend-related — see [[001gr]]'s task file for why a bare `python`/`pytest` fails on this machine.

---

## Step 1: Alembic migration

**New file**: `engine/migrations/versions/0041_add_unmapped_source_values_column.py`

Confirm current head first: `cd engine && /Users/vjkotra/projects/katana/.venv/bin/python -m alembic heads` → expect `0040 (head)`. If different, adjust `down_revision` below.

```python
"""add unmapped_source_values column to lookup_value_maps

Revision ID: 0041
Revises: 0040
Create Date: 2026-07-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "0041"
down_revision = "0040"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE lookup_value_maps ADD COLUMN IF NOT EXISTS unmapped_source_values JSON NULL"
    )
    op.execute("UPDATE lookup_value_maps SET unmapped_source_values = '[]' WHERE unmapped_source_values IS NULL")
    op.execute(
        "ALTER TABLE lookup_value_maps MODIFY COLUMN unmapped_source_values JSON NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("lookup_value_maps", "unmapped_source_values")
```

Mirrors `0040_add_destination_mappings_column.py` exactly. **Do not run `alembic upgrade head` against the live dev MySQL database as part of this plan** — the test suite uses a separate sqlite DB and doesn't need it; applying to the real dev DB is a separate, explicit step for whoever owns that environment.

---

## Step 2: Add the column to the SQLAlchemy model

**File**: [engine/src/migrations_engine/db/models.py](file:///Users/vjkotra/projects/katana/engine/src/migrations_engine/db/models.py)

```diff
     destination_mappings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
+    unmapped_source_values: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
     status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
```

(Inside `class LookupValueMap(Base):`, right after `destination_mappings`.)

---

## Step 3: Add the field to the response schema

**File**: [engine/src/migrations_engine/api/schemas.py](file:///Users/vjkotra/projects/katana/engine/src/migrations_engine/api/schemas.py)

```diff
 class LookupValueMapResponse(BaseModel):
     lookup_value_map_id: str
     project_id: str
     lookup_name: str
     destination_table: list[dict[str, Any]]
     source_value_map: dict[str, str]
     destination_mappings: list[DestinationMappingGroup]
     status: Literal["draft", "approved"]
     unmapped_row_count: int = 0
+    unmapped_source_values: list[str] = Field(default_factory=list)
     created_at: datetime
```

---

## Step 4: Update `_lookup_value_map_response`

**File**: [engine/src/migrations_engine/management/lookup_mapping.py](file:///Users/vjkotra/projects/katana/engine/src/migrations_engine/management/lookup_mapping.py)

Search for `def _lookup_value_map_response`:

```diff
 def _lookup_value_map_response(row: LookupValueMap, unmapped_row_count: int = 0) -> LookupValueMapResponse:
     dest_mappings = row.destination_mappings or []
     return LookupValueMapResponse(
         lookup_value_map_id=row.lookup_value_map_id,
         project_id=row.project_id,
         lookup_name=row.lookup_name,
         destination_table=row.destination_table,
         source_value_map=row.source_value_map,
         destination_mappings=dest_mappings,
         status=row.status,
         unmapped_row_count=unmapped_row_count,
+        unmapped_source_values=row.unmapped_source_values or [],
         created_at=row.created_at,
     )
```

---

## Step 5: Wire the AI's `unmatched_source_values` through (`fibers.py`)

**File**: [engine/src/migrations_engine/management/fibers.py](file:///Users/vjkotra/projects/katana/engine/src/migrations_engine/management/fibers.py)

### 5a. Add a parameter to `_sync_lookup_value_map_from_proposed_mappings`

Search for `def _sync_lookup_value_map_from_proposed_mappings`:

```diff
 def _sync_lookup_value_map_from_proposed_mappings(
     db: Session,
     *,
     project_id: str,
     lookup_name: str,
     proposed_mappings: list[dict[str, Any]],
+    unmatched_source_values: list[str] | None = None,
 ) -> LookupValueMap:
```

Then, further down in the same function, update **both** branches that construct/update `val_map`:

```diff
     if val_map:
         val_map.source_value_map = source_value_map
         val_map.destination_table = destination_table
         val_map.destination_mappings = destination_mappings
+        val_map.unmapped_source_values = list(unmatched_source_values or [])
     else:
         val_map = LookupValueMap(
             lookup_value_map_id=new_id(),
             project_id=project_id,
             lookup_name=lookup_name,
             destination_table=destination_table,
             source_value_map=source_value_map,
             destination_mappings=destination_mappings,
+            unmapped_source_values=list(unmatched_source_values or []),
             status="draft",
         )
         db.add(val_map)
```

### 5b. Pass it at the call site in `submit_lookup_inputs`

Search for `_sync_lookup_value_map_from_proposed_mappings(` inside `submit_lookup_inputs` (there's only one call site for this function today — verify with a search before editing, since Step 5a's function is called from exactly one place):

```diff
     fiber.proposed_mappings = proposals_for_denorm
     fiber.status = "mapped"
     _sync_lookup_value_map_from_proposed_mappings(
         db,
         project_id=project_id,
         lookup_name=fiber.fiber_key,
         proposed_mappings=proposals_for_denorm,
+        unmatched_source_values=ai_result.unmatched_source_values,
     )
     db.commit()
```

---

## Step 6: Rewrite `add_source_value` (`lookup_mapping.py`)

**File**: [engine/src/migrations_engine/management/lookup_mapping.py](file:///Users/vjkotra/projects/katana/engine/src/migrations_engine/management/lookup_mapping.py)

Search for `# Handle add_source_value action`:

```diff
     # Handle add_source_value action
     if body.add_source_value:
         dest_id = body.add_source_value.get("dest_id", "")
         src_val = body.add_source_value.get("source_value", "")
         if dest_id and src_val:
-            mappings = _reconcile_destination_mappings(lookup_map)
-            found = False
-            for group in mappings:
-                if str(group.get("dest_id", "")) == str(dest_id):
-                    svs = group.setdefault("source_values", [])
-                    if src_val not in svs:
-                        svs.append(src_val)
-                    found = True
-                    break
-            if not found:
-                label, dest_row_data = _lookup_dest_label(lookup_map, dest_id)
-                mappings.append({
-                    "dest_id": dest_id,
-                    "dest_label": label,
-                    "dest_row": dest_row_data,
-                    "source_values": [src_val],
-                    "status": "draft",
-                })
-            lookup_map.destination_mappings = mappings
-            flag_modified(lookup_map, "destination_mappings")
-            # Sync flat source_value_map for backward compat
-            svm = dict(lookup_map.source_value_map or {})
-            svm[src_val] = dest_id
-            lookup_map.source_value_map = svm
+            existing_svm = lookup_map.source_value_map or {}
+            src_val_folded = src_val.strip().lower()
+            case_insensitive_match = next(
+                (k for k in existing_svm if k.strip().lower() == src_val_folded),
+                None,
+            )
+            if case_insensitive_match is not None:
+                existing_dest_id = existing_svm[case_insensitive_match]
+                if str(existing_dest_id) != str(dest_id):
+                    raise AuthApiError(
+                        "source_value_already_mapped",
+                        f"'{src_val}' is already mapped to a different destination ({existing_dest_id}).",
+                        409,
+                    )
+                # Same destination, different casing of an already-mapped value — harmless no-op.
+            else:
+                mappings = _reconcile_destination_mappings(lookup_map)
+                known_dest_ids = {str(g.get("dest_id", "")) for g in mappings}
+                known_dest_ids |= {
+                    str(row.get("id") or row.get("destination_id") or "")
+                    for row in (lookup_map.destination_table or [])
+                }
+                known_dest_ids.discard("")
+                if str(dest_id) in known_dest_ids:
+                    found = False
+                    for group in mappings:
+                        if str(group.get("dest_id", "")) == str(dest_id):
+                            svs = group.setdefault("source_values", [])
+                            if src_val not in svs:
+                                svs.append(src_val)
+                            found = True
+                            break
+                    if not found:
+                        label, dest_row_data = _lookup_dest_label(lookup_map, dest_id)
+                        mappings.append({
+                            "dest_id": dest_id,
+                            "dest_label": label,
+                            "dest_row": dest_row_data,
+                            "source_values": [src_val],
+                            "status": "draft",
+                        })
+                    lookup_map.destination_mappings = mappings
+                    flag_modified(lookup_map, "destination_mappings")
+                    svm = dict(lookup_map.source_value_map or {})
+                    svm[src_val] = dest_id
+                    lookup_map.source_value_map = svm
+                else:
+                    # dest_id doesn't correspond to anything real — do not fabricate a
+                    # destination group. Track it as unmapped instead.
+                    unmapped = list(lookup_map.unmapped_source_values or [])
+                    if src_val not in unmapped:
+                        unmapped.append(src_val)
+                        lookup_map.unmapped_source_values = unmapped
+                        flag_modified(lookup_map, "unmapped_source_values")
```

`AuthApiError` is already imported in this file (`from ..api.deps import AuthApiError`, used elsewhere e.g. `lookup_map_approved`) — no new import needed.

---

## Step 7: Regression tests

**File**: [engine/tests/test_lookup_mapping_api.py](file:///Users/vjkotra/projects/katana/engine/tests/test_lookup_mapping_api.py)

Add after `test_patch_add_source_value_stacks_into_existing_group` (search for that function name):

```python
def test_patch_add_source_value_case_insensitive_same_destination_is_noop(admin_token: str) -> None:
    """Adding a case-variant of an already-mapped value to the SAME destination
    it's already mapped to is a harmless no-op, not a rejection."""
    project_id, _source_definition_id = _seed_project()

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [{"id": "ACTIVE", "label": "Active"}],
            "source_value_map": {"Active": "ACTIVE"},
            "destination_mappings": [
                {"dest_id": "ACTIVE", "dest_label": "Active", "dest_row": {}, "source_values": ["Active"], "status": "draft"},
            ],
        },
    )
    assert create.status_code == 201, create.text
    lookup_map_id = create.json()["lookup_value_map_id"]

    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"add_source_value": {"dest_id": "ACTIVE", "source_value": "active"}},
    )
    assert patch.status_code == 200, patch.text
    data = patch.json()
    active_groups = [g for g in data["destination_mappings"] if g["dest_id"] == "ACTIVE"]
    assert len(active_groups) == 1
    assert active_groups[0]["source_values"] == ["Active"]
    assert data["unmapped_source_values"] == []


def test_patch_add_source_value_case_insensitive_different_destination_is_rejected(admin_token: str) -> None:
    """Adding a case-variant of an already-mapped value to a DIFFERENT destination
    must be rejected with an error, not silently succeed or fabricate a new group.
    This is the exact incident that motivated this task."""
    project_id, _source_definition_id = _seed_project()

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [
                {"id": "ACTIVE", "label": "Active"},
                {"id": "BLOCKED", "label": "Blocked"},
            ],
            "source_value_map": {"Active": "ACTIVE"},
            "destination_mappings": [
                {"dest_id": "ACTIVE", "dest_label": "Active", "dest_row": {}, "source_values": ["Active"], "status": "draft"},
                {"dest_id": "BLOCKED", "dest_label": "Blocked", "dest_row": {}, "source_values": [], "status": "draft"},
            ],
        },
    )
    assert create.status_code == 201, create.text
    lookup_map_id = create.json()["lookup_value_map_id"]

    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"add_source_value": {"dest_id": "BLOCKED", "source_value": "active"}},
    )
    assert patch.status_code == 409, patch.text
    assert patch.json()["error"]["code"] == "source_value_already_mapped"

    # Confirm nothing changed — no phantom group, no mutation of ACTIVE or BLOCKED.
    get_resp = client.get(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    record = next(m for m in get_resp.json() if m["lookup_value_map_id"] == lookup_map_id)
    assert len(record["destination_mappings"]) == 2
    blocked_group = next(g for g in record["destination_mappings"] if g["dest_id"] == "BLOCKED")
    assert blocked_group["source_values"] == []
    assert record["unmapped_source_values"] == []


def test_patch_add_source_value_unknown_dest_id_routes_to_unmapped(admin_token: str) -> None:
    """A dest_id that doesn't correspond to any real destination_table row or
    existing destination_mappings group must not fabricate a new group — it
    must be tracked in unmapped_source_values instead."""
    project_id, _source_definition_id = _seed_project()

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [{"id": "ACTIVE", "label": "Active"}],
            "source_value_map": {"Active": "ACTIVE"},
            "destination_mappings": [
                {"dest_id": "ACTIVE", "dest_label": "Active", "dest_row": {}, "source_values": ["Active"], "status": "draft"},
            ],
        },
    )
    assert create.status_code == 201, create.text
    lookup_map_id = create.json()["lookup_value_map_id"]

    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"add_source_value": {"dest_id": "does-not-exist", "source_value": "Mystery"}},
    )
    assert patch.status_code == 200, patch.text
    data = patch.json()

    assert len(data["destination_mappings"]) == 1, data["destination_mappings"]
    assert data["destination_mappings"][0]["dest_id"] == "ACTIVE"
    assert data["unmapped_source_values"] == ["Mystery"]
```

Add a fourth test near the fiber/lookup-inputs tests (search the file for an existing `submit_lookup_inputs`-exercising test to place this near, or add near the bottom of the file if none exists — check `grep -n "lookup-inputs\|lookup_inputs" engine/tests/test_lookup_mapping_api.py` and also check `engine/tests/` for a `test_fibers*.py` file, since `submit_lookup_inputs` may be tested there instead of in `test_lookup_mapping_api.py`):

```bash
grep -rln "submit_lookup_inputs\|lookup-inputs" engine/tests/
```

Whichever file already covers the lookup-inputs submission endpoint, add a test there confirming `ai_result.unmatched_source_values` (mock/stub the AI adapter the same way the existing tests in that file do) ends up on the resulting `LookupValueMap.unmapped_source_values` / the fiber-submission response. Follow that file's existing AI-mocking pattern exactly rather than inventing a new one — do not skip this because it requires finding and matching an unfamiliar test setup; the AI-wiring half of this task (Step 5) has no other test coverage otherwise.

---

## Step 8: Frontend — `lookup-api.ts`

**File**: [web/lib/lookup-api.ts](file:///Users/vjkotra/projects/katana/web/lib/lookup-api.ts)

```diff
 export interface LookupValueMapRecord {
   lookupValueMapId: string;
   projectId: string;
   lookupName: string;
   destinationTable: Array<Record<string, unknown>>;
   sourceValueMap: Record<string, string>;
   destinationMappings: DestinationMappingGroup[];
   status: "draft" | "approved";
   unmappedRowCount?: number;
+  unmappedSourceValues: string[];
   createdAt: string;
 }
```

```diff
 function mapLookupValueMapResponse(response: {
   lookup_value_map_id: string;
   project_id: string;
   lookup_name: string;
   destination_table: Array<Record<string, unknown>>;
   source_value_map: Record<string, string>;
   destination_mappings?: Array<Record<string, unknown>>;
   status: "draft" | "approved";
+  unmapped_source_values?: string[];
   created_at: string;
 }): LookupValueMapRecord {
   return {
     lookupValueMapId: response.lookup_value_map_id,
     projectId: response.project_id,
     lookupName: response.lookup_name,
     destinationTable: response.destination_table,
     sourceValueMap: response.source_value_map,
     destinationMappings: (response.destination_mappings || []).map((g: Record<string, unknown>) => ({
       destId: String(g.dest_id ?? g.destId ?? ""),
       destLabel: String(g.dest_label ?? g.destLabel ?? ""),
       destRow: g.dest_row ?? g.destRow,
       sourceValues: Array.isArray(g.source_values ?? g.sourceValues) ? g.source_values ?? g.sourceValues : [],
       status: String(g.status ?? "draft"),
     })),
     status: response.status,
+    unmappedSourceValues: response.unmapped_source_values || [],
     createdAt: response.created_at,
   };
 }
```

---

## Step 9: Frontend — `ReviewGrid.tsx` type + prop threading

**File**: [web/components/projects/ReviewGrid.tsx](file:///Users/vjkotra/projects/katana/web/components/projects/ReviewGrid.tsx)

```diff
 export interface LookupValueGroup {
   lookupName: string;
   referenceTableName: string;
   lookupValueMapId?: string;
   unmappedRowCount?: number;
+  unmappedSourceValues?: string[];
   fiberStatus?: string;
```

Search for `groups={group.destinationMappings ?? []}`:

```diff
                 <LookupMappingTable
                   groups={group.destinationMappings ?? []}
                   unmappedRowCount={group.unmappedRowCount}
+                  unmappedSourceValues={group.unmappedSourceValues}
                   editingEnabled={editingEnabled}
                   onAddSourceValue={(destId, sourceValue) => onAddLookupSourceValue?.(group.lookupName, destId, sourceValue)}
                   onRemoveSourceValue={(destId, sourceValue) => onRemoveLookupSourceValue?.(group.lookupName, destId, sourceValue)}
                 />
```

---

## Step 10: Frontend — `LookupMappingTable.tsx` render the list

**File**: [web/components/projects/LookupMappingTable.tsx](file:///Users/vjkotra/projects/katana/web/components/projects/LookupMappingTable.tsx)

```diff
 interface LookupMappingTableProps {
   groups: DestinationMappingGroup[];
   unmappedRowCount?: number;
+  unmappedSourceValues?: string[];
   editingEnabled?: boolean;
   onAddSourceValue?: (destId: string, sourceValue: string) => void;
   onRemoveSourceValue?: (destId: string, sourceValue: string) => void;
 }
```

```diff
 export function LookupMappingTable({
   groups,
   unmappedRowCount,
+  unmappedSourceValues,
   editingEnabled,
   onAddSourceValue,
   onRemoveSourceValue,
 }: LookupMappingTableProps) {
```

There is exactly one `<table>` in this file — verify with a search before editing, then add the render block right after its closing `</table>`, still inside the outer `<div className="overflow-x-auto">`:

```diff
       </table>
+      {unmappedSourceValues && unmappedSourceValues.length > 0 && (
+        <div className="mt-3 rounded-lg border border-amber-300 bg-amber-50/50 p-3 space-y-1.5">
+          <div className="flex items-center gap-1.5 text-amber-800">
+            <span className="text-sm">⚠️</span>
+            <p className="text-xs font-semibold">Unmapped source values</p>
+          </div>
+          <div className="flex flex-wrap gap-1.5 pl-5">
+            {unmappedSourceValues.map((v) => (
+              <span
+                key={v}
+                className="rounded bg-amber-100 border border-amber-200/60 px-1.5 py-0.5 text-xs font-mono text-amber-800"
+              >
+                {v}
+              </span>
+            ))}
+          </div>
+        </div>
+      )}
     </div>
   );
 }
```

---

## Step 11: Frontend — `review/page.tsx` thread the data through

**File**: [web/app/projects/[id]/feeds/[feedId]/review/page.tsx](file:///Users/vjkotra/projects/katana/web/app/projects/%5Bid%5D/feeds/%5BfeedId%5D/review/page.tsx)

Search for `lookupGroups.push({`:

```diff
         lookupGroups.push({
           lookupName: binding.lookupName,
           referenceTableName: refTable,
           lookupValueMapId: latestMap?.lookupValueMapId,
           unmappedRowCount: latestMap?.unmappedRowCount,
+          unmappedSourceValues: latestMap?.unmappedSourceValues,
           fiberStatus: fiber?.status,
           destinationTable: latestMap?.destinationTable || [],
           destinationMappings,
         });
```

---

## Step 12: Verify

```bash
.venv/bin/python -m pytest engine/tests -q
cd web && npm test -- --run
```

Confirm zero failures on both. The backend suite should grow by exactly 4 tests versus the commit right before this task started (3 in `test_lookup_mapping_api.py` from Step 7, 1 wherever `submit_lookup_inputs`'s existing tests live). If the count is off, figure out why before declaring success — don't assume it's fine.

**Manual verification** (recommended): trigger a real "AI Analyze" / lookup-inputs submission where some source values have no confident destination match, and confirm they show up in the new "Unmapped source values" amber section on the Review page. Separately, try adding a case-variant of an already-mapped value under a different destination via the UI and confirm you get a visible error, not a silent success.
