# Plan: 001bs — Review Page Sample Data Context

- **Task Link:** [tasks/001bs-review-page-sample-data.md](../tasks/001bs-review-page-sample-data.md)
- **Domain Link:** [docs/domain/ui.md](../docs/domain/ui.md)

## Current State

The review page at `/projects/[id]/feeds/[feedId]/review` fetches mapping snapshots and renders field binding pairs in a `ReviewGrid`. `FeedSliceRecord` (from `listFeedSlices`) already carries:
- `headerCsv: string | null` — comma-separated column names (e.g. `"CUST_ID,SURNAME,DOB"`)
- `previewRows: string[]` — up to N masked CSV row strings

The review page does not currently call `listFeedSlices` or show any source data.

## Objective

Parse the latest approved `FeedSlice` on the review page and show 2–3 sample values per source field in the binding table so business users have evidence to approve against.

## Out of Scope

- Backend changes — `listFeedSlices` already exists and returns sufficient data
- Destination field sample values
- Lookup value mapping sample display

## Blast Radius

| Layer | Files |
|---|---|
| Review page | `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` |
| Shared component | `web/components/projects/ReviewGrid.tsx` |

## File Changes

### `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`

**Step 1 — Imports**

Add `listFeedSlices` from `@/lib/feeds-api`.

**Step 2 — State**

```ts
const [sampleValues, setSampleValues] = useState<Record<string, string[]>>({});
```

**Step 3 — `loadData` — fetch and parse slice**

After fetching snapshots and lookup maps, add:

```ts
const slices = await listFeedSlices(token, projectId, feedId);
const approvedSlice = slices
  .filter((s) => s.status === "approved")
  .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())[0];

if (approvedSlice?.headerCsv && approvedSlice.previewRows.length > 0) {
  const headers = splitCsvRow(approvedSlice.headerCsv).map((h) => h.trim());
  const parsed: Record<string, string[]> = {};

  for (const rowCsv of approvedSlice.previewRows.slice(0, 5)) {
    const cells = splitCsvRow(rowCsv);
    headers.forEach((col, i) => {
      const val = (cells[i] ?? "").trim();
      if (val) {
        const key = col.toLowerCase();
        if (!parsed[key]) parsed[key] = [];
        if (parsed[key].length < 3) parsed[key].push(val);
      }
    });
  }
  setSampleValues(parsed);
}
```

Add the CSV helper at module scope (handles quoted fields containing commas):
```ts
function splitCsvRow(row: string): string[] {
  return row.split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/).map((v) => v.replace(/^"|"$/g, ""));
}
```

> The `parsed` map is keyed by lowercased column name for case-insensitive lookup downstream.

**Step 4 — Pass `sampleValues` into `<ReviewGrid />`**

`ReviewGrid` is the shared component at `web/components/projects/ReviewGrid.tsx`. The binding rows are rendered inside it, so `sampleValues` must be passed as a prop.

In `page.tsx` JSX:
```tsx
<ReviewGrid
  mappingTables={...}
  lookupGroups={...}
  onApprove={...}
  onRequestRevision={...}
  sampleValues={sampleValues}
/>
```

### `web/components/projects/ReviewGrid.tsx`

**Step 5 — Extend `ReviewGridProps`**

```ts
interface ReviewGridProps {
  mappingTables: MappingTableRecord[];
  lookupGroups: LookupValueGroup[];
  onApprove?: () => void;
  onRequestRevision?: (comment: string) => void;
  sampleValues?: Record<string, string[]>;   // add this
}
```

Destructure in the function signature:
```ts
export function ReviewGrid({
  mappingTables,
  lookupGroups,
  onApprove,
  onRequestRevision,
  sampleValues = {},
}: ReviewGridProps) {
```

**Step 6 — Render chips in the source field cell**

In the binding row map (currently at line ~153 in ReviewGrid.tsx), replace the plain `sourceField` cell:

```tsx
// before
<td className="py-2.5 font-mono text-slate-700">{binding.sourceField}</td>

// after
<td className="py-2.5">
  <span className="font-mono text-slate-700">{binding.sourceField}</span>
  {(() => {
    const samples = sampleValues[binding.sourceField.toLowerCase()] ?? [];
    return samples.length > 0 ? (
      <div className="mt-0.5 flex flex-wrap gap-1">
        {samples.map((v, i) => (
          <span
            key={i}
            className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500 font-mono"
          >
            {v}
          </span>
        ))}
      </div>
    ) : null;
  })()}
</td>
```

**Step 7 — Guard for no slice or no header**

The `if (approvedSlice?.headerCsv && ...)` guard in `page.tsx` covers the null case. If `sampleValues` is `{}`, the per-binding lookup returns `[]` and no chips render — ReviewGrid degrades cleanly.

## Pitfalls

- **CSV quoting:** The `splitCsvRow` helper uses `split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/)` to handle quoted fields containing commas (e.g. `"Smith, Jr."`). The regex counts unescaped quote pairs to split only on unquoted commas. It then strips leading/trailing quotes from each cell.
- **`headerCsv` null:** Already guarded above — `approvedSlice?.headerCsv` short-circuits.
- **No approved slice:** `approvedSlice` is `undefined` → the `if` block is skipped → `sampleValues` stays `{}` → no chips render.
- **Case mismatch:** Binding `sourceField` values come from the AI analysis which reads column names from the slice header. They should match exactly. The `.toLowerCase()` lookup is a safety net.
- **Performance:** `listFeedSlices` is one extra network call on review page load. It's small (slice metadata + a handful of preview rows) — no pagination needed.

## Tests

No automated tests for the review page. Manual verification only.

## Verification

1. Navigate to `/projects/[id]/feeds/[feedId]/review` for a feed that has an approved slice
2. Each binding row's source field shows 1–3 muted sample value chips below the field name
3. Navigate to a feed with no approved slice (e.g. draft-only) — no chips, no crash
4. TypeScript compiles with no new errors

## Commit

- `feat(001bs): surface feed slice sample values on review page`
