# Plan: 001eq — Review Page — Stacked Destination-Field Cell with Add/Remove Controls

## Task and Domain links

- Task: `tasks/001eq-review-page-stacked-destination-cell-with-delete.md`
- Depends on: `001ep` (must be committed first — `patch_mapping` must allow dropping a signed-off
  binding before this task's delete controls can work end-to-end). Confirm before starting:
  `grep -n "mapping_already_approved" engine/src/migrations_engine/mapping/review.py` should return
  nothing. If it still finds the old 409 block, stop — `001ep` hasn't landed yet.
- Domain: no `docs/domain/` page documents this table's row/cell layout in enough detail to need an
  update.

## Audience note

Written for an agent with no prior context. Every edit gives the exact current text to find and
the exact replacement. Re-read both files in full immediately before starting to confirm they
still match what's quoted below — if either has drifted (e.g. `001eo` or other work landed and
changed nearby lines), reconcile by hand rather than blindly pasting a mismatched block.

## Current State (verbatim)

### `web/components/projects/ReviewGrid.tsx`

Lines 6-16 (the exported binding-array type used throughout this file):

```tsx
export interface MappingTableRecord {
  destinationTableName: string;
  destinationFields?: string[];
  fiberStatus?: string;
  bindings: Array<{
    sourceField: string;
    destinationField: string;
    bindingType: "direct" | "detail_fk" | "lookup_fk";
    referenceTableName?: string | null;
  }>;
}
```

Lines 31-48 (`ReviewGridProps`):

```tsx
interface ReviewGridProps {
  mappingTables: MappingTableRecord[];
  lookupGroups: LookupValueGroup[];
  sampleValues?: Record<string, string[]>;
  unmappedSourceFields?: string[];
  unmappedDestinationFields?: { tableName: string; fieldName: string }[];
  onApprove?: () => void;           // present for business_user only
  onRequestRevision?: (comment: string) => void;
  signOffStatus?: SignOffStatusRecord;
  currentUserRole?: string;
  editingEnabled?: boolean;
  onSignBinding?: (tableName: string, sourceField: string, destField: string) => void;
  onUnsignBinding?: (tableName: string, sourceField: string, destField: string) => void;
  onDestinationFieldChange?: (tableName: string, sourceField: string, oldDest: string, newDest: string) => void;
  onAddBinding?: (tableName: string, sourceField: string, availableFields: string[]) => void;
  onSignLookup?: (lookupValueMapId: string) => void;
  onUnsignLookup?: (lookupValueMapId: string) => void;
}
```

