# Plan: 001cc — Feed Slice Approval Data Profile + PII Scan

- **Task Link:** [tasks/001cc-feed-slice-approval-data-profile.md](../tasks/001cc-feed-slice-approval-data-profile.md)

## Current State

`web/app/projects/[id]/feeds/[feedId]/page.tsx`:
- When `latestSlice.status === "pending_approval"`: shows amber banner + renders the preview table in the slice panel (labelled "Masked Data Preview")
- When `latestSlice.status === "rejected"`: shows red banner + replacement upload; preview table still visible
- Approve/reject API functions (`approveFeedSlice`, `rejectFeedSlice`) exist in `feeds-api.ts` but no approve/reject UI exists in the feed workspace for `project_stakeholder`
- Preview table uses `.split(",")` — broken for quoted CSV fields

## Objective

1. Hide all data preview when the slice is `pending_approval` or `rejected`
2. For `project_stakeholder`, surface a meaningful approval card with computed stats, PII scan, and unmasked data in place of the current hollow amber banner
3. Make the approval step the first time anyone sees the data — giving it real review value

## Blast Radius

Single file: `web/app/projects/[id]/feeds/[feedId]/page.tsx`

Helper import: `splitCsvRow` from `web/lib/csv-utils.ts` (already exists)

## File Changes

### `web/app/projects/[id]/feeds/[feedId]/page.tsx`

---

#### Step 1 — PII scan helper (add near top of file, outside component)

```ts
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const SSN_RE = /^\d{3}-?\d{2}-?\d{4}$/;
const CARD_RE = /^\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}$/;
const PHONE_RE = /^\+?[\d\s\-().]{7,15}$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$|^\d{2}\/\d{2}\/\d{4}$/;

type PiiLevel = "pii" | "possible" | "clean";

function scanColumnPii(values: string[]): PiiLevel {
  const filled = values.filter((v) => v.trim().length > 0);
  if (filled.length === 0) return "clean";

  const strongHits = filled.filter(
    (v) => EMAIL_RE.test(v) || SSN_RE.test(v) || CARD_RE.test(v)
  ).length;
  if (strongHits / filled.length > 0.6) return "pii";

  const softHits = filled.filter(
    (v) => PHONE_RE.test(v) || DATE_RE.test(v)
  ).length;
  if (softHits / filled.length > 0.3) return "possible";

  return "clean";
}

function piiLabel(level: PiiLevel): { icon: string; className: string; text: string } {
  if (level === "pii") return { icon: "🔴", className: "text-red-600", text: "PII" };
  if (level === "possible") return { icon: "⚠️", className: "text-amber-600", text: "Possible PII" };
  return { icon: "✅", className: "text-emerald-600", text: "Clean" };
}
```

---

#### Step 2 — Stats + PII computation (inside component, derived from `latestSlice`)

```ts
const approvalProfile = useMemo(() => {
  if (!latestSlice || latestSlice.status !== "pending_approval") return null;

  const headers = latestSlice.headerCsv
    ? splitCsvRow(latestSlice.headerCsv)
    : [];
  const rows = (latestSlice.previewRows ?? []).map((r) => splitCsvRow(r));

  const blankColumns = headers.filter((_, colIdx) =>
    rows.every((row) => !row[colIdx]?.trim())
  );

  const columnPii: PiiLevel[] = headers.map((_, colIdx) =>
    scanColumnPii(rows.map((row) => row[colIdx] ?? ""))
  );

  return { headers, rows, blankColumns, columnPii };
}, [latestSlice]);
```

---

#### Step 3 — Approval state + handlers

Add state:
```ts
const [rejectionReason, setRejectionReason] = useState("");
const [approvalLoading, setApprovalLoading] = useState<"approve" | "reject" | null>(null);
const [approvalError, setApprovalError] = useState<string | null>(null);
```

Add handlers:
```ts
const handleApproveSlice = async () => {
  if (!session || !routeParams || !latestSlice) return;
  setApprovalLoading("approve");
  setApprovalError(null);
  try {
    await approveFeedSlice(session.accessToken, routeParams.id, feedId, latestSlice.sourceSliceId);
    const refreshed = await listFeedSlices(session.accessToken, routeParams.id, feedId);
    setSlices(refreshed);
  } catch (e) {
    setApprovalError(e instanceof Error ? e.message : "Approval failed.");
  } finally {
    setApprovalLoading(null);
  }
};

const handleRejectSlice = async () => {
  if (!session || !routeParams || !latestSlice || !rejectionReason.trim()) return;
  setApprovalLoading("reject");
  setApprovalError(null);
  try {
    await rejectFeedSlice(
      session.accessToken, routeParams.id, feedId,
      latestSlice.sourceSliceId, rejectionReason.trim()
    );
    const refreshed = await listFeedSlices(session.accessToken, routeParams.id, feedId);
    setSlices(refreshed);
    setRejectionReason("");
  } catch (e) {
    setApprovalError(e instanceof Error ? e.message : "Rejection failed.");
  } finally {
    setApprovalLoading(null);
  }
};
```

---

#### Step 4 — Replace amber banner with approval card (for `project_stakeholder`)

Replace the existing `pending_approval` banner block:

