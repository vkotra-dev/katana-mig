Task: tasks/002h0-ui-slice-ddl-collapse-and-lookup-lock.md
Domain: docs/domain/ui.md

## Current State

- `web/app/projects/[id]/feeds/[feedId]/page.tsx` (lines 708-728): Source DDL is displayed as a static `<pre>` block after the "Analyze with AI" button. It's always visible when `sourceDDL` is set.
- `web/components/projects/ReviewGrid.tsx` (lines 585-610): Table binding editability uses `rowEditable = editingEnabled && !isSignedByEither` with OR logic (`centralTeam.signed || projectStakeholder.signed`) at line 589.
- `web/components/projects/LookupMappingTable.tsx` (lines 93-111): Lookup source values are displayed in a `<input readOnly>` field with a "×" remove button gated only by `editingEnabled` (line 101). No per-lookup sign-off check.
- `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` (line 586): `editingEnabled = signOffStatus?.currentBallRole === role && isAnyDraft`. This is a ball-holder flag, not a per-item lock.
- `web/components/projects/ReviewGrid.tsx` passes `editingEnabled` to `LookupMappingTable` at line 776 without any per-lookup lock data.
- `web/components/projects/ReviewGrid.tsx` (lines 345-411): `renderLookupSignOffChips` accesses `signOffStatus.lookups[lookupValueMapId].centralTeam` / `.projectStakeholder` — the same `signOffStatus` is already available as a prop (line 52).
- `web/components/projects/ReviewGrid.tsx` (line 589): Table bindings use OR logic to decide if a row is locked (`isSignedByEither = centralTeam.signed || projectStakeholder.signed`). Lookup lock should follow the same convention.

## Objective

1. **Source DDL expand/collapse**: Add a toggle and `useState` for expanded state. Default to collapsed (false). Show "Show Source DDL" button when collapsed, reveal `<pre>` when expanded.
2. **Move Source DDL**: Move the Source DDL block from between the "Analyze with AI" button and the upload section to the very end of the Slice section's `<div className="space-y-4">`.
3. **Lock lookup mappings**: Derive `isLocked` once per lookup group from `signOffStatus.lookups[lookupValueMapId]` using OR logic (consistent with table binding lock at line 589: lock when either `centralTeam.signed` OR `projectStakeholder.signed`). Pass `locked` as a single boolean prop to `LookupMappingTable`.

## Out of Scope

- Backend API changes
- Changes to the sign-off workflow
- Table mapping expand/collapse (already exists)
- Per-source-value locking within a lookup — the entire lookup group is locked if the lookup is signed

## Blast Radius

| File | Action | What changes |
|------|--------|-------------|
| `web/app/projects/[id]/feeds/[feedId]/page.tsx` | modify | Add `sourceDdlExpanded` state, toggle UI (show/hide button), move Source DDL block to bottom of Slice section |
| `web/components/projects/ReviewGrid.tsx` | modify | Derive `isLocked` per lookup group from `signOffStatus.lookups`, pass `locked` as single boolean prop to `LookupMappingTable` |
| `web/components/projects/LookupMappingTable.tsx` | modify | Add `locked?: boolean` to `LookupMappingTableProps`; gate remove "×" and "add" buttons with `&& !locked` |

No changes to `lookup-api.ts` or any backend files.

## File Changes

### `web/app/projects/[id]/feeds/[feedId]/page.tsx`

**Add state (near line 62):**
```ts
const [sourceDdlExpanded, setSourceDdlExpanded] = useState(false);
```

