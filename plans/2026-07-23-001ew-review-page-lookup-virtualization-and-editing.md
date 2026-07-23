---
type: Plan
task: 001ew-review-page-lookup-virtualization-and-editing
date: 2026-07-23
---

# Plan: 001ew — Enable lookup editing and virtualization

**Task:** [001ew-review-page-lookup-virtualization-and-editing](../tasks/001ew-review-page-lookup-virtualization-and-editing.md)  
**Domain:** [governance.md](../docs/domain/governance.md)

---

## Current State

- `web/components/projects/ReviewGrid.tsx` loops through `lookupGroups` (built from `lookupMaps`) and renders an HTML `<table>` with all source values at once.
- The destination row is completely read-only.
- If `lookupGroups` has thousands of pairs, rendering the DOM tree freezes the browser.
- `web/lib/lookup-api.ts` lacks an endpoint to patch an existing `LookupValueMapRecord` with user edits.
- `engine/src/migrations_engine/routes/lookup.py` has `POST` routes for creation but no `PATCH` route for partial updates.

---

## File Changes

### Step 1 — Backend API: Add `PATCH` route for LookupValueMap

**Path:** `engine/src/migrations_engine/routes/lookup.py`
**Path:** `engine/src/migrations_engine/mapping/lookup_service.py` (or equivalent service layer)

- Implement a new `PATCH /projects/{project_id}/lookup-maps/{lookup_value_map_id}` endpoint.
- Accept a partial update request model (e.g., `LookupValueMapPatchRequest`) containing `sourceValueMap: dict[str, str]`.
- The service layer must fetch the existing record and update its `source_value_map`.
- **Crucial Rule:** The update operation must clear/invalidate any existing sign-off state for this lookup map to enforce re-review of the manual change.

### Step 2 — Frontend API: Add `patchLookupValueMap`

**Path:** `web/lib/lookup-api.ts`

- Export a new function: `async function patchLookupValueMap(token, projectId, lookupValueMapId, sourceValueMap)` pointing to the new `PATCH` endpoint.

### Step 3 — Frontend UI: Extract `LookupMappingTable`

**Path:** `web/components/projects/LookupMappingTable.tsx` (New Component)

- Extract the `<table className="w-full border-collapse...">` rendering logic for a single `LookupValueGroup` from `ReviewGrid.tsx` into this new component.
- **Props:** Accepts `group: LookupValueGroup`, `editingEnabled`, `onEditLookup` callback, and sign-off callbacks if applicable.
- **Progressive Loading / Virtualization:**
  - Implement an `IntersectionObserver`-based progressive loader inside the component.
  - Maintain a local React state `visibleCount` starting at `50`.
  - Slice the data array `group.pairs.slice(0, visibleCount)` to render.
  - Place a Sentinel element (`<tr ref={observerRef}>`) at the end of the list to bump `visibleCount` by 50 when intersected.
- **Editing UX:**
  - When `editingEnabled` is true, render a `<select>` or custom combobox in the "Destination Row" cell instead of static text.
  - The dropdown options must be mapped strictly from `group.destinationTable` (the predefined reference rows).
  - The selected value represents the `destinationRow.id`.
  - Selecting a new value fires the `onEditLookup` callback with the updated key-value pair.

### Step 4 — Frontend UI: Update `ReviewGrid` and `ReviewPage`

**Path:** `web/components/projects/ReviewGrid.tsx`
- Replace the inline lookup table rendering block with instances of `<LookupMappingTable>`.
- Expose an `onEditLookup(lookupValueMapId: string, updatedSourceValueMap: Record<string, string>)` prop to pass manual edits up the component tree.

**Path:** `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`
- Implement a `handleEditLookup` function.
- Calls `patchLookupValueMap` API to persist the edit.
- On success, updates the local React state (or triggers a full data reload) and visually updates the sign-off chips to reflect the invalidated state.

---

## Blast Radius

| Layer | Impact |
|-------|--------|
| `routes/lookup.py` | Add `PATCH` endpoint |
| `lookup-api.ts` | Add `patchLookupValueMap` API client function |
| `ReviewGrid.tsx` | Reduced in size; delegates table rendering |
| `LookupMappingTable.tsx` | New component housing the IntersectionObserver and edit state |
| `ReviewPage` | New state handler for saving manual edits |

---

## Tests

1. Add backend tests in `engine/tests/test_lookup_routes.py` (or equivalent file) to ensure the `PATCH` route updates the DB and clears sign-off status properly.
2. Ensure existing UI tests pass (`web/app/projects/[id]/feeds/[feedId]/review/page.test.tsx`).
3. Add unit tests for `LookupMappingTable.tsx` to verify progressive loading triggers correctly and edit callbacks fire with expected data.
