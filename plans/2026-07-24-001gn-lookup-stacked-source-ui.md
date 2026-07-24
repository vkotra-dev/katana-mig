# Plan: Task 001gn — Component-Level Stacked Source Value Upsert (Add/Remove) UI in LookupMappingTable

- **Task**: [001gn-lookup-stacked-source-ui.md](file:///Users/vjkotra/projects/katana/tasks/001gn-lookup-stacked-source-ui.md)

---

## Goal Description

Refactor `LookupMappingTable.tsx` on the Review Page to provide a destination-anchored stacked source upsert interface with exact visual parity (`×` buttons) matching table mapping fibers (Task 001eq).

**Source values only** — there is no delete control on the destination side; destination groups are never deleted from this table.

```
+----------------------------------+--------------------------------------+------------+
| Destination (Anchor)             | Mapped Source Values (Stacked)       | Status     |
+----------------------------------+--------------------------------------+------------+
| Blocked (BLOCKED)                | ['B']                         [×]    | Pending    |
|                                   | ['BLOCKED']                   [×]    |            |
|                                   | + Add source value                   |            |
+----------------------------------+--------------------------------------+------------+
```

---

## Step-by-Step Build Instructions (Agent Executable)

---

### Step 1: Add Inline Add Form State in `LookupMappingTable.tsx`

**File**: [web/components/projects/LookupMappingTable.tsx](file:///Users/vjkotra/projects/katana/web/components/projects/LookupMappingTable.tsx)

```diff
 interface LookupMappingTableProps {
   groups: DestinationMappingGroup[];
   unmappedRowCount?: number;
   editingEnabled?: boolean;
   onAddSourceValue?: (destId: string, sourceValue: string) => void;
   onRemoveSourceValue?: (destId: string, sourceValue: string) => void;
 }

 export function LookupMappingTable({
   groups,
   unmappedRowCount,
   editingEnabled,
   onAddSourceValue,
   onRemoveSourceValue,
 }: LookupMappingTableProps) {
+  const [addingDestId, setAddingDestId] = useState<string | null>(null);
+  const [newSourceValue, setNewSourceValue] = useState("");
+
+  const handleStartAdd = (destId: string) => {
+    setAddingDestId(destId);
+    setNewSourceValue("");
+  };
+
+  const handleCancelAdd = () => {
+    setAddingDestId(null);
+    setNewSourceValue("");
+  };
+
+  const handleConfirmAdd = (destId: string) => {
+    if (newSourceValue.trim() && onAddSourceValue) {
+      onAddSourceValue(destId, newSourceValue.trim());
+    }
+    handleCancelAdd();
+  };
```

Note: add `import { useState } from "react";` at the top of the file (it's currently a plain `"use client"` component with no hooks).

---

### Step 2: Tighten Item Delete `×` Styling in `LookupMappingTable.tsx`

**File**: [web/components/projects/LookupMappingTable.tsx](file:///Users/vjkotra/projects/katana/web/components/projects/LookupMappingTable.tsx)

Destination label cell is unchanged — no delete control is added there. Only the existing item-delete button's className is tightened to exact parity with the table-mapping `×` buttons in `ReviewGrid.tsx`, and the add flow becomes the inline form:

```diff
               {group.sourceValues.map((srcVal, idx) => (
                 <div key={`${group.destId}-sv-${idx}`} className="flex items-center gap-2">
                   <input
                     type="text"
                     readOnly={!editingEnabled}
                     value={srcVal}
-                    className="px-2.5 py-1 text-sm border rounded bg-slate-50 border-slate-200 text-slate-800 focus:outline-none focus:bg-white focus:border-indigo-500 w-full max-w-sm"
+                    className="px-2.5 py-1 text-sm border rounded bg-slate-50 border-slate-200 text-slate-800 focus:outline-none focus:bg-white focus:border-indigo-500 w-full max-w-sm font-mono"
                   />
                   {editingEnabled && onRemoveSourceValue && group.destId && (
                     <button
                       type="button"
                       onClick={() => onRemoveSourceValue(group.destId, srcVal)}
-                      className="text-slate-400 hover:text-red-500 p-1 font-bold text-xs"
+                      className="text-slate-400 hover:text-red-600 focus:outline-none text-xs font-bold leading-none p-1 transition-colors"
                       title="Remove source value"
                     >
                       ×
                     </button>
                   )}
                 </div>
               ))}
               {editingEnabled && onAddSourceValue && group.destId && (
                 addingDestId === group.destId ? (
                   <div className="flex items-center gap-2 mt-1">
                     <input
                       type="text"
                       autoFocus
                       value={newSourceValue}
                       onChange={(e) => setNewSourceValue(e.target.value)}
                       onKeyDown={(e) => {
                         if (e.key === "Enter") handleConfirmAdd(group.destId);
                         if (e.key === "Escape") handleCancelAdd();
                       }}
                       placeholder="Enter source value alias..."
                       className="px-2.5 py-1 text-xs border border-indigo-300 rounded bg-white text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500 w-full max-w-xs font-mono"
                     />
                     <button
                       type="button"
                       onClick={() => handleConfirmAdd(group.destId)}
                       disabled={!newSourceValue.trim()}
                       className="px-2 py-1 text-xs font-semibold rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                     >
                       Add
                     </button>
                     <button
                       type="button"
                       onClick={handleCancelAdd}
                       className="px-1.5 py-1 text-xs font-medium text-slate-500 hover:text-slate-700"
                     >
                       Cancel
                     </button>
                   </div>
                 ) : (
                   <button
                     type="button"
                     onClick={() => handleStartAdd(group.destId)}
                     className="text-xs text-indigo-600 font-medium hover:text-indigo-800 self-start mt-1 flex items-center gap-1"
                   >
                     + Add another source value
                   </button>
                 )
               )}
             </div>
           </td>
```

---

### Step 3: Add Component Unit Tests in `LookupMappingTable.test.tsx`

**File**: [web/components/projects/__tests__/LookupMappingTable.test.tsx](file:///Users/vjkotra/projects/katana/web/components/projects/__tests__/LookupMappingTable.test.tsx)

```typescript
  it("opens inline add form when + Add another source value is clicked", () => {
    const onAddSourceValue = vi.fn();
    render(<LookupMappingTable groups={groups} editingEnabled onAddSourceValue={onAddSourceValue} />);

    const addButtons = screen.getAllByText("+ Add another source value");
    fireEvent.click(addButtons[0]);

    const input = screen.getByPlaceholderText("Enter source value alias...");
    expect(input).toBeInTheDocument();

    fireEvent.change(input, { target: { value: "NEW_ALIAS" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onAddSourceValue).toHaveBeenCalledWith("ACTIVE", "NEW_ALIAS");
  });

  it("closes inline add form without calling onAddSourceValue when Escape is pressed", () => {
    const onAddSourceValue = vi.fn();
    render(<LookupMappingTable groups={groups} editingEnabled onAddSourceValue={onAddSourceValue} />);

    fireEvent.click(screen.getAllByText("+ Add another source value")[0]);
    const input = screen.getByPlaceholderText("Enter source value alias...");
    fireEvent.change(input, { target: { value: "DRAFT_ALIAS" } });
    fireEvent.keyDown(input, { key: "Escape" });

    expect(onAddSourceValue).not.toHaveBeenCalled();
    expect(screen.queryByPlaceholderText("Enter source value alias...")).not.toBeInTheDocument();
  });
```

---

## Verification Plan

```bash
cd web && npm test -- --run components/projects/__tests__/LookupMappingTable.test.tsx
```
