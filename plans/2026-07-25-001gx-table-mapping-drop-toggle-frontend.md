Task: tasks/001gx-table-mapping-drop-toggle-frontend.md
Domain: docs/domain/ui.md

## Current State

- **Gate: do not start this plan until 001gw is complete** — `MappingFieldBindingResponse.dropped` must exist on the `/mapping` GET/PATCH response before this plan's Step 2 has anything real to read.
- `ReviewGrid.tsx:526-535` renders a hard-delete `×` button, gated entirely on `editingEnabled` (not rendered at all otherwise): `onClick={() => onRemoveSourceField?.(table.destinationTableName, group.sourceField)}`.
- `review/page.tsx:360-386`'s `handleRemoveSourceField` filters the target source field's bindings *out* of the array, then PATCHes the reduced list — this is the hard-delete behavior 001gw's backend contract requires replacing with "send the full list, one flag flipped."
- `MappingTableRecord.bindings` (`ReviewGrid.tsx:11-16`) has no `dropped` field yet; neither does `MappingFieldBindingRecord` (`mapping-api.ts:3-12`) or `MappingSnapshotRaw`'s `field_bindings` shape (same file, `:59-68`).
- The `groups` array (`ReviewGrid.tsx:458-467`, built inline inside the render, grouping `table.bindings` by `sourceField`) has no per-group `dropped` state — needs one computed as `group.bindings.every(b => b.dropped)`.
- `AutocompleteInput` (`ReviewGrid.tsx:74-207`), used for the destination-field picker in this same table, has its dropdown `<ul>` clipped by the table wrapper's `overflow-x-auto` ancestor (`ReviewGrid.tsx:511`) — a CSS spec quirk (`overflow-x: auto` forces `overflow-y` to also clip on the same element; `z-[100]` on the dropdown cannot escape a clipping ancestor, which is why it doesn't help today). Confirmed choice: fix via flip-upward positioning, not a portal.
- Existing tests in `ReviewGrid.test.tsx` (search `"shows a source-field delete icon even for a single-destination source field"` and `"does not show either delete icon when editingEnabled is false"`) assert the *current* hard-delete, editingEnabled-gated-visibility behavior — both must be updated, not left alongside new tests, or the suite will contain contradictory assertions.
- **Scope note**: this is the table/field mapping grid (`ReviewGrid.tsx`), not `LookupMappingTable.tsx` (lookup value mappings, already covered by tasks 001gq-001gu). Do not touch `LookupMappingTable.tsx`.

## Objective

Replace the hard-delete `×` button with a checkbox/tick toggle (always visible, read-only when not editable) that flips the `dropped` flag 001gw's backend now understands — the row stays in the table with the source field name struck through when dropped, and the PATCH always sends the full bindings list so sign-offs survive. Also fix `AutocompleteInput`'s dropdown clipping (flip-upward near the viewport bottom) — an unrelated bug folded into this task per explicit product request, since it's the same component family.

## Out of Scope

- Do NOT touch `LookupMappingTable.tsx` or any lookup-value-mapping frontend code.
- Do NOT change the destination-mapping-level `×` (`"Remove this destination mapping"`, a *different* control from the source-field toggle — it removes one binding within a 1-to-N group, stays `editingEnabled`-gated, unaffected by this task).
- Do NOT implement a React Portal for the dropdown fix — flip-upward was the explicit, confirmed choice; a portal is a larger change not authorized here.
- Do NOT add any client-side "is this value already mapped/duplicate" validation logic anywhere in this task — not applicable to table mapping's drop toggle (that constraint was specific to lookup value mapping's `add_source_value`, task 001gu), but flagging so it's not accidentally copied over by pattern-matching against that task.

## Blast Radius

| File | Action | What changes |
|------|--------|-------------|
| `web/lib/mapping-api.ts` | modify | `dropped` field on request/response types and mapping functions |
| `web/components/projects/ReviewGrid.tsx` | modify | `MappingTableRecord.bindings[].dropped`; prop rename `onRemoveSourceField`→`onToggleSourceField`; computed `group.dropped`; toggle button replaces `×`; strikethrough; `AutocompleteInput` flip-upward fix |
| `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` | modify | `handleRemoveSourceField`→`handleToggleSourceField` (full-list semantics); `mappingTablesMap` construction carries `dropped`; prop passed to `<ReviewGrid>` renamed |
| `web/components/projects/__tests__/ReviewGrid.test.tsx` | modify | 2 existing tests updated (old behavior wrong now), 1 new test added |
| `docs/domain/ui.md` | modify | document the toggle control once this task is complete, per invariant I22 |

