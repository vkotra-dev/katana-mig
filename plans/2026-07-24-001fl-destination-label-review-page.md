# Plan: Task 001fl — Fix Destination Value Column Showing Raw ID

- **Task**: [001fl-destination-label-review-page.md](file:///Users/vjkotra/projects/katana/tasks/001fl-destination-label-review-page.md)

---

## Goal Description

The Review Page (`/projects/[id]/feeds/[feedId]/review`) "Destination Value (ID)" column currently displays raw values like `2`, `4`, or UUIDs like `6f24684f-c1af-49e9-9cc3-437358a40783` without human-readable labels.

The goal is to ensure mapped destination values display as `Paid (2)` or `Active (ACTIVE)`, showing human-readable labels first with the ID in parentheses.

---

## Step-by-Step Build Instructions (Agent Executable)

---

### Step 1: Widen fallback label extractor in `review/page.tsx`

**File**: [web/app/projects/[id]/feeds/[feedId]/review/page.tsx](file:///Users/vjkotra/projects/katana/web/app/projects/%5Bid%5D/feeds/%5BfeedId%5D/review/page.tsx)  
**Lines**: 455–475

#### Exact Code Diff to Apply:

```diff
         let destinationMappings = latestMap?.destinationMappings ?? [];
         // For approved maps without destinationMappings (legacy), fall back to pairs
         if (destinationMappings.length === 0 && latestMap) {
+          const extractDestLabel = (row: Record<string, unknown>): string => {
+            for (const key of ["label", "name", "description", "desc", "val", "value", "display"]) {
+              const v = row[key];
+              if (typeof v === "string" && v.trim()) return v.trim();
+            }
+            for (const [k, v] of Object.entries(row)) {
+              const kl = k.toLowerCase();
+              if (["label", "name", "desc", "display"].some((s) => kl.includes(s)) && typeof v === "string" && v.trim())
+                return v.trim();
+            }
+            return "";
+          };
+
           destinationMappings = Object.entries(latestMap.sourceValueMap)
             .filter(([, destId]) => destId && destId.trim())
             .map(([srcVal, destId]) => {
               const destRow = latestMap.destinationTable.find((row: Record<string, unknown>) => {
                 const rowId = (row as any).id ?? (row as any).destination_id;
                 return String(rowId ?? "") === String(destId);
               });
-              const destLabel = destRow
-                ? ((destRow as any).name ?? (destRow as any).value ?? "")
-                : "";
+              const destLabel = destRow ? extractDestLabel(destRow) : "";
               return {
                 destId,
                 destLabel,
                 destRow: destRow || {},
                 sourceValues: [srcVal],
                 status: isConfirmed ? "approved" : "draft",
               };
             });
         }
```

---

### Step 2: Update Table Header in `LookupMappingTable.tsx`

**File**: [web/components/projects/LookupMappingTable.tsx](file:///Users/vjkotra/projects/katana/web/components/projects/LookupMappingTable.tsx)  
**Line**: 55

#### Exact Code Diff to Apply:

```diff
       <table className="w-full border-collapse text-left text-xs">
         <thead>
           <tr className="border-b border-slate-100 pb-2 text-slate-400 font-semibold uppercase tracking-wider">
-            <th className="py-2 w-1/3">Destination Value (ID)</th>
+            <th className="py-2 w-1/3">Destination</th>
             <th className="py-2 w-1/2">Mapped Source Values</th>
             <th className="py-2 w-1/6">Status</th>
           </tr>
         </thead>
```

---

### Step 3: Run Vitest Unit Tests

Execute the Vitest suite in `web/`:

```bash
cd /Users/vjkotra/projects/katana/web && npm test -- --run components/projects/__tests__/LookupMappingTable.test.tsx
```

---

## Verification Plan

### Automated Tests

```bash
cd web && npm test -- --run
```

Expected: All frontend tests pass.

### Manual Verification

1. Navigate to `/projects/[id]/feeds/[feedId]/review`.
2. Inspect the Lookup Mapping grid under the "Lookup Value Mappings" section.
3. Confirm mapped rows show `Paid (2)` instead of raw `2`.
4. Confirm column header shows `Destination`.