Lines 193-210 (the `ReviewGrid` function's prop destructuring):

```tsx
export function ReviewGrid({
  mappingTables,
  lookupGroups,
  sampleValues = {},
  unmappedSourceFields = [],
  unmappedDestinationFields = [],
  onApprove,
  onRequestRevision,
  signOffStatus,
  currentUserRole,
  editingEnabled = false,
  onSignBinding,
  onUnsignBinding,
  onDestinationFieldChange,
  onAddBinding,
  onSignLookup,
  onUnsignLookup,
}: ReviewGridProps) {
```

Lines 436-582 (the whole per-table block, from the `mappingTables.map` callback through its
closing — this is the block that gets restructured; quoted in full since nearly every line inside
it is either replaced or re-indented):

```tsx
            {mappingTables.map((table) => {
              const isExpanded = !!expandedTables[table.destinationTableName];
              // Count how many times each source field is mapped (for 1-to-N support)
              const sourceFieldCount: Record<string, number> = {};
              for (const b of table.bindings) {
                sourceFieldCount[b.sourceField] = (sourceFieldCount[b.sourceField] || 0) + 1;
              }
              return (
                <div
                  key={table.destinationTableName}
                  className="overflow-hidden rounded-2xl border border-outline-variant bg-surface-container shadow-sm transition-all hover:shadow"
                >
                  <button
                    onClick={() => toggleTable(table.destinationTableName)}
                    className="flex w-full items-center justify-between px-5 py-4 text-left font-semibold text-slate-900 hover:bg-slate-50 focus:outline-none"
                    type="button"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono text-primary font-bold">
                        {table.destinationTableName}
                      </span>
                      {table.fiberStatus && (
                        <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase font-semibold ${
                          table.fiberStatus === "operator_triggered" || table.fiberStatus === "codegen_complete"
                            ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-700"
                            : table.fiberStatus === "business_approved"
                            ? "border-blue-500/20 bg-blue-500/10 text-blue-700"
                            : table.fiberStatus === "operator_assigned"
                            ? "border-amber-500/20 bg-amber-500/10 text-amber-700"
                            : "border-slate-200 bg-slate-50 text-slate-600"
                        }`}>
                          {table.fiberStatus.replace(/_/g, " ")}
                        </span>
                      )}
                      <span className="text-xs font-normal text-slate-500">
                        ({table.bindings.length} fields mapped)
                      </span>
                    </div>
                    <svg
                      className={`h-5 w-5 text-slate-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>

                  {isExpanded && (
                    <div className="border-t border-outline-variant bg-white px-5 py-4">
                      <div className="overflow-x-auto">
                        <table className="w-full border-collapse text-left text-xs">
                          <thead>
                            <tr className="border-b border-slate-100 pb-2 text-slate-400 font-semibold uppercase tracking-wider">
                              <th className="py-2">Source Field</th>
                              <th className="py-2">Destination Field</th>
                              <th className="py-2">Type</th>
                              {signOffStatus && <th className="py-2">Sign-offs</th>}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {table.bindings.map((binding, idx) => (
                              <tr key={idx} className="hover:bg-slate-50/50">
                                <td className="py-2.5">
                                  <div className="flex items-center gap-1.5">
                                    <span className="font-mono text-slate-700">{binding.sourceField}</span>
                                    {sourceFieldCount[binding.sourceField] > 1 && (
                                      <span className="inline-flex items-center rounded bg-primary/10 px-1.5 py-0.5 text-[9px] font-semibold text-primary">
                                        1-to-{sourceFieldCount[binding.sourceField]}
                                      </span>
                                    )}
                                  </div>
                                  {(() => {
                                    // Show "Map to another destination" button next to each editable row
                                    const bindingStatus = signOffStatus?.bindings[table.destinationTableName]?.[binding.sourceField]?.[binding.destinationField];
                                    const isRowSigned = !!(bindingStatus && (bindingStatus.centralTeam.signed || bindingStatus.projectStakeholder.signed));
                                    if (!editingEnabled || isRowSigned) return null;
                                    const mappedDests = new Set(table.bindings.filter(b => b.sourceField === binding.sourceField).map(b => b.destinationField));
                                    const available = (table.destinationFields || []).filter(d => d && !mappedDests.has(d));
                                    if (available.length === 0) return null;
                                    return (
                                      <button
                                        type="button"
                                        onClick={() => onAddBinding?.(table.destinationTableName, binding.sourceField, available)}
                                        className="mt-1 text-xs text-primary font-semibold hover:text-primary-hover flex items-center gap-1"
                                      >
                                        <span className="text-sm leading-none">+</span> Map to another destination
                                      </button>
                                    );
                                  })()}
                                  {(() => {
                                    const samples = sampleValues[binding.sourceField.toLowerCase()] ?? [];
                                    if (samples.length === 0) return null;
                                    return (
                                      <div className="mt-0.5 flex flex-wrap gap-1">
                                        {samples.map((v, i) => (
                                          <span key={i} className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500 font-mono">
                                            {v}
                                          </span>
                                        ))}
                                      </div>
                                    );
                                  })()}
                                </td>
                                <td className="py-2.5 font-mono text-slate-900 font-medium">
                                  {(() => {
                                    const bindingStatus = signOffStatus?.bindings[table.destinationTableName]?.[binding.sourceField]?.[binding.destinationField];
                                    const isSignedByEither = !!(bindingStatus && (bindingStatus.centralTeam.signed || bindingStatus.projectStakeholder.signed));
                                    const rowEditable = editingEnabled && !isSignedByEither;
                                    return rowEditable ? (
                                      <AutocompleteInput
                                        value={binding.destinationField}
                                        options={table.destinationFields || []}
                                        onChange={(newVal) => onDestinationFieldChange?.(table.destinationTableName, binding.sourceField, binding.destinationField, newVal)}
                                        className="rounded border border-slate-200 bg-white px-2 py-1 font-mono text-xs w-full focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none"
                                        placeholder="destination field..."
                                      />
                                    ) : (
                                      <div className="flex items-center gap-1.5 py-1 text-slate-700">
                                        <span>{binding.destinationField || <span className="text-slate-400 italic font-sans text-xs">unmapped</span>}</span>
                                        {isSignedByEither && (
                                          <span title="Locked because this mapping has been signed off by a reviewer" className="text-[10px] text-slate-400 select-none">
                                            🔒
                                          </span>
                                        )}
                                      </div>
                                    );
                                  })()}
                                </td>
                                <td className="py-2.5">{getBindingBadge(binding.bindingType)}</td>
                                {signOffStatus && (
                                  <td className="py-2.5">
                                    {renderSignOffChips(table.destinationTableName, binding.sourceField, binding.destinationField)}
                                  </td>
                                )}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
```

### `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`

`handleAddBinding` (lines 246-284 — quoted as the reference pattern the two new handlers must
match; not itself edited by this task):

```tsx
  const handleAddBinding = async (tableName: string, sourceField: string, availableFields: string[]) => {
    // Filter out already-mapped destination fields
    const targetSnapshot = mappingSnapshots.find((s) => s.destinationObjectName === tableName);
    if (!targetSnapshot) return;

    const existingDests = new Set(targetSnapshot.fieldBindings.map(b => b.destinationField));
    const available = availableFields.find(d => d && !existingDests.has(d));
    if (!available) {
      setError("All destination fields are already mapped for this source field.");
      return;
    }

    // Optimistically add the binding to local state
    setMappingSnapshots((prev) =>
      prev.map((snapshot) => {
        if (snapshot.destinationObjectName !== tableName) return snapshot;
        return {
          ...snapshot,
          fieldBindings: [
            ...snapshot.fieldBindings,
            { sourceField, destinationField: available, bindingType: "direct", lookupName: null }
          ],
        };
      })
    );

    // Commit in the background
    if (!session) return;
    try {
      // Include the newly added binding in the payload (use the target snapshot from local state,
      // which is the same copy read by the optimistic update above — avoids stale closure)
      const updatedBindings = [...targetSnapshot.fieldBindings, { sourceField, destinationField: available, lookupName: null }];
      await patchMappingSnapshot(session.accessToken, projectId, feedId, updatedBindings, tableName);
      const updated = await getSignOffStatus(session.accessToken, projectId, feedId);
      setSignOffStatus(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add binding.");
    }
  };
```

The `<ReviewGrid>` call site (lines 534-551):

```tsx
                    <ReviewGrid
                      mappingTables={mappingTables}
                      lookupGroups={lookupGroups}
                      sampleValues={sampleValues}
                      unmappedSourceFields={unmappedSourceFields}
                      unmappedDestinationFields={unmappedDestinationFields}
                      onApprove={showStakeholderActionButtons ? handleApprove : undefined}
                      onRequestRevision={showStakeholderActionButtons ? handleRequestRevision : undefined}
                      signOffStatus={signOffStatus || undefined}
                      currentUserRole={role}
                      editingEnabled={editingEnabled}
                      onSignBinding={handleSignBinding}
                      onUnsignBinding={handleUnsignBinding}
                      onDestinationFieldChange={handleDestinationFieldChange}
                      onAddBinding={handleAddBinding}
                      onSignLookup={handleSignLookup}
                      onUnsignLookup={handleUnsignLookup}
                    />
```

## Objective

Group bindings by source field for rendering (one `<tr>` per group), stack the Destination
Field/Type/Sign-offs cells per entry within that row, add a per-entry delete control (hidden on
entry 0), add a whole-source-field delete control, and wire both through to the backend via new
`onRemoveBinding`/`onRemoveSourceField` props and matching page-level handlers.

## File Changes

### 1. `web/components/projects/ReviewGrid.tsx`

**1a.** Find the exact `ReviewGridProps` block quoted above and add two new optional props after
`onAddBinding`:

```tsx
  onAddBinding?: (tableName: string, sourceField: string, availableFields: string[]) => void;
  onRemoveBinding?: (tableName: string, sourceField: string, destinationField: string) => void;
  onRemoveSourceField?: (tableName: string, sourceField: string) => void;
  onSignLookup?: (lookupValueMapId: string) => void;
```

(only the two new lines are inserted between the existing `onAddBinding` and `onSignLookup` lines
— everything else in the interface is unchanged.)

**1b.** Find the exact `ReviewGrid({ ... })` destructuring block quoted above and add the same two
names:

```tsx
  onAddBinding,
  onRemoveBinding,
  onRemoveSourceField,
  onSignLookup,
```

**1c.** Find the exact 436-582 block quoted above in full under "Current State" and replace it
with:

```tsx
            {mappingTables.map((table) => {
              const isExpanded = !!expandedTables[table.destinationTableName];
              type BindingEntry = MappingTableRecord["bindings"][number];
              const groups: Array<{ sourceField: string; bindings: BindingEntry[] }> = [];
              const groupIndexBySourceField: Record<string, number> = {};
              table.bindings.forEach((b) => {
                if (groupIndexBySourceField[b.sourceField] === undefined) {
                  groupIndexBySourceField[b.sourceField] = groups.length;
                  groups.push({ sourceField: b.sourceField, bindings: [] });
                }
                groups[groupIndexBySourceField[b.sourceField]].bindings.push(b);
              });
              return (
                <div
                  key={table.destinationTableName}
                  className="overflow-hidden rounded-2xl border border-outline-variant bg-surface-container shadow-sm transition-all hover:shadow"
                >
                  <button
                    onClick={() => toggleTable(table.destinationTableName)}
                    className="flex w-full items-center justify-between px-5 py-4 text-left font-semibold text-slate-900 hover:bg-slate-50 focus:outline-none"
                    type="button"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono text-primary font-bold">
                        {table.destinationTableName}
                      </span>
                      {table.fiberStatus && (
                        <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase font-semibold ${
                          table.fiberStatus === "operator_triggered" || table.fiberStatus === "codegen_complete"
                            ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-700"
                            : table.fiberStatus === "business_approved"
                            ? "border-blue-500/20 bg-blue-500/10 text-blue-700"
                            : table.fiberStatus === "operator_assigned"
                            ? "border-amber-500/20 bg-amber-500/10 text-amber-700"
                            : "border-slate-200 bg-slate-50 text-slate-600"
                        }`}>
                          {table.fiberStatus.replace(/_/g, " ")}
                        </span>
                      )}
                      <span className="text-xs font-normal text-slate-500">
                        ({table.bindings.length} fields mapped)
                      </span>
                    </div>
                    <svg
                      className={`h-5 w-5 text-slate-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>

                  {isExpanded && (
                    <div className="border-t border-outline-variant bg-white px-5 py-4">
                      <div className="overflow-x-auto">
                        <table className="w-full border-collapse text-left text-xs">
                          <thead>
                            <tr className="border-b border-slate-100 pb-2 text-slate-400 font-semibold uppercase tracking-wider">
                              <th className="py-2">Source Field</th>
                              <th className="py-2">Destination Field</th>
                              <th className="py-2">Type</th>
                              {signOffStatus && <th className="py-2">Sign-offs</th>}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {groups.map((group) => (
                              <tr key={group.sourceField} className="hover:bg-slate-50/50">
                                <td className="py-2.5 align-top">
                                  <div className="flex items-center gap-1.5">
                                    {editingEnabled && (
                                      <button
                                        type="button"
                                        onClick={() => onRemoveSourceField?.(table.destinationTableName, group.sourceField)}
                                        title="Drop this source field from migration"
                                        className="text-slate-400 hover:text-red-600 focus:outline-none text-xs font-bold leading-none"
                                      >
                                        ×
                                      </button>
                                    )}
                                    <span className="font-mono text-slate-700">{group.sourceField}</span>
                                    {group.bindings.length > 1 && (
                                      <span className="inline-flex items-center rounded bg-primary/10 px-1.5 py-0.5 text-[9px] font-semibold text-primary">
                                        1-to-{group.bindings.length}
                                      </span>
                                    )}
                                  </div>
                                  {(() => {
                                    const samples = sampleValues[group.sourceField.toLowerCase()] ?? [];
                                    if (samples.length === 0) return null;
                                    return (
                                      <div className="mt-0.5 flex flex-wrap gap-1">
                                        {samples.map((v, i) => (
                                          <span key={i} className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500 font-mono">
                                            {v}
                                          </span>
                                        ))}
                                      </div>
                                    );
                                  })()}
                                </td>
                                <td className="py-2.5 font-mono text-slate-900 font-medium align-top">
                                  <div className="flex flex-col gap-1.5">
                                    {group.bindings.map((binding, entryIdx) => {
                                      const bindingStatus = signOffStatus?.bindings[table.destinationTableName]?.[binding.sourceField]?.[binding.destinationField];
                                      const isSignedByEither = !!(bindingStatus && (bindingStatus.centralTeam.signed || bindingStatus.projectStakeholder.signed));
                                      const rowEditable = editingEnabled && !isSignedByEither;
                                      return (
                                        <div key={entryIdx} className="flex items-center gap-1.5">
                                          {rowEditable ? (
                                            <AutocompleteInput
                                              value={binding.destinationField}
                                              options={table.destinationFields || []}
                                              onChange={(newVal) => onDestinationFieldChange?.(table.destinationTableName, binding.sourceField, binding.destinationField, newVal)}
                                              className="rounded border border-slate-200 bg-white px-2 py-1 font-mono text-xs w-full focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none"
                                              placeholder="destination field..."
                                            />
                                          ) : (
                                            <div className="flex items-center gap-1.5 py-1 text-slate-700">
                                              <span>{binding.destinationField || <span className="text-slate-400 italic font-sans text-xs">unmapped</span>}</span>
                                              {isSignedByEither && (
                                                <span title="Locked because this mapping has been signed off by a reviewer" className="text-[10px] text-slate-400 select-none">
                                                  🔒
                                                </span>
                                              )}
                                            </div>
                                          )}
                                          {editingEnabled && entryIdx > 0 && (
                                            <button
                                              type="button"
                                              onClick={() => onRemoveBinding?.(table.destinationTableName, binding.sourceField, binding.destinationField)}
                                              title="Remove this destination mapping"
                                              className="text-slate-400 hover:text-red-600 focus:outline-none text-xs font-bold leading-none"
                                            >
                                              ×
                                            </button>
                                          )}
                                        </div>
                                      );
                                    })}
                                    {editingEnabled && (() => {
                                      const mappedDests = new Set(group.bindings.map((b) => b.destinationField));
                                      const available = (table.destinationFields || []).filter((d) => d && !mappedDests.has(d));
                                      if (available.length === 0) return null;
                                      return (
                                        <button
                                          type="button"
                                          onClick={() => onAddBinding?.(table.destinationTableName, group.sourceField, available)}
                                          className="text-xs text-primary font-semibold hover:text-primary-hover flex items-center gap-1"
                                        >
                                          <span className="text-sm leading-none">+</span> Map to another destination
                                        </button>
                                      );
                                    })()}
                                  </div>
                                </td>
                                <td className="py-2.5 align-top">
                                  <div className="flex flex-col gap-1.5">
                                    {group.bindings.map((binding, entryIdx) => (
                                      <div key={entryIdx} className="py-1">{getBindingBadge(binding.bindingType)}</div>
                                    ))}
                                  </div>
                                </td>
                                {signOffStatus && (
                                  <td className="py-2.5 align-top">
                                    <div className="flex flex-col gap-1.5">
                                      {group.bindings.map((binding, entryIdx) => (
                                        <div key={entryIdx} className="py-1">
                                          {renderSignOffChips(table.destinationTableName, binding.sourceField, binding.destinationField)}
                                        </div>
                                      ))}
                                    </div>
                                  </td>
                                )}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
```

Note precisely what changed versus the original, so a reviewer can verify intent, not just text:
- `sourceFieldCount` (a parallel count-map) is deleted entirely — `group.bindings.length` replaces
  every use of it.
- `table.bindings.map((binding, idx) => ...)` (one `<tr>` per binding) becomes
  `groups.map((group) => ...)` (one `<tr>` per unique source field).
- The old per-row "Map to another destination" button (previously duplicated once per binding row
  within a 1-to-N group — a pre-existing quirk of the old flat-row layout) is now a single button
  per group, and no longer checks any binding's signed status (see Requirement 6 in the task file
  for why that check is dropped, not just relocated).