## File Changes

### `web/lib/mapping-api.ts`

```diff
 export interface MappingFieldBindingRecord {
   sourceField: string;
   destinationField: string;
   lookupName: string | null;
   bindingType?: "direct" | "detail_fk" | "lookup_fk";
   referenceTableName?: string | null;
   destinationTableName?: string | null;
   destinationDataType?: string | null;
   nullable?: boolean | null;
+  dropped?: boolean;
 }
```

```diff
   field_bindings: Array<{
     source_field: string;
     destination_field: string;
     lookup_name: string | null;
     binding_type?: string | null;
     reference_table_name?: string | null;
     destination_table_name?: string | null;
     destination_data_type?: string | null;
     nullable?: boolean | null;
+    dropped?: boolean;
   }>;
```

(Inside `MappingSnapshotRaw`.)

```diff
     fieldBindings: response.field_bindings.map((binding) => ({
       sourceField: binding.source_field,
       destinationField: binding.destination_field,
       lookupName: binding.lookup_name,
       bindingType: binding.binding_type as any,
       referenceTableName: binding.reference_table_name,
       destinationTableName: binding.destination_table_name,
       destinationDataType: binding.destination_data_type,
       nullable: binding.nullable,
+      dropped: binding.dropped ?? false,
     })),
```

(Inside `mapMappingSnapshotResponse`.)

```diff
 export async function patchMappingSnapshot(
   token: string,
   projectId: string,
   sourceDefinitionId: string,
-  fieldBindings: Array<{ sourceField: string; destinationField: string; lookupName: string | null }>,
+  fieldBindings: Array<{ sourceField: string; destinationField: string; lookupName: string | null; dropped?: boolean }>,
   destinationObjectName?: string,
 ): Promise<MappingReviewRecord> {
   const query = destinationObjectName ? `?destination_object_name=${encodeURIComponent(destinationObjectName)}` : "";
   const response = await requestMappingJson<MappingReviewRaw>(
     `/projects/${projectId}/sources/${sourceDefinitionId}/mapping${query}`,
     {
       method: "PATCH",
       token,
       body: JSON.stringify({
         field_bindings: fieldBindings.map((binding) => ({
           source_field: binding.sourceField,
           destination_field: binding.destinationField,
           lookup_name: binding.lookupName,
+          dropped: binding.dropped ?? false,
         })),
       }),
     },
   );
   return mapMappingReviewResponse(response);
 }
```

