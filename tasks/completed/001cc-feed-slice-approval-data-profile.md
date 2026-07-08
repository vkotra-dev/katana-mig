# Task 001cc — Feed Slice Approval Data Profile + PII Scan

**Plan:** `plans/2026-07-08-001cc-feed-slice-approval-data-profile.md`

## Context

The feed slice approval step gates AI mapping — nothing can proceed until a business user approves the uploaded file. Currently the approval step is hollow: the approver sees a banner and no data, making the approval a rubber stamp. Meanwhile the feed workspace already shows a "Masked Data Preview" table even before approval, which leaks the data shape without any review value.

## Scope

**Frontend only. No backend changes. All computed from existing `FeedSliceRecord` (`headerCsv` + `previewRows` + `rowCount`).**

### 1. Gate the preview in the feed workspace

Remove the "Masked Data Preview" table from the slice panel when `latestSlice.status === "pending_approval"` or `"rejected"`. Show only: version, row count, status badge, and (for rejected) the rejection reason + replacement upload. Data is hidden until approved.

When `latestSlice.status === "approved"`, the preview table remains as-is.

### 2. Approval card for `project_stakeholder`

When `latestSlice.status === "pending_approval"` and `role === "project_stakeholder"`, render a dedicated "Review & Approve" card above the slice panel replacing the plain amber banner. It contains:

**Stats strip** — computed from `headerCsv` and `previewRows`:
- Column count
- Total rows (`latestSlice.rowCount`)
- Preview rows shown (`previewRows.length`)
- Blank columns — columns where every preview value is empty or whitespace

**PII scan** — computed client-side from `previewRows`, one badge per column:
- 🔴 **PII detected** — >60% of preview values match a strong pattern (email, SSN `###-##-####`, credit card 16-digit)
- ⚠️ **Possible PII** — >30% match a softer pattern (phone digits, date-like `YYYY-MM-DD` or `MM/DD/YYYY`, numeric ID-like)
- ✅ **Clean** — low match rate

**Unmasked sample data table** — full `previewRows` rendered without any masking; uses `splitCsvRow` from `web/lib/csv-utils.ts` (not `.split(",")`) for correct quoted-field handling; blank cells highlighted in amber.

**Approve / Reject actions** — calls existing `approveFeedSlice` / `rejectFeedSlice` from `feeds-api.ts`; rejection requires a reason (text input, required before submit).

### 3. `central_team` view when pending

For `central_team` role when status is `pending_approval`, keep the existing amber banner text but no data preview (data is the approver's domain, not the operator's at this stage).

## Acceptance Criteria

- Feed workspace shows no preview data when status is `pending_approval` or `rejected`
- `project_stakeholder` sees the full approval card (stats + PII scan + unmasked table + approve/reject) when status is `pending_approval`
- Blank cells in the sample table are visually distinct (amber background)
- PII badges appear on each column header — red / amber / green
- Approving transitions the slice to `approved` and reloads the workspace
- Rejecting requires a reason; transitions to `rejected`
- `central_team` and other roles see no data until approved
- TypeScript compiles cleanly; uses `splitCsvRow` not `.split(",")`

## Pitfalls

- Current preview table uses `.split(",")` — replace with `splitCsvRow` from `web/lib/csv-utils.ts` to handle quoted fields correctly
- PII scan operates only on `previewRows` (typically 5–20 rows) — make this explicit in the UI ("based on preview sample")
- `approveFeedSlice` and `rejectFeedSlice` already exist in `feeds-api.ts` — no new API functions needed
- The approval card should only render for `project_stakeholder` — not `central_team`, not `read_only_auditor`
- After approval or rejection, reload slices via `listFeedSlices` to refresh state

## Commit

- `feat(001cc): gate feed slice preview behind approval; add data profile and PII scan for approvers`