- A new `×` on the source field (unconditional on `editingEnabled`, not on group size) and a new
  `×` per stacked destination entry (conditional on `editingEnabled && entryIdx > 0`) are added.
- Type and Sign-offs `<td>`s go from rendering one value to rendering
  `group.bindings.map(...)`, one entry per binding, in the same order as the destination-field
  stack.

### 2. `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`

**2a.** Find the exact `handleAddBinding` function quoted above under "Current State" and insert
two new functions immediately after its closing `};` (before `handlePushForReview`, which is the
next function in the file):

```tsx
  const handleRemoveBinding = async (tableName: string, sourceField: string, destinationField: string) => {
    const targetSnapshot = mappingSnapshots.find((s) => s.destinationObjectName === tableName);
    if (!targetSnapshot) return;

    // Optimistically remove the binding from local state
    setMappingSnapshots((prev) =>
      prev.map((snapshot) => {
        if (snapshot.destinationObjectName !== tableName) return snapshot;
        return {
          ...snapshot,
          fieldBindings: snapshot.fieldBindings.filter(
            (b) => !(b.sourceField === sourceField && b.destinationField === destinationField)
          ),
        };
      })
    );

    // Commit in the background — build the payload directly from the pre-update targetSnapshot
    // closure captured above, same pattern as handleAddBinding, avoids any stale-closure race.
    if (!session) return;
    try {
      const updatedBindings = targetSnapshot.fieldBindings
        .filter((b) => !(b.sourceField === sourceField && b.destinationField === destinationField))
        .map((b) => ({ sourceField: b.sourceField, destinationField: b.destinationField, lookupName: b.lookupName }));
      await patchMappingSnapshot(session.accessToken, projectId, feedId, updatedBindings, tableName);
      const updated = await getSignOffStatus(session.accessToken, projectId, feedId);
      setSignOffStatus(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove binding.");
    }
  };

  const handleRemoveSourceField = async (tableName: string, sourceField: string) => {
    const targetSnapshot = mappingSnapshots.find((s) => s.destinationObjectName === tableName);
    if (!targetSnapshot) return;

    // Optimistically remove every binding for this source field from local state
    setMappingSnapshots((prev) =>
      prev.map((snapshot) => {
        if (snapshot.destinationObjectName !== tableName) return snapshot;
        return {
          ...snapshot,
          fieldBindings: snapshot.fieldBindings.filter((b) => b.sourceField !== sourceField),
        };
      })
    );

    if (!session) return;
    try {
      const updatedBindings = targetSnapshot.fieldBindings
        .filter((b) => b.sourceField !== sourceField)
        .map((b) => ({ sourceField: b.sourceField, destinationField: b.destinationField, lookupName: b.lookupName }));
      await patchMappingSnapshot(session.accessToken, projectId, feedId, updatedBindings, tableName);
      const updated = await getSignOffStatus(session.accessToken, projectId, feedId);
      setSignOffStatus(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove source field mapping.");
    }
  };
```