`dropped` is optional on the input type so the existing call in `web/lib/mapping-api.test.ts:193-195` (which doesn't pass it) keeps compiling and implicitly sends `dropped: false` — do not edit that test.

### `web/components/projects/ReviewGrid.tsx`

**Types** — search for `export interface MappingTableRecord`:

```diff
   bindings: Array<{
     sourceField: string;
     destinationField: string;
     bindingType: "direct" | "detail_fk" | "lookup_fk";
     referenceTableName?: string | null;
+    dropped?: boolean;
   }>;
```

**Prop rename** — search for `onRemoveSourceField?:` in `ReviewGridProps`:

```diff
-  onRemoveSourceField?: (tableName: string, sourceField: string) => void;
+  onToggleSourceField?: (tableName: string, sourceField: string, dropped: boolean) => void;
```

And in the destructured props (search `onRemoveSourceField,` on its own line):

```diff
-  onRemoveSourceField,
+  onToggleSourceField,
```

**Computed `dropped` per group** — search for `const groups: Array<{ sourceField: string; bindings: BindingEntry[] }> = [];`:

```diff
-              const groups: Array<{ sourceField: string; bindings: BindingEntry[] }> = [];
+              const groups: Array<{ sourceField: string; bindings: BindingEntry[]; dropped: boolean }> = [];
               const groupIndexBySourceField: Record<string, number> = {};
               table.bindings.forEach((b) => {
                 if (groupIndexBySourceField[b.sourceField] === undefined) {
                   groupIndexBySourceField[b.sourceField] = groups.length;
-                  groups.push({ sourceField: b.sourceField, bindings: [] });
+                  groups.push({ sourceField: b.sourceField, bindings: [], dropped: false });
                 }
                 groups[groupIndexBySourceField[b.sourceField]].bindings.push(b);
               });
+              groups.forEach((g) => {
+                g.dropped = g.bindings.length > 0 && g.bindings.every((b) => b.dropped === true);
+              });
```

**The toggle button** — search for `title="Drop this source field from migration"` to find the exact block (the `×` button plus its `{editingEnabled && (...)}` wrapper and the source-field `<span>` immediately after):

```diff
                                 <td className="py-2.5 align-top">
                                   <div className="flex items-center gap-1.5">
-                                    {editingEnabled && (
-                                      <button
-                                        type="button"
-                                        onClick={() => onRemoveSourceField?.(table.destinationTableName, group.sourceField)}
-                                        title="Drop this source field from migration"
-                                        className="text-slate-400 hover:text-red-600 focus:outline-none text-xs font-bold leading-none"
-                                      >
-                                        ×
-                                      </button>
-                                    )}
-                                    <span className="font-mono text-slate-700">{group.sourceField}</span>
+                                    <button
+                                      type="button"
+                                      disabled={!editingEnabled}
+                                      onClick={() => onToggleSourceField?.(table.destinationTableName, group.sourceField, !group.dropped)}
+                                      title={group.dropped ? "Excluded from migration — click to include" : "Included in migration — click to exclude"}
+                                      aria-pressed={!group.dropped}
+                                      className={`flex-shrink-0 inline-flex items-center justify-center h-4 w-4 rounded border transition-colors focus:outline-none ${
+                                        group.dropped
+                                          ? "border-slate-300 bg-white"
+                                          : "border-emerald-500 bg-emerald-500"
+                                      } ${editingEnabled ? "cursor-pointer hover:border-emerald-400" : "cursor-default"}`}
+                                    >
+                                      {!group.dropped && (
+                                        <svg className="h-3 w-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
+                                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
+                                        </svg>
+                                      )}
+                                    </button>
+                                    <span className={`font-mono ${group.dropped ? "line-through text-slate-400" : "text-slate-700"}`}>{group.sourceField}</span>
                                     {group.bindings.length > 1 && (
```

The icon is now always rendered (no `editingEnabled` visibility gate) — `disabled={!editingEnabled}` handles interactivity only, per the design decision.

**`AutocompleteInput` flip-upward fix** — search for `function AutocompleteInput({`:

```diff
 function AutocompleteInput({
   value,
   options,
   onChange,
   className = "",
   placeholder = "",
 }: AutocompleteInputProps) {
   const [isOpen, setIsOpen] = useState(false);
   const [query, setQuery] = useState(value);
   const [highlightedIndex, setHighlightedIndex] = useState(-1);
+  const [openUpward, setOpenUpward] = useState(false);
   const containerRef = useRef<HTMLDivElement>(null);
```

Add after the click-outside `useEffect` (search for `document.removeEventListener("mousedown", handleClickOutside);`, insert after its closing `}, []);`):

```diff
+  const openDropdown = () => {
+    if (containerRef.current) {
+      const rect = containerRef.current.getBoundingClientRect();
+      const estimatedDropdownHeight = 200; // matches max-h-48 (~192px) + margin
+      setOpenUpward(rect.bottom + estimatedDropdownHeight > window.innerHeight);
+    }
+    setIsOpen(true);
+  };
+
   const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
     if (e.key === "ArrowDown") {
       e.preventDefault();
-      setIsOpen(true);
+      openDropdown();
       setHighlightedIndex((prev) =>
         prev < filteredOptions.length - 1 ? prev + 1 : 0
       );
     } else if (e.key === "ArrowUp") {
       e.preventDefault();
-      setIsOpen(true);
+      openDropdown();
       setHighlightedIndex((prev) =>
         prev > 0 ? prev - 1 : filteredOptions.length - 1
       );
```

```diff
         <input
           type="text"
           value={query}
           onChange={(e) => {
             setQuery(e.target.value);
-            setIsOpen(true);
+            openDropdown();
             setHighlightedIndex(-1);
           }}
-          onFocus={() => setIsOpen(true)}
+          onFocus={openDropdown}
           onBlur={() => {
             onChange(query);
             setIsOpen(false);
           }}
```

```diff
         <button
           type="button"
-          onClick={() => setIsOpen((prev) => !prev)}
+          onClick={() => (isOpen ? setIsOpen(false) : openDropdown())}
           className="absolute right-0 top-1/2 -translate-y-1/2 px-2.5 py-1 text-slate-400 hover:text-slate-600 focus:outline-none"
         >
```

```diff
       {isOpen && filteredOptions.length > 0 && (
-        <ul className="absolute left-0 right-0 z-[100] mt-1 max-h-48 overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 text-xs shadow-lg ring-1 ring-black/5 focus:outline-none font-mono">
+        <ul className={`absolute left-0 right-0 z-[100] max-h-48 overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 text-xs shadow-lg ring-1 ring-black/5 focus:outline-none font-mono ${openUpward ? "bottom-full mb-1" : "mt-1"}`}>
```

Do not change the filtering logic, keyboard navigation beyond what's shown, or the click-outside handler.

### `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`

Search for `const handleRemoveSourceField = async`:

```diff
-  const handleRemoveSourceField = async (tableName: string, sourceField: string) => {
+  const handleToggleSourceField = async (tableName: string, sourceField: string, dropped: boolean) => {
     const targetSnapshot = mappingSnapshots.find((s) => s.destinationObjectName === tableName);
     if (!targetSnapshot) return;
 
-    // Optimistically remove every binding for this source field from local state
+    // Optimistically toggle every binding for this source field in local state
     setMappingSnapshots((prev) =>
       prev.map((snapshot) => {
         if (snapshot.destinationObjectName !== tableName) return snapshot;
         return {
           ...snapshot,
-          fieldBindings: snapshot.fieldBindings.filter((b) => b.sourceField !== sourceField),
+          fieldBindings: snapshot.fieldBindings.map((b) =>
+            b.sourceField === sourceField ? { ...b, dropped } : b
+          ),
         };
       })
     );
 
     if (!session) return;
     try {
-      const updatedBindings = targetSnapshot.fieldBindings
-        .filter((b) => b.sourceField !== sourceField)
-        .map((b) => ({ sourceField: b.sourceField, destinationField: b.destinationField, lookupName: b.lookupName }));
+      const updatedBindings = targetSnapshot.fieldBindings.map((b) => ({
+        sourceField: b.sourceField,
+        destinationField: b.destinationField,
+        lookupName: b.lookupName,
+        dropped: b.sourceField === sourceField ? dropped : b.dropped,
+      }));
       await patchMappingSnapshot(session.accessToken, projectId, feedId, updatedBindings, tableName);
       const updated = await getSignOffStatus(session.accessToken, projectId, feedId);
       setSignOffStatus(updated);
     } catch (err) {
-      setError(err instanceof Error ? err.message : "Failed to remove source field mapping.");
+      setError(err instanceof Error ? err.message : "Failed to update source field mapping.");
     }
   };
```

This is the critical behavior change: `updatedBindings` is the *full* current list (mapped, not filtered), with only the target source field's `dropped` flag changed. This is what makes 001gw's sign-off-preservation logic work.

Search for `mappingTablesMap[tblName].bindings.push({`:

```diff
       mappingTablesMap[tblName].bindings.push({
         sourceField: binding.sourceField,
         destinationField: binding.destinationField,
         bindingType: binding.bindingType || "direct",
         referenceTableName: binding.referenceTableName || null,
+        dropped: binding.dropped ?? false,
       });
```

Search for `onRemoveSourceField={handleRemoveSourceField}`:

```diff
-                      onRemoveSourceField={handleRemoveSourceField}
+                      onToggleSourceField={handleToggleSourceField}
```

## Tests

### `web/components/projects/__tests__/ReviewGrid.test.tsx`

Update the `testProps` object's `onRemoveSourceField: vi.fn()` (search for it, around the `describe("stacked destination-cell with add/remove controls"` block) to `onToggleSourceField: vi.fn()`.

**Replace** the test currently named `"shows a source-field delete icon even for a single-destination source field"`:

```tsx
it("shows a source-field toggle icon even for a single-destination source field", () => {
  const onToggleSourceField = vi.fn();
  const propsWithToggle = { ...testProps, onToggleSourceField };
  render(<ReviewGrid {...propsWithToggle} />);
  fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

  const toggleButtons = screen.getAllByTitle("Included in migration — click to exclude");
  expect(toggleButtons).toHaveLength(2); // one per group, including the single-entry "src_status" group
  fireEvent.click(toggleButtons[1]); // "src_status" is the second group in bindings order

  expect(onToggleSourceField).toHaveBeenCalledWith("accounts", "src_status", true);
});
```

**Replace** the test currently named `"does not show either delete icon when editingEnabled is false"` with two tests:

```tsx
it("does not show the destination-mapping delete icon when editingEnabled is false", () => {
  const propsNoEdit = { ...testProps, editingEnabled: false };
  render(<ReviewGrid {...propsNoEdit} />);
  fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

  expect(screen.queryByTitle("Remove this destination mapping")).not.toBeInTheDocument();
});

it("shows the source-field toggle icon but disables it when editingEnabled is false", () => {
  const propsNoEdit = { ...testProps, editingEnabled: false };
  render(<ReviewGrid {...propsNoEdit} />);
  fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

  const toggleButtons = screen.getAllByTitle("Included in migration — click to exclude");
  expect(toggleButtons.length).toBeGreaterThan(0);
  toggleButtons.forEach((btn) => expect(btn).toBeDisabled());
});
```

**Add** a new test for the dropped/strikethrough visual state:

```tsx
it("shows strikethrough and unchecked icon for a dropped source field", () => {
  const droppedProps = {
    ...testProps,
    mappingTables: [
      {
        ...testProps.mappingTables[0],
        bindings: testProps.mappingTables[0].bindings.map((b) =>
          b.sourceField === "src_status" ? { ...b, dropped: true } : b
        ),
      },
    ],
  };
  render(<ReviewGrid {...droppedProps} />);
  fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

  const droppedLabel = screen.getByText("src_status");
  expect(droppedLabel.className).toContain("line-through");
  expect(screen.getByTitle("Excluded from migration — click to include")).toBeInTheDocument();
});
```

## Verification

```bash
cd web && npm test -- --run
```

Confirm zero failures. `web/lib/mapping-api.test.ts` needs no edits — if it fails, `dropped` was likely made required instead of optional in Step "File Changes" for `mapping-api.ts`.

Manual browser verification (required — jsdom has no real layout engine, so strikethrough rendering and dropdown clipping cannot be observed by unit tests):

1. Toggle a source field off on a table with several rows. Confirm the row stays visible with the source field name struck through, icon unchecked.
2. Toggle it back on. Confirm strikethrough clears.
3. As a non-editing viewer, confirm the icon/strikethrough state is visible but not clickable.
4. Open the destination-field autocomplete on the *last* row of a table with several rows. Confirm the dropdown opens upward and every option is selectable — not clipped behind the table's scrollbar.

## Pitfalls

- Do NOT leave the two existing `ReviewGrid.test.tsx` tests (source-field delete icon, editingEnabled visibility) unmodified alongside new tests — they assert the old hard-delete/gated-visibility behavior and will either fail or (worse) pass while asserting the wrong contract if only loosely touched.
- Do NOT send a filtered bindings list from `handleToggleSourceField` — that silently reverts this task to the old hard-delete semantics and breaks 001gw's sign-off preservation, even though the button would *look* like a toggle in the UI.
- Do NOT implement dropdown clipping via a portal — flip-upward was the explicit, confirmed design choice.
- Do NOT assume jsdom can verify the `openUpward` logic — it has no real `getBoundingClientRect`/viewport geometry. The manual browser check is the only real verification for that fix.

## Commit

```
feat(mapping): replace hard-delete source field button with dropped soft-delete toggle
```
