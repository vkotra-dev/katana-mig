# Plan: 001bu — Feed Slice Rejection: Status Banner and Data Replacement

- **Task Link:** [tasks/001bu-feed-slice-rejection-replacement.md](../tasks/001bu-feed-slice-rejection-replacement.md)
- **Domain Link:** [docs/domain/ui.md](../docs/domain/ui.md)

## Current State

`web/app/projects/[id]/feeds/[feedId]/page.tsx`:
- `latestSlice = slices[slices.length - 1]` — backend returns slices ascending by `created_at`
- `hasNoSlices = slices.length === 0`
- Existing banner slots at lines 367–377: `{error && ...}` and `{notice && ...}`
- Slice status badge (line 406) hardcodes "received" text — actual `latestSlice.status` is not displayed
- No upload control is shown after initial slice is present (001bj removed it)

`web/lib/feeds-api.ts`:
- `FeedSliceRecord.status: string` and `FeedSliceRecord.approvalRejectionReason: string | null` are already mapped
- `uploadFeedSlice(token, projectId, sourceDefinitionId, { content })` exists — creates a new slice
- **Missing:** `resubmitFeedSlice` — backend route `POST /sources/{id}/slices/{sliceId}/resubmit` exists but has no frontend counterpart

Backend slice statuses (from model default + management code): `pending_approval`, `approved`, `rejected`.

## Objective

1. **Amber banner (all roles):** When `latestSlice.status === "pending_approval"`, show an amber info banner at the top of the workspace.

2. **Rejection state — red banner + upload control:** When `latestSlice.status === "rejected"`, show a red alert banner with `approvalRejectionReason` + file input + "Upload replacement" button. On success: reload slices, amber banner appears.

3. **Approved state — quiet re-upload in Slice panel:** When `latestSlice.status === "approved"`, show a small "Upload new slice" file input + button at the bottom of the Slice panel (left column). This covers the case where an operator discovers a data gap after approval and needs to re-upload a corrected file. On success: new slice enters `pending_approval`, amber banner appears.

4. **Pending approval state — upload locked:** No upload control shown when `pending_approval` — one slice must clear the review queue before a new one is submitted.

5. **Add `resubmitFeedSlice` to `feeds-api.ts`:** Backend route exists but has no frontend counterpart. Wire it up for future use — not exposed in UI in this task.

## Out of Scope

- Admin approve/reject controls (already exist)
- Notifications
- Showing status banners on the feeds list page

## Blast Radius

| Layer | Files |
|---|---|
| Frontend API client | `web/lib/feeds-api.ts` |
| Feed workspace page | `web/app/projects/[id]/feeds/[feedId]/page.tsx` |

## File Changes

### `web/lib/feeds-api.ts`

Add `resubmitFeedSlice` after `approveFeedSlice`/`rejectFeedSlice`:

```ts
export async function resubmitFeedSlice(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  sourceSliceId: string,
  encoding?: string,
): Promise<FeedSliceRecord> {
  const response = await requestJson<Parameters<typeof mapFeedSliceResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/slices/${sourceSliceId}/resubmit`,
    {
      method: "POST",
      token,
      body: JSON.stringify({ encoding: encoding ?? null }),
    },
  );
  return mapFeedSliceResponse(response);
}
```

### `web/app/projects/[id]/feeds/[feedId]/page.tsx`

**Step 1 — Imports**

Add `resubmitFeedSlice` to existing import from `@/lib/feeds-api`.

**Step 2 — State for replacement upload**

```ts
const [replacementFile, setReplacementFile] = useState<string | null>(null);
const [uploadingReplacement, setUploadingReplacement] = useState(false);
```

**Step 3 — Upload replacement handler**

```ts
async function handleUploadReplacement() {
  if (!replacementFile || !session?.accessToken) return;
  setUploadingReplacement(true);
  try {
    await uploadFeedSlice(session.accessToken, projectId, feedId, { content: replacementFile });
    setReplacementFile(null);
    // Reload slices — new slice enters pending_approval, amber banner appears
    const refreshed = await listFeedSlices(session.accessToken, projectId, feedId);
    setSlices(refreshed);
  } catch {
    setError("Failed to upload replacement file.");
  } finally {
    setUploadingReplacement(false);
  }
}
```

**Step 4 — File reader helper (same pattern as initial upload)**

```ts
function handleReplacementFileChange(e: React.ChangeEvent<HTMLInputElement>) {
  const file = e.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (ev) => setReplacementFile(ev.target?.result as string);
  reader.readAsText(file);
}
```

**Step 5 — Banners (insert after existing `{notice && ...}` block, before the `{loading ? ...}` block)**

```tsx
{/* Pending approval banner */}
{!loading && latestSlice?.status === "pending_approval" && (
  <div
    role="alert"
    className="rounded-xl border border-amber-400/30 bg-amber-50 px-4 py-3 text-sm text-amber-800"
  >
    Source data is pending approval — field mapping analysis will be available once the slice
    is approved.
  </div>
)}

