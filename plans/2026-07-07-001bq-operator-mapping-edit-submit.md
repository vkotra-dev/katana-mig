# Plan: 001bq — Operator Mapping Edit and Submit for Review

- **Task Link:** [001bq-operator-mapping-edit-submit.md](file:///Users/vjkotra/projects/katana/tasks/001bq-operator-mapping-edit-submit.md)
- **Domain Link:** [ui.md](file:///Users/vjkotra/projects/katana/docs/domain/ui.md)

## Current State

The feed workspace renders AI-proposed field bindings as a read-only accordion. There is no way to:
1. Change a wrong destination field assignment (e.g. fix `CUST_ID → customer_name` → `CUST_ID → customer_id`)
2. Signal to the business user that the mapping is ready for review

The `patchMappingSnapshot` backend endpoint (`PATCH /projects/{id}/sources/{feedId}/mapping`) already accepts a full field-bindings replacement and exists in `web/lib/mapping-api.ts`, but has no UI in the feed workspace. 

`destinationFields` (the valid destination column list from DDL) is included in `MappingReviewRecord` but not in `MappingSnapshotRecord` — the type used by the feed workspace after 001bo. It is stored in the `MappingSnapshot.destination_fields` DB column but stripped by the list route mapper.

## Objective

1. Add `destinationFields` to `MappingSnapshotRecord` (frontend type + backend route serialization) so the feed workspace can populate destination field dropdowns
2. Make each binding row's destination field editable — an inline `<select>` showing valid destination columns for that table
3. Add a per-table "Save" button that calls `patchMappingSnapshot` with the full updated binding list
4. Add a "Submit for review" button (appears once any mapping is saved) that changes the page state to indicate review is in progress and fires a stakeholder notification

## Out of Scope

- Editing on the review page (stays read-only)
- Adding or removing binding rows (only correcting destination field for existing AI-proposed bindings)
- Per-table approve/reject (separate from 001bp)
- Backend notification infrastructure changes (if a lightweight notification path doesn't exist, "Submit for review" can show a confirmation message as a first step)

## Blast Radius

- `web/lib/mapping-api.ts` — add `destinationFields` to `MappingSnapshotRaw` + `MappingSnapshotRecord`; add `submitForReview` helper if needed
- `engine/src/migrations_engine/routes/mapping_snapshots.py` — include `destination_fields` in the list-snapshots response serialization
- `web/app/projects/[id]/feeds/[feedId]/page.tsx` — inline `<select>` per binding row, per-table Save button, Submit for review button

## File Changes

### `engine/src/migrations_engine/routes/mapping_snapshots.py`

In the route that serializes snapshots for `GET /mapping-snapshots`, add `destination_fields` to the per-snapshot dict:

```python
{
    ...existing fields...,
    "destination_fields": snapshot.destination_fields or [],
}
```

### `web/lib/mapping-api.ts`

Extend `MappingSnapshotRaw`:
```ts
type MappingSnapshotRaw = {
  ...
  destination_fields?: string[];
};
```

Extend `MappingSnapshotRecord`:
```ts
export interface MappingSnapshotRecord {
  ...
  destinationFields: string[];
}
```

Update `mapMappingSnapshotResponse` to include `destinationFields: response.destination_fields ?? []`.

Remove `MappingReviewRecord extends MappingSnapshotRecord` duplication of `destinationFields` (it will now be on the base type).

### `web/app/projects/[id]/feeds/[feedId]/page.tsx`

**New state per table:** `bindingEdits: Record<string, MappingFieldBindingRecord[]>` — keyed by `destinationObjectName`, starts empty (no edits). When the user changes a dropdown, update the binding in this map. When Save is clicked, send the edited bindings (falling back to the original snapshot bindings for unchanged rows).

**Per binding row:** Replace the read-only destination field text with:
```tsx
{snapshot.status === "draft" ? (
  <select
    value={editedBinding.destinationField}
    onChange={(e) => updateBindingEdit(tblName, idx, e.target.value)}
    className="rounded border border-slate-200 bg-white px-1 py-0.5 font-mono text-xs"
  >
    {snapshot.destinationFields.map(col => (
      <option key={col} value={col}>{col}</option>
    ))}
  </select>
) : (
  <span className="font-mono text-xs">{binding.destinationField}</span>
)}
```

**Per-table Save button** (only when status is "draft" and edits exist for that table):
```tsx
<button onClick={() => handleSaveBindings(tblName)} ...>Save</button>
```

`handleSaveBindings(tblName)`:
- Takes the edited bindings for the table (falling back to original for unchanged rows)
- Calls `patchMappingSnapshot(token, projectId, feedId, updatedBindings)`
- On success, reloads all snapshots and clears the edit state for that table

**Submit for review button** — shown in the field mappings section header when at least one snapshot is draft:
```tsx
{allMappingSnapshots.some(s => s.status === "draft") && (
  <button onClick={handleSubmitForReview} ...>Submit for review</button>
)}
```

`handleSubmitForReview`: Show a notice `"Mapping submitted for business review."`. In a future task this fires a stakeholder notification via a new endpoint; for now the draft status already makes it visible on the review page.

## Tests

No automated tests for the feed workspace page. Manual verification only.

## Verification

1. Feed workspace shows field mapping accordion for a draft snapshot
2. Expanding a table accordion shows destination fields as editable `<select>` dropdowns
3. Changing a dropdown and clicking Save calls `patchMappingSnapshot` — the field updates persist after reload
4. "Submit for review" button appears, clicking it shows a notice
5. Approved snapshots show destination fields as read-only text (select hidden)
6. TypeScript compiles with no new errors

## Pitfalls

- `patchMappingSnapshot` sends a FULL replacement — must include ALL bindings for the table, not just changed ones. Merge edited rows with originals before sending.
- `destination_fields` on the `MappingSnapshot` DB model may be `None` for older snapshots that pre-date the column — always default to `[]` and gracefully hide the select if empty.
- The select renders inside the accordion's `<table>` — keep the column widths stable so the layout doesn't shift when in edit mode.

## Commit

- `feat(001bq): add operator field-binding edit and submit-for-review to feed workspace`
