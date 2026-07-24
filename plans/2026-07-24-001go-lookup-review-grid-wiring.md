# Plan: Task 001go — End-to-End Prop Wiring for Lookup Mapping Actions in ReviewGrid and Review Page

- **Task**: [001go-lookup-review-grid-wiring.md](file:///Users/vjkotra/projects/katana/tasks/001go-lookup-review-grid-wiring.md)

---

## Goal Description

Wire lookup mapping action handlers (`onAddSourceValue`, `onRemoveSourceValue`, `onDeleteDestinationGroup`) from the Review Page through `ReviewGrid.tsx` into `LookupMappingTable.tsx`.

---

## Step-by-Step Build Instructions (Agent Executable)

---

### Step 1: Update `ReviewGridProps` and `<LookupMappingTable>` Invocation in `ReviewGrid.tsx`

**File**: [web/components/projects/ReviewGrid.tsx](file:///Users/vjkotra/projects/katana/web/components/projects/ReviewGrid.tsx)

```diff
 interface ReviewGridProps {
   mappingTables: MappingTableRecord[];
   lookupGroups: LookupValueGroup[];
+  onAddSourceValue?: (lookupName: string, destId: string, sourceValue: string) => void;
+  onRemoveSourceValue?: (lookupName: string, destId: string, sourceValue: string) => void;
+  onDeleteDestinationGroup?: (lookupName: string, destId: string) => void;
```

```diff
                 <LookupMappingTable
                   groups={group.destinationMappings ?? []}
                   unmappedRowCount={group.unmappedRowCount}
                   editingEnabled={editingEnabled}
+                  onAddSourceValue={onAddSourceValue ? (destId, sourceValue) => onAddSourceValue(group.lookupName, destId, sourceValue) : undefined}
+                  onRemoveSourceValue={onRemoveSourceValue ? (destId, sourceValue) => onRemoveSourceValue(group.lookupName, destId, sourceValue) : undefined}
+                  onDeleteGroup={onDeleteDestinationGroup ? (destId) => onDeleteDestinationGroup(group.lookupName, destId) : undefined}
                 />
```

---

### Step 2: Implement Handlers & Pass Props in `review/page.tsx`

**File**: [web/app/projects/[id]/feeds/[feedId]/review/page.tsx](file:///Users/vjkotra/projects/katana/web/app/projects/%5Bid%5D/feeds/%5BfeedId%5D/review/page.tsx)

```typescript
  const handleDeleteDestinationGroup = async (lookupValueMapId: string, destId: string) => {
    if (!session) return;
    const map = lookupMaps.find(m => m.lookupValueMapId === lookupValueMapId);
    if (!map) return;
    try {
      const updatedMappings = (map.destinationMappings || []).filter(g => g.destId !== destId);
      await patchLookupValueMap(session.accessToken, projectId, lookupValueMapId, {
        destinationMappings: updatedMappings,
      });
      await loadData(session.accessToken);
      setNotice(`Deleted destination group "${destId}".`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete destination group.");
    }
  };

  const handleDeleteDestinationGroupByLookup = async (lookupName: string, destId: string) => {
    const map = lookupMaps.find(m => m.lookupName === lookupName);
    if (map?.lookupValueMapId) {
      await handleDeleteDestinationGroup(map.lookupValueMapId, destId);
    }
  };
```

Pass into `<ReviewGrid>`:

```diff
                       lookupGroups={lookupGroups}
+                      onAddSourceValue={handleAddSourceByLookup}
+                      onRemoveSourceValue={handleRemoveSourceByLookup}
+                      onDeleteDestinationGroup={handleDeleteDestinationGroupByLookup}
```

---

## Verification Plan

```bash
cd web && npm test -- --run
```