**2b.** Find the exact `<ReviewGrid ...>` block quoted above under "Current State" and add two new
props after `onAddBinding`:

```tsx
                      onAddBinding={handleAddBinding}
                      onRemoveBinding={handleRemoveBinding}
                      onRemoveSourceField={handleRemoveSourceField}
                      onSignLookup={handleSignLookup}
```

## Tests

Add to `web/components/projects/__tests__/ReviewGrid.test.tsx`, inside the existing
`describe("ReviewGrid", ...)` block. All 5 new tests below share one fixture — define it once near
the top of the new tests (or inline per test, matching this file's existing style of inlining
`testProps` per test rather than sharing via a variable across `it` blocks — check the existing
`describe("handleAddBinding")` tests, which each define their own `testProps`, and follow that same
per-test inlining, not a shared `beforeEach`):

```tsx
const testProps = {
  ...props,
  editingEnabled: true,
  onRemoveBinding: vi.fn(),
  onRemoveSourceField: vi.fn(),
  onAddBinding: vi.fn(),
  onDestinationFieldChange: vi.fn(),
  mappingTables: [
    {
      destinationTableName: "accounts",
      destinationFields: ["id", "status_id", "name", "email", "created_at"],
      bindings: [
        { sourceField: "src_id", destinationField: "id", bindingType: "direct" as const },
        { sourceField: "src_id", destinationField: "name", bindingType: "direct" as const },
        { sourceField: "src_status", destinationField: "status_id", bindingType: "lookup_fk" as const },
      ],
    },
  ],
};
```

