# Plan: 001bv — Unmapped Source Fields Warning

- **Task Link:** [tasks/001bv-unmapped-source-fields-warning.md](../tasks/001bv-unmapped-source-fields-warning.md)
- **Domain Link:** [docs/domain/ui.md](../docs/domain/ui.md)

## Current State

**Review page** (`review/page.tsx`):
- `sampleValues: Record<string, string[]>` built from `headerCsv` + `previewRows` (001bs)
- `allMappingSnapshots: MappingSnapshotRecord[]` — each snapshot has `fieldBindings`
- `headerCsv` is available on the approved `FeedSlice` fetched in 001bs — but `allSourceColumns` is not stored in state, only `sampleValues` is

**Feed workspace** (`feeds/[feedId]/page.tsx`):
- `allMappingSnapshots` loaded on mount
- `slices` loaded; `latestSlice.headerCsv` is available

**ReviewGrid** (`components/projects/ReviewGrid.tsx`):
- Already receives `sampleValues?: Record<string, string[]>` (001bs)
- Renders per-table binding rows

No unmapped field computation exists anywhere.

## Objective

Compute the set of source columns with no binding across any destination table and render it as an amber informational panel on both the review page and the feed workspace.

## Blast Radius

| Layer | Files |
|---|---|
| Shared component | `web/components/projects/ReviewGrid.tsx` |
| Review page | `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` |
| Feed workspace | `web/app/projects/[id]/feeds/[feedId]/page.tsx` |

## File Changes

### Shared helper — define `computeUnmappedFields` (inline in each page or extract to a utility)

```ts
function computeUnmappedFields(
  headerCsv: string | null,
  allBindings: Array<{ sourceField: string }>,
): string[] {
  if (!headerCsv) return [];
  const headers = splitCsvRow(headerCsv).map((h) => h.trim().toLowerCase());
  const bound = new Set(allBindings.map((b) => b.sourceField.toLowerCase()));
  return headers.filter((h) => h && !bound.has(h));
}
```

> `splitCsvRow` is already defined in `review/page.tsx` (001bs). Either duplicate for the workspace or extract to `web/lib/csv-utils.ts`.

---

### `web/components/projects/ReviewGrid.tsx`

**Extend `ReviewGridProps`:**

```ts
interface ReviewGridProps {
  mappingTables: MappingTableRecord[];
  lookupGroups: LookupValueGroup[];
  onApprove?: () => void;
  onRequestRevision?: (comment: string) => void;
  sampleValues?: Record<string, string[]>;
  unmappedSourceFields?: string[];   // add this
}
```

Destructure with default `[]`:
```ts
export function ReviewGrid({
  ...
  unmappedSourceFields = [],
}: ReviewGridProps) {
```

**Render unmapped panel after the last table section, before lookup groups:**

```tsx
{unmappedSourceFields.length > 0 && (
  <div className="rounded-xl border border-amber-300/40 bg-amber-50 p-4 space-y-2">
    <p className="text-sm font-semibold text-amber-800">
      Unmapped source fields — data in these columns will not be migrated
    </p>
    <ul className="space-y-1">
      {unmappedSourceFields.map((col) => {
        const samples = sampleValues?.[col] ?? [];
        return (
          <li key={col} className="flex items-start gap-2">
            <span className="font-mono text-sm text-amber-900">{col}</span>
            {samples.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {samples.map((v, i) => (
                  <span
                    key={i}
                    className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-mono text-amber-700"
                  >
                    {v}
                  </span>
                ))}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  </div>
)}
```

---

### `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`

**Step 1 — Store `allSourceColumns` in state**

In the `loadData` function, where `approvedSlice` is already found (001bs), also capture the header columns:

```ts
const headerColumns = approvedSlice?.headerCsv
  ? splitCsvRow(approvedSlice.headerCsv).map((h) => h.trim())
  : [];
// store so we can compute unmapped fields after snapshots load
setAllSourceColumns(headerColumns);
```

Add state:
```ts
const [allSourceColumns, setAllSourceColumns] = useState<string[]>([]);
```

**Step 2 — Compute `unmappedSourceFields` before render**

```ts
const allBoundFields = allMappingSnapshots.flatMap((s) => s.fieldBindings);
const unmappedSourceFields = computeUnmappedFields(
  allSourceColumns.join(","),   // rejoin for the helper, or adapt helper to accept string[]
  allBoundFields,
);
```

Simpler: adapt `computeUnmappedFields` to accept `string[]` directly:

```ts
function computeUnmappedFields(
  headerColumns: string[],
  allBindings: Array<{ sourceField: string }>,
): string[] {
  const bound = new Set(allBindings.map((b) => b.sourceField.toLowerCase()));
  return headerColumns
    .map((h) => h.trim())
    .filter((h) => h && !bound.has(h.toLowerCase()));
}
```

**Step 3 — Pass to ReviewGrid**

```tsx
<ReviewGrid
  mappingTables={mappingTables}
  lookupGroups={lookupGroups}
  onApprove={...}
  onRequestRevision={...}
  sampleValues={sampleValues}
  unmappedSourceFields={unmappedSourceFields}   // add
/>
```

---

### `web/app/projects/[id]/feeds/[feedId]/page.tsx`

**Step 1 — Compute unmapped fields from `latestSlice` + loaded snapshots**

In the JSX (derived value, no extra state needed):

```ts
const allBoundFields = allMappingSnapshots.flatMap((s) => s.fieldBindings ?? []);
const unmappedSourceFields =
  latestSlice?.headerCsv && allMappingSnapshots.length > 0
    ? computeUnmappedFields(
        splitCsvRow(latestSlice.headerCsv).map((h) => h.trim()),
        allBoundFields,
      )
    : [];
```

**Step 2 — Render in the Field Mappings section**

Below the table accordions (after the "Submit for review" button), add:

```tsx
{unmappedSourceFields.length > 0 && (
  <div className="rounded-xl border border-amber-300/40 bg-amber-50 p-4 mt-4 space-y-2">
    <p className="text-sm font-semibold text-amber-800">
      Unmapped source fields — data in these columns will not be migrated
    </p>
    <ul className="flex flex-wrap gap-2">
      {unmappedSourceFields.map((col) => (
        <li key={col} className="font-mono text-xs text-amber-900 rounded bg-amber-100 px-2 py-1">
          {col}
        </li>
      ))}
    </ul>
  </div>
)}
```

> The workspace version is compact (chips only, no sample values) since the operator already knows the data. The review page version (via ReviewGrid) shows sample values since business users need the evidence.

## Pitfalls

- `splitCsvRow` is defined in `review/page.tsx` — either duplicate for workspace or extract to `web/lib/csv-utils.ts`. Extracting is cleaner and avoids the duplication pitfall flagged in 001bs.
- `allMappingSnapshots.length === 0` means no analysis has run — skip computation entirely rather than showing all columns as unmapped.
- If `headerCsv` contains the column name `""` (blank) after split, filter it out.
- The `unmappedSourceFields` list is already lowercased for computation but should be displayed in their original casing from the header — store originals separately from the lowercased set.

## Tests

No automated tests for these pages. Manual verification only.

## Verification

1. Review page for a feed where some source columns have no binding → amber panel appears below binding tables listing unmapped columns with sample value chips
2. Review page where all source columns are bound → no amber panel shown
3. Feed workspace → compact amber chip list of unmapped columns appears below field mapping accordions
4. Approve/reject controls are unaffected by the presence of the warning
5. Feed with no approved slice → no warning panel (guard works)
6. TypeScript compiles with no new errors

## Commit

- `feat(001bv): show informational warning for unmapped source fields on review and workspace pages`
