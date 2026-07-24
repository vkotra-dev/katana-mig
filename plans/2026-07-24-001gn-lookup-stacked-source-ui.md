# Plan: Task 001gn — Component-Level Stacked Source Upsert & Delete Controls in LookupMappingTable

- **Task**: [001gn-lookup-stacked-source-ui.md](file:///Users/vjkotra/projects/katana/tasks/001gn-lookup-stacked-source-ui.md)

---

## Goal Description

Refactor `LookupMappingTable.tsx` on the Review Page to provide a destination-anchored stacked source upsert interface with exact visual parity (`×` buttons) matching table mapping fibers (Task 001eq).

```
+----------------------------------+--------------------------------------+------------+
| Destination (Anchor)             | Mapped Source Values (Stacked)       | Status     |
+----------------------------------+--------------------------------------+------------+
| Blocked (BLOCKED)            [×] | ['B']                         [×]    | Pending    |
|                                  | ['BLOCKED']                   [×]    |            |
|                                  | + Add source value                   |            |
+----------------------------------+--------------------------------------+------------+
```

---

## Step-by-Step Build Instructions (Agent Executable)

---

### Step 1: Add `onDeleteGroup` and Inline Add Form State in `LookupMappingTable.tsx`

**File**: [web/components/projects/LookupMappingTable.tsx](file:///Users/vjkotra/projects/katana/web/components/projects/LookupMappingTable.tsx)

```diff
 interface LookupMappingTableProps {
   groups: DestinationMappingGroup[];
   unmappedRowCount?: number;
   editingEnabled?: boolean;
   onAddSourceValue?: (destId: string, sourceValue: string) => void;
   onRemoveSourceValue?: (destId: string, sourceValue: string) => void;
+  onDeleteGroup?: (destId: string) => void;
 }

 export function LookupMappingTable({
   groups,
   unmappedRowCount,
   editingEnabled,
   onAddSourceValue,
   onRemoveSourceValue,
+  onDeleteGroup,
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

---

### Step 2: Render Group Delete `×` and Item Delete `×` in `LookupMappingTable.tsx`

**File**: [web/components/projects/LookupMappingTable.tsx](file:///Users/vjkotra/projects/katana/web/components/projects/LookupMappingTable.tsx)

```diff
       {groups.map((group, groupIdx) => (
         <tr key={`${group.destId || 'empty'}-${groupIdx}`} className="hover:bg-slate-50/50 group">
           <td className="py-2.5 pr-4">
+            <div className="flex items-center justify-between gap-2">
               <div>
                 {group.destLabel && group.destLabel !== group.destId ? (
                   <>
                     {group.destLabel}{" "}
                     <span className="text-slate-400">({group.destId})</span>
                   </>
                 ) : (
                   group.destId || "—"
                 )}
               </div>
+              {editingEnabled && onDeleteGroup && group.destId && (
+                <button
+                  type="button"
+                  onClick={() => onDeleteGroup(group.destId)}
+                  className="text-slate-400 hover:text-red-600 focus:outline-none text-xs font-bold leading-none p-1 transition-colors opacity-0 group-hover:opacity-100"
+                  title="Delete destination group"
+                >
+                  ×
+                </button>
+              )}
+            </div>
           </td>
           <td className="py-2.5">
             <div className="flex flex-col gap-1.5 w-full">
               {group.sourceValues.map((srcVal, idx) => (
                 <div key={`${group.destId}-sv-${idx}`} className="flex items-center gap-2">
                   <input
                     type="text"
                     readOnly={!editingEnabled}
                     value={srcVal}
                     className="px-2.5 py-1 text-sm border rounded bg-slate-50 border-slate-200 text-slate-800 focus:outline-none focus:bg-white focus:border-indigo-500 w-full max-w-sm font-mono"
                   />
                   {editingEnabled && onRemoveSourceValue && group.destId && (
                     <button
                       type="button"
                       onClick={() => onRemoveSourceValue(group.destId, srcVal)}
                       className="text-slate-400 hover:text-red-600 focus:outline-none text-xs font-bold leading-none p-1 transition-colors"
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
  it("renders row delete '×' button when onDeleteGroup is provided", () => {
    const onDeleteGroup = vi.fn();
    render(<LookupMappingTable groups={groups} editingEnabled onDeleteGroup={onDeleteGroup} />);

    const groupDeleteButtons = screen.getAllByTitle("Delete destination group");
    expect(groupDeleteButtons.length).toBe(2);
    fireEvent.click(groupDeleteButtons[0]);
    expect(onDeleteGroup).toHaveBeenCalledWith("ACTIVE");
  });

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
```

---

## Verification Plan

```bash
cd web && npm test -- --run components/projects/__tests__/LookupMappingTable.test.tsx
```