```tsx
{!loading && latestSlice?.status === "pending_approval" && role === "project_stakeholder" && approvalProfile && (
  <div className="rounded-2xl border border-amber-300 bg-amber-50 p-6 space-y-6">
    <div>
      <h3 className="text-base font-bold text-slate-900">Review & Approve Feed Data</h3>
      <p className="text-xs text-slate-500 mt-1">Based on preview sample ({approvalProfile.rows.length} rows shown)</p>
    </div>

    {/* Stats strip */}
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {[
        { label: "Columns", value: approvalProfile.headers.length },
        { label: "Total Rows", value: latestSlice.rowCount },
        { label: "Preview Rows", value: approvalProfile.rows.length },
        { label: "Blank Columns", value: approvalProfile.blankColumns.length, alert: approvalProfile.blankColumns.length > 0 },
      ].map(({ label, value, alert }) => (
        <div key={label} className={`rounded-xl border p-3 text-center ${alert ? "border-amber-300 bg-amber-100" : "border-outline-variant bg-white"}`}>
          <div className={`text-xl font-bold ${alert ? "text-amber-700" : "text-slate-900"}`}>{value}</div>
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mt-0.5">{label}</div>
        </div>
      ))}
    </div>

    {/* PII scan results */}
    <div>
      <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">PII Scan</div>
      <div className="flex flex-wrap gap-2">
        {approvalProfile.headers.map((col, i) => {
          const badge = piiLabel(approvalProfile.columnPii[i]);
          return (
            <span key={col} className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${badge.className}`}>
              {badge.icon} {col}
            </span>
          );
        })}
      </div>
      {approvalProfile.blankColumns.length > 0 && (
        <p className="mt-2 text-xs text-amber-700">
          Blank columns: {approvalProfile.blankColumns.join(", ")}
        </p>
      )}
    </div>

    {/* Unmasked sample data table */}
    <div>
      <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Sample Data</div>
      <div className="max-h-64 overflow-auto rounded-xl border border-outline-variant bg-white">
        <table className="text-left text-[10px] border-collapse font-mono w-full">
          <thead className="bg-slate-50 border-b border-outline-variant sticky top-0">
            <tr>
              {approvalProfile.headers.map((col, i) => {
                const badge = piiLabel(approvalProfile.columnPii[i]);
                return (
                  <th key={i} className="px-3 py-2 font-bold text-slate-700 whitespace-nowrap">
                    <span className={badge.className}>{badge.icon}</span> {col}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {approvalProfile.rows.map((cells, rowIdx) => (
              <tr key={rowIdx} className="hover:bg-slate-50/50">
                {approvalProfile.headers.map((_, colIdx) => {
                  const val = cells[colIdx] ?? "";
                  const blank = !val.trim();
                  return (
                    <td key={colIdx} className={`px-3 py-1.5 whitespace-nowrap ${blank ? "bg-amber-50 text-amber-400 italic" : "text-slate-600"}`}>
                      {blank ? "—" : val}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>

    {/* Approve / Reject */}
    {approvalError && (
      <p className="text-xs text-red-600">{approvalError}</p>
    )}
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
      <button
        type="button"
        onClick={handleApproveSlice}
        disabled={approvalLoading !== null}
        className="rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
      >
        {approvalLoading === "approve" ? "Approving…" : "Approve"}
      </button>
      <div className="flex flex-1 flex-col gap-1.5">
        <input
          type="text"
          placeholder="Rejection reason (required to reject)"
          value={rejectionReason}
          onChange={(e) => setRejectionReason(e.target.value)}
          className="rounded-lg border border-outline-variant px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400"
        />
        <button
          type="button"
          onClick={handleRejectSlice}
          disabled={!rejectionReason.trim() || approvalLoading !== null}
          className="rounded-xl border border-red-300 px-5 py-2 text-sm font-semibold text-red-600 hover:bg-red-50 disabled:opacity-40 self-start"
        >
          {approvalLoading === "reject" ? "Rejecting…" : "Reject"}
        </button>
      </div>
    </div>
  </div>
)}

{/* Plain banner for non-stakeholder roles when pending */}
{!loading && latestSlice?.status === "pending_approval" && role !== "project_stakeholder" && (
  <div role="alert" className="rounded-xl border border-amber-400/30 bg-amber-50 px-4 py-3 text-sm text-amber-800">
    Source data is pending approval — field mapping analysis will be available once approved.
  </div>
)}
```

---

#### Step 5 — Remove preview table from slice panel when `pending_approval` or `rejected`

In the slice panel, gate the preview table block:
```tsx
{/* Preview Table — only shown after approval */}
{latestSlice.status === "approved" && (latestSlice.previewRows || []).length > 0 && (
  // ...existing preview table...
)}
```

Also fix the preview table to use `splitCsvRow` instead of `.split(",")`.

---

#### Step 6 — Add `approveFeedSlice` / `rejectFeedSlice` to imports

Both already exist in `feeds-api.ts`. Add to the import block at the top of the page.

## Pitfalls

- `approvalProfile` is memoised — recomputes only when `latestSlice` changes, not on every render
- `scanColumnPii` skips empty values when computing hit rates — a column that's 90% blank and 10% email should still flag as PII
- `rejectFeedSlice` signature: verify the param order in `feeds-api.ts` before coding (`token, projectId, feedId, sliceId, reason`)
- After approve/reject, `setSlices(refreshed)` triggers the `latestSlice` derivation — approval card disappears automatically as status changes
- The plain banner for non-stakeholder roles when pending is still needed so `central_team` knows the status

## Verification

1. Upload a feed as operator → feed workspace shows no preview data, just metadata + amber banner
2. Log in as `project_stakeholder` → approval card renders with stats strip, PII badges, unmasked table, approve/reject controls
3. Column with email addresses → 🔴 PII badge
4. Column with all blanks → amber count in stats strip, amber cell highlighting in table
5. Reject with empty reason → reject button stays disabled
6. Approve → slice transitions to `approved`, full workspace opens, preview table now visible
7. Reject with reason → rejection banner appears with replacement upload
8. TypeScript compiles cleanly

## Commit

- `feat(001cc): gate feed slice preview behind approval; add data profile and PII scan for approvers`
