# Mapping and Lookup UI — AI-Driven Field and Table Display

Task: [tasks/001be-mapping-lookup-ui.md](/Users/vjkotra/projects/katana/tasks/001be-mapping-lookup-ui.md)
Domain: [docs/domain/source-model.md](/Users/vjkotra/projects/katana/docs/domain/source-model.md)
Depends on: 001bd (must be merged first)

**Goal:** Replace the manual lookup-name input on the mapping page and the unguided destination-table
textarea on the lookup page with AI-driven field and reference table display. No regex anywhere.

---

## Current State

**Mapping page** (`web/app/projects/[id]/sources/[sourceId]/mapping/page.tsx`)

- Binding table has three columns: Source field | Destination field | Lookup.
- The Lookup column renders `<input type="text">` — user types a lookup name manually or leaves blank.
- AI proposal sets `lookup_name = null` for all bindings (hardcoded in `propose_mapping`).
- `MappingReviewRecord` has no `lookupTableReferences` field.

**Lookup page** (`web/app/projects/[id]/sources/[sourceId]/lookup/page.tsx`)

- Derives tabs from `snapshot.fieldBindings` where `lookupName != null`.
- `LookupFieldState.lookupName` is editable via an `<input>` in the destination table section.
- Destination table rows are pasted as raw JSON/CSV — user has no guidance on which table to use.
- No `lookupTableReferences` consumed anywhere.

**API lib** (`web/lib/mapping-api.ts`)

- `MappingReviewRecord.fieldBindings: Array<{ sourceField, destinationField, lookupName | null }>`.
- No `lookupTableReferences` field.

---

## Blast Radius

- `web/lib/mapping-api.ts`
- `web/app/projects/[id]/sources/[sourceId]/mapping/page.tsx`
- `web/app/projects/[id]/sources/[sourceId]/lookup/page.tsx`
- `web/app/projects/[id]/sources/[sourceId]/mapping/page.test.tsx`
- `web/app/projects/[id]/sources/[sourceId]/lookup/page.test.tsx`

---

## File Changes

### 1. `web/lib/mapping-api.ts`

Add `lookupTableReferences` to both `MappingReviewRecord` and `MappingSnapshotRecord`:

```typescript
export interface LookupTableReference {
  lookupName: string;
  destinationTableName: string;  // reference table in the DDL, e.g. "status_ref"
}

export interface MappingReviewRecord {
  // ... existing fields ...
  lookupTableReferences: LookupTableReference[];  // [] when not present (pre-001bd snapshots)
}
```

In the response mapper, read `lookup_table_references` from the API payload, defaulting to `[]`:

```typescript
lookupTableReferences: (raw.lookup_table_references ?? []).map((ref: ...) => ({
  lookupName: ref.lookup_name,
  destinationTableName: ref.destination_table_name,
})),
```

Apply the same addition to `MappingSnapshotRecord` used by the lookup page.

---

### 2. `web/app/projects/[id]/sources/[sourceId]/mapping/page.tsx`

**Replace the Lookup `<input>` with a read-only badge:**

```tsx
// Before (editable input):
<input
  value={binding.lookupName ?? ""}
  onChange={...}
  placeholder="optional"
/>

// After (read-only badge or dash):
{binding.lookupName ? (
  <div className="space-y-0.5">
    <span className="inline-flex rounded-full border border-amber-500/20 bg-amber-500/10
                     px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-700">
      {binding.lookupName}
    </span>
    {referenceTableFor(binding.lookupName, snapshot.lookupTableReferences) && (
      <p className="text-[10px] text-slate-400">
        ref: {referenceTableFor(binding.lookupName, snapshot.lookupTableReferences)}
      </p>
    )}
  </div>
) : (
  <span className="text-slate-400">—</span>
)}
```

Helper (pure, no regex):

```typescript
function referenceTableFor(
  lookupName: string,
  refs: LookupTableReference[],
): string | null {
  return refs.find((r) => r.lookupName === lookupName)?.destinationTableName ?? null;
}
```

Remove `lookupName` from the `isDirty` tracking path — it is no longer editable.
The `editedBindings` state can drop the `lookupName` field from the editable shape
(or keep it read-only from the snapshot and never include it in the patch payload).

---

### 3. `web/app/projects/[id]/sources/[sourceId]/lookup/page.tsx`

**Pass `lookupTableReferences` into `LookupFieldState`:**

```typescript
interface LookupFieldState {
  lookupName: string;
  sourceField: string;
  destinationTableName: string | null;  // new: from lookup_table_references
  draftText: string;
  // ... rest unchanged ...
}
```

Populate on load:

```typescript
const refMap = Object.fromEntries(
  (mappingResponse.lookupTableReferences ?? []).map((r) => [r.lookupName, r.destinationTableName])
);

for (const tab of tabs) {
  nextStates[tab.lookupName] = {
    ...existingFields,
    destinationTableName: refMap[tab.lookupName] ?? null,
  };
}
```

**Update tab header to show reference table name:**

```tsx
<button key={tab.lookupName} ...>
  {state?.lookupName ?? tab.lookupName}
  {state?.destinationTableName && (
    <span className="ml-1 text-[10px] text-slate-400">({state.destinationTableName})</span>
  )}
</button>
```

**Update destination table label to name the reference table:**

```tsx
<label htmlFor="lookup-table">
  {activeState?.destinationTableName
    ? `Rows from ${activeState.destinationTableName}`
    : "Draft destination table"}
</label>
<p className="text-xs text-slate-500">
  {activeState?.destinationTableName
    ? `Paste JSON or CSV rows from the ${activeState.destinationTableName} reference table.`
    : "Paste JSON or CSV rows with an id or destination_id column."}
</p>
```

**Remove the editable `lookupName` `<input>`** in the destination table section (lines 652–669
in the current file). The lookup name is fixed from the approved mapping snapshot.

---

## Tests

- [ ] `mapping/page.test.tsx`: Add a test that a snapshot with `lookupTableReferences` renders the
  reference table name in the Lookup column (not an input). Add a test that a snapshot without
  `lookupTableReferences` renders `—` without crashing.
- [ ] `lookup/page.test.tsx`: Add a test that `destinationTableName` appears in the tab header and
  destination table label when `lookupTableReferences` is populated. Add a test for the absent-field
  fallback.

---

## Verification

- Load the mapping page after approving an AI-proposed mapping from 001bd. Lookup bindings show
  amber badge + reference table label. No text input in the Lookup column.
- Load the lookup page. Each tab header shows the reference table name. Destination table label
  names the source table.
- Load with a pre-001bd snapshot (no `lookup_table_references`). Pages render without error;
  reference table label is absent gracefully.

---

## Pitfalls

- Pre-001bd snapshots have no `lookup_table_references` — always default to `[]` in the API mapper,
  never `undefined`.
- `isDirty` tracked `lookupName` edits before; removing the input means removing that dirty source.
  Verify the Save Draft button still activates on destination field changes.
- Lookup page keys `fieldStates` on `lookupName`. The name is now immutable from the snapshot, so
  the key is stable. Do not re-key on re-render.
- No regex anywhere in these files. Field detection and table names come only from API response fields.

---

## Commit

- `feat(001be): show AI-detected lookup fields and reference tables in mapping and lookup UI`