This has one group (`"src_id"`) with 2 stacked bindings and one group (`"src_status"`) with 1 —
covering both the multi-entry and single-entry cases in one fixture.

1.

```tsx
  it("renders one row per source field, with destination fields stacked", () => {
    const testProps = { /* fixture above */ };
    render(<ReviewGrid {...testProps} />);
    fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

    // "src_id" appears once (one row for the group), not twice (one per binding)
    expect(screen.getAllByText("src_id")).toHaveLength(1);
    expect(screen.getAllByText("src_status")).toHaveLength(1);
  });
```

2.

```tsx
  it("shows a delete icon on all but the first stacked destination entry", () => {
    const testProps = { /* fixture above */ };
    render(<ReviewGrid {...testProps} />);
    fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

    // Only the group with 2 bindings ("src_id") has an entry past index 0
    expect(screen.getAllByTitle("Remove this destination mapping")).toHaveLength(1);
  });
```

3.

```tsx
  it("calls onRemoveBinding with the correct source and destination field", () => {
    const onRemoveBinding = vi.fn();
    const testProps = { /* fixture above, with onRemoveBinding */ };
    render(<ReviewGrid {...testProps} />);
    fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

    fireEvent.click(screen.getByTitle("Remove this destination mapping"));

    expect(onRemoveBinding).toHaveBeenCalledWith("accounts", "src_id", "name");
  });
```

