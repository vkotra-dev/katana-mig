# Plan: Task 001fe — Destination-Anchored Lookup Grid & Local LLM Agent Execution Guide

- **Task**: [001fe-review-page-lookup-grid-display.md](file:///Users/vjkotra/projects/katana/tasks/001fe-review-page-lookup-grid-display.md)
- **Domain**: [governance.md](file:///Users/vjkotra/projects/katana/docs/domain/governance.md) | [ui.md](file:///Users/vjkotra/projects/katana/docs/domain/ui.md)

---

## Current State
1. In `LookupMappingTable.tsx`, line 247 checks `row.label || row.name || row.description ...`. If no key matches, it falls back to joining all non-ID object entries with ` | `, outputting multi-column gibberish strings like `"Y | N | APPROVED | Approved | 3"`.
2. On the Feed Page (`page.tsx`), proposed mappings render `JSON.stringify(pm.destRow)` on line 1018 instead of a formatted badge, and the table puts `Source Value` in Column 1 and `Destination Row` in Column 2.
3. In `LookupMappingTable.tsx`, source values are not editable inline when `editingEnabled` is true.

---

## Objective
1. Redesign `LookupMappingTable.tsx` into a **Destination-Anchored Many-to-1 Grid**: Column 1 = `Destination Value (ID)` (e.g. `Approved (3)`), Column 2 = Vertically stacked flex column (`flex flex-col gap-1.5`) holding inline editable source value `<input>` fields with adjacent `×` delete buttons and a stacked **`+ Add another source value`** button.
2. Completely delete the multi-column pipe string join fallback (`"Y | N | APPROVED | Approved | 3"`) in `LookupMappingTable.tsx`.
3. Unify column order on the Feed Page (`page.tsx`) AI Proposed Mappings table to match: Column 1 = `Destination Value (ID)`, Column 2 = `Mapped Source Value`, Column 3 = `Confidence`.
4. Ensure `_bridge_lookup_fiber_to_value_map` in `fibers.py` preserves `label` on `destination_table` rows.

---

## Out of Scope
- Modifying stored procedure codegen logic (Task 001fd).
- Creating or editing database models / Alembic migrations.

---

## Blast Radius
- `web/components/projects/LookupMappingTable.tsx`
- `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`
- `web/app/projects/[id]/feeds/[feedId]/page.tsx`
- `engine/src/migrations_engine/management/fibers.py`

---

## Detailed Code Diffs for Agent

### Component 1: `web/components/projects/LookupMappingTable.tsx`

#### 1. Label Extraction & Fallback Removal
Replace lines 247–259 with explicit priority keys and fallback to `destId` directly:
```ts
const rawLabel = 
  row.label || 
  row.status_name || 
  row.display_name || 
  row.name || 
  row.title || 
  row.description || 
  row.status_code || 
  row.code || 
  row.desc || 
  row.val || 
  row.value || 
  row.display;

let finalLabel = destId;
if (rawLabel) {
  finalLabel = String(rawLabel).replace(/['"`]/g, "");
}
```

#### 2. Table Headers & Vertical Stack Body
```tsx
<table className="w-full border-collapse text-left text-xs">
  <thead>
    <tr className="border-b border-slate-100 pb-2 text-slate-400 font-semibold uppercase tracking-wider">
      <th className="py-2 w-1/3">Destination Value (ID)</th>
      <th className="py-2 w-1/2">Mapped Source Values</th>
      <th className="py-2 w-1/6">Status</th>
    </tr>
  </thead>
  <tbody className="divide-y divide-slate-100">
    {destinationRows.map((destRow) => {
      const destId = extractDestinationId(destRow);
      const destLabelText = availableDestinationOptions.find(o => o.value === destId)?.label || destId;
      const mappedSources = pairs
        .filter(p => (p.destinationId ?? p.destinationRow?.id) === destId)
        .map(p => p.sourceValue);

      return (
        <tr key={destId} className="hover:bg-slate-50/50">
          <td className="py-3 font-mono text-[11px] text-slate-800 font-medium align-top">
            {destLabelText !== destId ? (
              <>
                {destLabelText} <span className="text-slate-400">({destId})</span>
              </>
            ) : (
              destId
            )}
          </td>
          <td className="py-3 pr-4 align-top">
            <div className="flex flex-col gap-1.5 w-full max-w-full overflow-hidden">
              {(mappedSources.length > 0 ? mappedSources : [""]).map((srcVal, srcIdx) => (
                <div key={srcIdx} className="flex items-center gap-1.5 w-full">
                  {editingEnabled ? (
                    <input
                      type="text"
                      value={srcVal}
                      placeholder="Type source value..."
                      onChange={(e) => handleSourceChange(destId, srcIdx, e.target.value)}
                      className="rounded border border-slate-200 bg-white px-2.5 py-1 font-mono text-xs text-slate-900 w-full max-w-[240px] focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none"
                    />
                  ) : (
                    <span className="font-mono text-xs text-slate-800 font-semibold truncate max-w-[240px] inline-block">{srcVal || <span className="text-amber-600 italic">Unmapped</span>}</span>
                  )}
                  {editingEnabled && mappedSources.length > 0 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveSource(destId, srcIdx)}
                      className="text-slate-400 hover:text-red-600 font-bold text-xs px-1 shrink-0"
                      title="Remove source mapping"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
              {editingEnabled && (
                <button
                  type="button"
                  onClick={() => handleAddSource(destId)}
                  className="text-xs text-primary font-semibold hover:text-primary-hover flex items-center gap-1 mt-1 text-left self-start"
                >
                  <span className="text-sm leading-none">+</span> Add another source value
                </button>
              )}
            </div>
          </td>
          <td className="py-3 align-top">{getStatusBadge(mappedSources.length > 0 ? "confirmed" : "pending")}</td>
        </tr>
      );
    })}
  </tbody>
</table>
```

---

### Component 2: `web/app/projects/[id]/feeds/[feedId]/page.tsx`
Swap headers and cells on line 1007 to match Destination-Anchored layout:
```tsx
<tr className="border-b border-slate-100 bg-slate-50 text-slate-500 font-semibold">
  <th className="px-3 py-2">Destination Value (ID)</th>
  <th className="px-3 py-2">Mapped Source Value</th>
  <th className="px-3 py-2 text-right">Confidence</th>
</tr>
```
Line 1018:
```tsx
<td className="px-3 py-2 font-mono text-xs text-slate-800 font-medium">
  {pm.destRow ? (
    pm.destRow.label && pm.destRow.label !== pm.destRow.id ? (
      <>
        {pm.destRow.label} <span className="text-slate-400">({pm.destRow.id})</span>
      </>
    ) : (
      pm.destRow.id || "—"
    )
  ) : (
    <span className="text-slate-400 italic">—</span>
  )}
</td>
```

---

### Component 3: `engine/src/migrations_engine/management/fibers.py`
Ensure `_bridge_lookup_fiber_to_value_map` includes `label` in `destination_table` dictionaries:
```python
dest_entries.append({
    "id": str(row_data.get("id", row.entry_id)),
    "label": row_data.get("label") or _extract_destination_label(row_data),
})
```

---

## Tests
```bash
# Frontend test suite
cd web && npm run test

# Backend test suite
cd engine && source ../.venv/bin/activate && pytest -v
```

---

## Verification Checklist
- [ ] Review Page Column 1 displays `Approved (3)` without any pipe gibberish (`"Y | N | APPROVED | Approved | 3"`).
- [ ] Review Page Column 2 displays vertically stacked inline editable source inputs with adjacent `×` buttons.
- [ ] Click **`+ Add another source value`** creates a new input stacked below existing inputs.
- [ ] Feed Page proposed mappings table matches Column 1 = `Destination Value (ID)`, Column 2 = `Mapped Source Value`.
- [ ] Frontend vitest tests and backend pytest tests pass 100%.

---

## Pitfalls & Agent Safeguards
- **DO NOT** delete `extractDestinationId` helper function in `LookupMappingTable.tsx`.
- **DO NOT** modify stored procedure codegen files (`codegen/lookup_upsert.py`).
- Maintain `w-full max-w-[240px] truncate` styling on source inputs to prevent horizontal scrolling.

---

## Commit
`feat(ui,lookup): clean destination labels, vertical stacked source inputs, and unified column order (001fe)`
