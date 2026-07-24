# Plan: Task 001go — Fix `removeSourceValue` Patch Key Bug and Wire Add/Remove Source Value Actions Through ReviewGrid

- **Task**: [001go-lookup-review-grid-wiring.md](file:///Users/vjkotra/projects/katana/tasks/001go-lookup-review-grid-wiring.md)

---

## Goal Description

Wire the already-implemented `handleAddSourceByLookup`/`handleRemoveSourceByLookup` handlers from the Review Page through `ReviewGrid.tsx` into `LookupMappingTable.tsx`, and fix a live bug where "remove source value" silently no-ops due to a camelCase/snake_case key mismatch between the frontend and backend.

**Source values only** — no destination-group delete action exists in this task (see [[001gn]] scope note). Review Page only; `feeds/[feedId]/page.tsx` is untouched.

---

## Step-by-Step Build Instructions (Agent Executable)

---

### Step 1: Fix `removeSourceValue` Key Bug in `lookup-api.ts`

**File**: [web/lib/lookup-api.ts](file:///Users/vjkotra/projects/katana/web/lib/lookup-api.ts)

Line 144 currently sends the wrong key, so the backend's PATCH handler (which checks `body.remove_source_value` in `engine/src/migrations_engine/management/lookup_mapping.py`) never sees the action:

```diff
   if (input.sourceValueMap) body.source_value_map = input.sourceValueMap;
   if (input.destinationMappings) body.destination_mappings = input.destinationMappings;
   if (input.addSourceValue) body.add_source_value = input.addSourceValue;
-  if (input.removeSourceValue) body.removeSourceValue = input.removeSourceValue;
+  if (input.removeSourceValue) body.remove_source_value = input.removeSourceValue;
   if (input.moveSourceValue) body.move_source_value = input.moveSourceValue;
```

---

### Step 2: Update `ReviewGridProps` and `<LookupMappingTable>` Invocation in `ReviewGrid.tsx`

**File**: [web/components/projects/ReviewGrid.tsx](file:///Users/vjkotra/projects/katana/web/components/projects/ReviewGrid.tsx)

```diff
 interface ReviewGridProps {
   mappingTables: MappingTableRecord[];
   lookupGroups: LookupValueGroup[];
+  onAddSourceValue?: (lookupName: string, destId: string, sourceValue: string) => void;
+  onRemoveSourceValue?: (lookupName: string, destId: string, sourceValue: string) => void;
```

```diff
                 <LookupMappingTable
                   groups={group.destinationMappings ?? []}
                   unmappedRowCount={group.unmappedRowCount}
                   editingEnabled={editingEnabled}
+                  onAddSourceValue={onAddSourceValue ? (destId, sourceValue) => onAddSourceValue(group.lookupName, destId, sourceValue) : undefined}
+                  onRemoveSourceValue={onRemoveSourceValue ? (destId, sourceValue) => onRemoveSourceValue(group.lookupName, destId, sourceValue) : undefined}
                 />
```

---

### Step 3: Pass Existing Handlers Into `<ReviewGrid>` in `review/page.tsx`

**File**: [web/app/projects/[id]/feeds/[feedId]/review/page.tsx](file:///Users/vjkotra/projects/katana/web/app/projects/%5Bid%5D/feeds/%5BfeedId%5D/review/page.tsx)

`handleAddSourceByLookup` and `handleRemoveSourceByLookup` (around line 235-249) already exist and are correctly implemented — they just aren't passed to `<ReviewGrid>` (around line 699) yet. No new handler functions are needed for this task.

```diff
                       lookupGroups={lookupGroups}
+                      onAddSourceValue={handleAddSourceByLookup}
+                      onRemoveSourceValue={handleRemoveSourceByLookup}
```

---

## Verification Plan

```bash
cd web && npm test -- --run
```

Manual check: on the Review Page, click "+ Add another source value" on a lookup destination group, submit a value, and confirm it persists after a page reload (proves the add path is wired end-to-end). Then click the `×` next to a source value and confirm it disappears and stays gone after reload (proves the bug fix — before this fix, the remove button appeared to work optimistically in local state but reverted on reload since the backend never applied it).