4.

```tsx
  it("shows a source-field delete icon even for a single-destination source field", () => {
    const onRemoveSourceField = vi.fn();
    const testProps = { /* fixture above, with onRemoveSourceField */ };
    render(<ReviewGrid {...testProps} />);
    fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

    const deleteButtons = screen.getAllByTitle("Drop this source field from migration");
    expect(deleteButtons).toHaveLength(2); // one per group, including the single-entry "src_status" group
    fireEvent.click(deleteButtons[1]); // "src_status" is the second group in bindings order

    expect(onRemoveSourceField).toHaveBeenCalledWith("accounts", "src_status");
  });
```

5.

```tsx
  it("does not show either delete icon when editingEnabled is false", () => {
    const testProps = { /* fixture above, with editingEnabled: false */ };
    render(<ReviewGrid {...testProps} />);
    fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

    expect(screen.queryByTitle("Remove this destination mapping")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Drop this source field from migration")).not.toBeInTheDocument();
  });
```

6. **No new test needed for the Add button.** The existing test
   `"should allow adding a new binding when a row has available alternative destinations"`
   (`ReviewGrid.test.tsx` lines 228-264 as of this writing) uses a fixture with exactly one source
   field and one binding — under the new grouped rendering this is still exactly one group, so the
   "+" button still renders once and `screen.getAllByText(/Map to another destination/)` still
   finds it. This test requires **no changes** — run it as part of Verification to confirm it still
   passes unmodified; do not edit it.