**Move Source DDL block** (currently at lines 709-728) to after the upload section (after line 730, before the Slice panel's closing `</div>`). Replace the static block with:
```tsx
{sourceDDL && (
  <div className="pt-4 border-t border-slate-100 space-y-2">
    <div className="flex items-center justify-between mb-1">
      <h4 className="text-sm font-semibold text-slate-700">Source DDL</h4>
      <button type="button" onClick={() => { navigator.clipboard.writeText(sourceDDL); setNotice("DDL copied to clipboard."); }} className="text-xs text-primary hover:text-primary-hover font-medium">
        Copy to clipboard
      </button>
    </div>
    {!sourceDdlExpanded ? (
      <button type="button" onClick={() => setSourceDdlExpanded(true)} className="w-full text-left text-xs text-slate-500 hover:text-slate-700 font-medium py-1">
        Show Source DDL
      </button>
    ) : (
      <div className="space-y-2">
        <pre className="text-xs bg-slate-950 text-slate-100 rounded-lg p-3 font-mono whitespace-pre-wrap max-h-64 overflow-auto">
          {sourceDDL}
        </pre>
        <button type="button" onClick={() => setSourceDdlExpanded(false)} className="text-xs text-slate-500 hover:text-slate-700 font-medium">
          Hide Source DDL
        </button>
      </div>
    )}
  </div>
)}
```

### `web/components/projects/ReviewGrid.tsx`

**In the LookupMappingTable render (around line 772), replace the single prop render with:**
```tsx
{(() => {
  const lookupStatus = signOffStatus?.lookups?.[group.lookupValueMapId];
  const isLocked = lookupStatus && (lookupStatus.centralTeam?.signed || lookupStatus.projectStakeholder?.signed);
  return (
    <LookupMappingTable
      locked={isLocked}
      groups={group.destinationMappings ?? []}
      unmappedRowCount={group.unmappedRowCount}
      unmappedSourceValues={group.unmappedSourceValues}
      editingEnabled={editingEnabled}
      onAddSourceValue={(destId, sourceValue) => onAddLookupSourceValue?.(group.lookupName, destId, sourceValue)}
      onRemoveSourceValue={(destId, sourceValue) => onRemoveLookupSourceValue?.(group.lookupName, destId, sourceValue)}
    />
  );
})()}
```

### `web/components/projects/LookupMappingTable.tsx`

**Add prop:**
```ts
interface LookupMappingTableProps {
  // existing props ...
  locked?: boolean;
  // ...
}
```

**Gate remove button (line ~101):**
```tsx
{!locked && editingEnabled && onRemoveSourceValue && group.destId && (
```

**Gate add button (line ~113):**
```tsx
{!locked && editingEnabled && onAddSourceValue && group.destId && (
```

## Verification

Before calling this done:

1. `cd web && npx tsc --noEmit` — zero new TS errors (existing errors in `codegen/page.test.tsx` are pre-existing and unrelated).
2. `cd web && npm test -- --run` — all existing tests pass (specifically `LookupMappingTable.test.tsx` and `ReviewGrid.test.tsx`).
3. Manual: Open a feed page → run "Analyze with AI" → verify Source DDL appears collapsed with "Show Source DDL" button → click to expand → verify `<pre>` renders with scroll → click "Hide" → verify it collapses again.
4. Manual: On the review page, sign off one side of a lookup mapping → verify the lookup's remove "×" buttons and "+ Add another source value" button disappear → verify the other side can still edit if they hold the ball.

## Implementation Plan

### 1. Feed page: Source DDL collapsible + reorder

In `web/app/projects/[id]/feeds/[feedId]/page.tsx`:

1. Add state: `const [sourceDdlExpanded, setSourceDdlExpanded] = useState(false);`
2. Move the Source DDL block from lines 709-728 to after the upload section (after line 730, before the closing `</div>` of the Slice panel's `</div>`).
3. When collapsed: show a button labelled "Show Source DDL". On click, call `setSourceDdlExpanded(true)`.
4. When expanded: show the `<pre>` DDL block + copy-to-clipboard button + a "Hide Source DDL" button.

### 2. ReviewGrid: derive lock and pass as single prop

In `web/components/projects/ReviewGrid.tsx`:

1. `signOffStatus` is already a prop (line 52). Derive the lock for each lookup group inline, where `LookupMappingTable` is rendered (line 772).
2. For each lookup group, compute `isLocked`:
   ```ts
   const lookupStatus = signOffStatus?.lookups?.[group.lookupValueMapId];
   const isLocked = lookupStatus && (lookupStatus.centralTeam?.signed || lookupStatus.projectStakeholder?.signed);
   ```
3. Pass a single new prop to `LookupMappingTable`: `locked={isLocked}` (boolean).

### 3. LookupMappingTable: accept locked prop

In `web/components/projects/LookupMappingTable.tsx`:

1. Add `locked?: boolean` to `LookupMappingTableProps`.
2. In the source values list, where the remove "×" button is gated by `editingEnabled` (line 101), add `&& !locked` to the condition.
3. Where the "Add another source value" button is gated by `editingEnabled` (line 113), add `&& !locked` to the condition.
4. When `locked` is true, the locked lookups display a small "locked" label next to the lookup header in `ReviewGrid` (rendered alongside `renderLookupSignOffChips`).

## Pitfalls

1. **Lock uses OR logic** — consistent with the existing table binding lock (`isSignedByEither` at ReviewGrid.tsx line 589). The lock engages as soon as the first reviewer signs.
2. **No type changes needed** — `locked` is a new prop on `LookupMappingTableProps`, not on `DestinationMappingGroup`. The `lookup-api.ts` file is untouched.
3. `signOffStatus.lookups` is keyed by `lookupValueMapId` which may be `undefined` for some groups — guard with optional chaining.

## Tests

- Unit: `ReviewGrid` with `signOffStatus.lookups[mapId].centralTeam.signed === true` (projectStakeholder false) — verify `isLocked === true` (OR logic).
- Unit: `ReviewGrid` with both `centralTeam` and `projectStakeholder` unsigned — verify `isLocked === false`.
- Unit: Feed page Source DDL starts collapsed (`sourceDdlExpanded` defaults to false).
- Manual: Sign off one side of a lookup on the review page — verify lookup source values become non-editable (remove buttons and "add" button disappear).
- Manual: Verify Source DDL starts collapsed in feed page Slice section and toggles correctly.

## Commit

```
fix(ui): add Source DDL expand/collapse, move to bottom, and lock lookup mappings when either reviewer signs

- Add collapsible Source DDL in Slice section of feed page (collapsed by default)
- Move Source DDL below upload section in Slice panel
- Add locked prop to LookupMappingTable; gate edit controls when lookup is signed off (OR logic)
- Derive isLocked from signOffStatus.lookups in ReviewGrid, matching table binding lock pattern
```