{/* Rejection banner + replacement upload */}
{!loading && latestSlice?.status === "rejected" && (
  <div
    role="alert"
    className="rounded-xl border border-red-400/30 bg-red-50 px-4 py-3 text-sm text-red-800 space-y-3"
  >
    <p className="font-medium">
      Source data was rejected
      {latestSlice.approvalRejectionReason
        ? `: ${latestSlice.approvalRejectionReason}`
        : "."}
    </p>
    <p className="text-xs text-red-700">
      Upload a replacement file to re-enter the approval queue.
    </p>
    <div className="flex items-center gap-3">
      <input
        type="file"
        accept=".csv,.txt"
        onChange={handleReplacementFileChange}
        className="text-xs text-red-800"
      />
      <button
        onClick={handleUploadReplacement}
        disabled={!replacementFile || uploadingReplacement}
        className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40 hover:bg-red-700"
      >
        {uploadingReplacement ? "Uploading…" : "Upload replacement"}
      </button>
    </div>
  </div>
)}
```

> Both banners are gated on `!loading` so they don't flicker before slices are fetched.

**Step 6 — Quiet re-upload in the Slice panel when `approved` (bottom of left column)**

When the latest slice is approved, the upload control is not in a banner but inline at the bottom of the Slice panel card — a low-key disclosure for fixing discovered data gaps:

```tsx
{latestSlice?.status === "approved" && (
  <div className="border-t border-outline-variant pt-3 mt-2 space-y-2">
    <p className="text-xs text-slate-500">Upload a corrected file to replace this slice:</p>
    <div className="flex items-center gap-2">
      <input
        type="file"
        accept=".csv,.txt"
        onChange={handleReplacementFileChange}
        className="text-xs text-slate-600"
      />
      <button
        onClick={handleUploadReplacement}
        disabled={!replacementFile || uploadingReplacement}
        className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 disabled:opacity-40 hover:bg-slate-50"
      >
        {uploadingReplacement ? "Uploading…" : "Upload new slice"}
      </button>
    </div>
  </div>
)}
```

This shares the same `replacementFile`, `uploadingReplacement`, `handleReplacementFileChange`, and `handleUploadReplacement` state and handlers defined in Steps 2–4 — no duplication needed.

> Upload is **not** available when `pending_approval` — one slice must clear the review queue before a new one can be submitted.

**Step 7 — Fix hardcoded "received" status badge (line ~406)**

Replace the hardcoded badge with a dynamic one:

```tsx
// Before
<span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">
  <span className="h-1.5 w-1.5 rounded-full bg-emerald-600"></span>
  received
</span>

// After
<span
  className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold ${
    latestSlice.status === "approved"
      ? "bg-emerald-50 text-emerald-700"
      : latestSlice.status === "rejected"
        ? "bg-red-50 text-red-700"
        : "bg-amber-50 text-amber-700"
  }`}
>
  <span
    className={`h-1.5 w-1.5 rounded-full ${
      latestSlice.status === "approved"
        ? "bg-emerald-600"
        : latestSlice.status === "rejected"
          ? "bg-red-500"
          : "bg-amber-500"
    }`}
  />
  {latestSlice.status === "approved"
    ? "approved"
    : latestSlice.status === "rejected"
      ? "rejected"
      : "pending approval"}
</span>
```

## Pitfalls

- After `handleUploadReplacement` succeeds, reload slices with `listFeedSlices` (not a full page reload). `latestSlice` is derived from `slices[slices.length - 1]` — the reload correctly makes the new `pending_approval` slice the latest, hiding both the red banner and the Slice panel upload control, and showing the amber banner instead.
- `replacementFile` holds the raw file content as a string (same shape as `FeedFileUploadInput.content`). Clear it after upload so a stale file can't be accidentally re-submitted.
- The Slice panel upload control (`approved` state) and the red banner upload control (`rejected` state) share the same state variables — only one will be visible at a time, so there is no conflict.
- Upload is intentionally locked when `pending_approval` — do not add an upload control for that state.
- `resubmitFeedSlice` re-parses the same retained binary — useful only if the rejection was an encoding mismatch, not a data content problem. Wired in client only; not exposed in UI in this task.
- The `pending_approval` banner must not appear when `latestSlice` is `undefined` (`hasNoSlices` case). The `latestSlice?.status ===` optional-chain guard handles this.

## Tests

No automated tests for the feed workspace page. Manual verification only.

## Verification

1. Upload a new feed slice → status badge shows "pending approval", amber banner appears; no upload control visible
2. Admin rejects the slice → status badge shows "rejected", red banner with rejection reason appears; file upload control is present in the banner
3. Upload a replacement file (from rejected state) → slices reload, red banner replaced by amber banner
4. Admin approves the slice → amber banner disappears, status badge shows "approved"; quiet "Upload new slice" control appears at the bottom of the Slice panel
5. Upload a corrected file from approved state → slices reload, amber banner appears, Slice panel upload control disappears
6. TypeScript compiles with no new errors

## Commit

- `feat(001bu): show approval status banner and data replacement upload on rejected feed slice`