In `web/app/projects/[id]/feeds/[feedId]/review/page.test.tsx`, inside the existing
`describe("ReviewPage", ...)` block. Both new tests below mirror the exact structure of the
existing test `"includes the new binding in the PATCH payload when adding a binding"` (lines
364-422 as of this writing) — same `loadUiSessionMock`/`getAllApprovedMappingSnapshotsMock`/
`getSignOffStatusMock` setup shape, same `callArgs[3]` extraction for the PATCH payload.

7.

```tsx
  it("removes a binding and sends the reduced field list to patchMappingSnapshot", async () => {
    loadUiSessionMock.mockReturnValue(BUSINESS_SESSION);

    const multiFieldSnapshot = {
      ...SNAPSHOT,
      destinationObjectName: "users",
      destinationFields: ["status_id", "name", "email"],
      fieldBindings: [
        {
          sourceField: "src_status",
          destinationField: "status_id",
          lookupName: "status_map",
          bindingType: "lookup_fk",
          referenceTableName: "status_ref",
        },
        {
          sourceField: "src_status",
          destinationField: "name",
          lookupName: null,
          bindingType: "direct",
        },
      ],
    };

    getAllApprovedMappingSnapshotsMock.mockResolvedValue([multiFieldSnapshot]);
    getSignOffStatusMock.mockResolvedValue({
      complete: false,
      currentBallRole: "project_stakeholder",
      bindings: {
        users: {
          src_status: {
            status_id: {
              centralTeam: { signed: false, signedAt: null, userId: null },
              projectStakeholder: { signed: false, signedAt: null, userId: null },
            },
            name: {
              centralTeam: { signed: false, signedAt: null, userId: null },
              projectStakeholder: { signed: false, signedAt: null, userId: null },
            },
          },
        },
      },
      lookups: {},
    });

    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: /users/ }));

    fireEvent.click(screen.getByTitle("Remove this destination mapping"));

    await waitFor(() => {
      expect(patchMappingSnapshotMock).toHaveBeenCalled();
    });

    const callArgs = patchMappingSnapshotMock.mock.calls[0];
    const bindings = callArgs[3];

    expect(bindings).toContainEqual(expect.objectContaining({ sourceField: "src_status", destinationField: "status_id" }));
    expect(bindings).not.toContainEqual(expect.objectContaining({ sourceField: "src_status", destinationField: "name" }));
  });
```

8.

```tsx
  it("removing a source field entirely sends a payload with no bindings for it", async () => {
    loadUiSessionMock.mockReturnValue(BUSINESS_SESSION);

    const multiFieldSnapshot = {
      ...SNAPSHOT,
      destinationObjectName: "users",
      destinationFields: ["status_id", "name", "email"],
      fieldBindings: [
        {
          sourceField: "src_status",
          destinationField: "status_id",
          lookupName: "status_map",
          bindingType: "lookup_fk",
          referenceTableName: "status_ref",
        },
        {
          sourceField: "src_email",
          destinationField: "email",
          lookupName: null,
          bindingType: "direct",
        },
      ],
    };

    getAllApprovedMappingSnapshotsMock.mockResolvedValue([multiFieldSnapshot]);
    getSignOffStatusMock.mockResolvedValue({
      complete: false,
      currentBallRole: "project_stakeholder",
      bindings: {},
      lookups: {},
    });

    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: /users/ }));

    const deleteButtons = screen.getAllByTitle("Drop this source field from migration");
    fireEvent.click(deleteButtons[0]); // "src_status" is the first group

    await waitFor(() => {
      expect(patchMappingSnapshotMock).toHaveBeenCalled();
    });

    const callArgs = patchMappingSnapshotMock.mock.calls[0];
    const bindings = callArgs[3];

    expect(bindings).not.toContainEqual(expect.objectContaining({ sourceField: "src_status" }));
    expect(bindings).toContainEqual(expect.objectContaining({ sourceField: "src_email", destinationField: "email" }));
  });
```

In `web/app/projects/[id]/feeds/[feedId]/review/page.test.tsx`:

7. **`"removes a binding and sends the reduced field list to patchMappingSnapshot"`.** Mirror the
   existing `"includes the new binding in the PATCH payload when adding a binding"` test (added in
   an earlier task) but for deletion: seed a snapshot with 2 bindings for the same source field,
   render, expand, click the per-entry delete icon on the second one, and assert
   `patchMappingSnapshotMock`'s call args contain only the first binding, not the second.
8. **`"removing a source field entirely sends a payload with no bindings for it"`.** Similar, using
   the source-field-level delete icon; assert the PATCH payload has zero entries for that source
   field (removes all of them if it had more than one).

## Verification

```bash
cd /Users/vjkotra/projects/katana/web
npx tsc --noEmit
```
Expect: no new type errors versus the pre-existing baseline (compare via `git checkout HEAD~1 --
<file>` + rerun + `git checkout HEAD -- <file>` if anything appears, exactly as done in prior tasks
this session — do not assume any error is new without checking).

```bash
npx vitest run components/projects/__tests__/ReviewGrid.test.tsx "app/projects/[id]/feeds/[feedId]/review/page.test.tsx"
```
Expect: all tests pass, including every pre-existing test in both files plus the 8 new ones above.

```bash
npx vitest run
```
Expect: full suite passes, same count as before this task plus the new tests, zero failures.

## Pitfalls

- **Don't gate either delete control on sign-off status.** This is the entire point of `001ep`
  landing first — re-adding an `isSignedByEither`-style check on the delete buttons would silently
  defeat that backend change and contradict the task's explicit requirement.
- **Don't gate the "Map to another destination" button on any binding's signed status either** —
  per Requirement 6, this is a deliberate simplification versus the old per-row code, not an
  oversight. Adding a signed-check back in would reintroduce the old, arguably-accidental
  inconsistency.
- **`group.sourceField` must be a stable, unique React key.** Since grouping is by `sourceField`
  and a table's bindings should never have two different groups with the same source field name
  (that's what the grouping collapses), this is safe — but if a future change ever allows two
  independent binding entries with identical `sourceField` values that are NOT meant to be grouped
  together, this key strategy would break. Not a concern for this task's scope, just don't "fix"
  the grouping logic to use array index keys instead — that would break React's reconciliation
  across add/remove operations (a classic index-key bug when list order/length changes).
- **Build every PATCH payload from the pre-update `targetSnapshot` closure captured at the top of
  the handler, via `.filter()`/`.map()` directly — never from a fresh `mappingSnapshots.find(...)`
  read taken after the optimistic `setMappingSnapshots` call.** This exact class of stale-closure
  bug was found and fixed in `handleAddBinding` earlier this session (React state updates aren't
  synchronous, so a `mappingSnapshots` read after `setMappingSnapshots` in the same function body
  still sees the old array). Both new handlers above already follow the fixed pattern — do not
  "simplify" them by re-reading state after the optimistic update.
- **`type BindingEntry = MappingTableRecord["bindings"][number];`** — this is how to reference the
  binding element's type without duplicating the inline object-literal type. Don't redefine a
  separate, parallel interface for this; it would drift from `MappingTableRecord` over time.
- **This task does not touch the Lookup Value Mapping section** (`lookupGroups.map(...)`, further
  down in the same file, a completely separate `<table>`) — confirm any diff tool/review doesn't
  show unintended changes there.

## Commit

Own commit, after `001ep`. Suggested message: `feat: stacked destination-field cell with add/remove
controls on the review page (001eq)`.
