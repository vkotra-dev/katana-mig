# Source Slice Approval — Design Spec

**Date:** 2026-06-29
**Status:** Approved

## Problem

`SourceSlice` records are created during file upload (task 001q) but there is no mechanism
to mark them as approved. The run engine (`pin_snapshots` in 001t) and the analysis stage
(001v) both require an approved slice before they can proceed. Without this flow the entire
downstream pipeline is blocked.

## Scope

This spec covers:
- `SourceSlice.status` state machine
- Three new API endpoints (approve, reject, resubmit)
- Two UI surfaces (Approvals page, Project detail Artifacts tab)

Out of scope: approval flows for `MappingSnapshot`, `LookupSnapshot`, or any other artifact
(those are defined in 001w and 001x respectively).

---

## Status State Machine

```
upload + parse success
        │
        ▼
 pending_approval  ──── approve ───▶  approved  (immutable; downstream can consume)
        │
        └────────── reject ────────▶  rejected
                                          │
                                       resubmit (new SourceSlice record)
                                          │
                                          ▼
                                   pending_approval  (cycle repeats)
```

**Rules:**
- Parse success (existing 001q upload endpoint) sets `status = "pending_approval"` automatically.
- `"approved"` is terminal and immutable. A slice cannot be un-approved.
- `"rejected"` is terminal for that record. Resubmit creates a **new** `SourceSlice` record
  (new `source_slice_id`, incremented version) for the same `SourceDefinition`.
  The rejected record is retained for audit.
- At most one `SourceSlice` per `SourceDefinition` should be in `"pending_approval"` at
  a time. If the operator resubmits while a previous pending slice exists, the previous
  pending slice is automatically moved to `"rejected"` (reason: `"superseded_by_resubmit"`).

---

## Data Model Changes

### `source_slices` table

Three columns added as part of **migration 0008** (001q scope — 0008 is not yet shipped):

```python
status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_approval")
approval_rejection_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
parse_warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
file_storage_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
```

- `status` permitted values: `"pending_approval"`, `"approved"`, `"rejected"`
- `parse_warnings` is populated by the 001q upload parser (e.g. `["3 rows skipped: missing field"]`)
- `file_storage_path` stores the server-side path or object-storage key for the original uploaded
  file. Required for resubmit to re-parse with new settings. The 001q upload endpoint must write
  this on every upload. If local-disk storage is used in development, this is an absolute path;
  in production it is an object-storage key.

Version numbering: `source_slice_version` is a human-readable string (`"v1"`, `"v2"`, …).
The upload endpoint sets `"v1"` on the first slice for a source. Resubmit reads the
highest existing version number for the `source_definition_id`, increments it, and sets
the new slice's version to `"v{n+1}"`.

---

## API

All three endpoints require `central_team` role. All emit an `AuditEvent`.

### Approve

```
POST /projects/{project_id}/sources/{source_definition_id}/slices/{source_slice_id}/approve
```

- Precondition: slice `status == "pending_approval"` and slice belongs to this project/source.
- Action: `status → "approved"`; `AuditEvent(event_type="source_slice_approved")`
- Response: `200` with updated `SourceSliceResponse`
- Error: `409 slice_not_pending` if status is not `"pending_approval"`

### Reject

```
POST /projects/{project_id}/sources/{source_definition_id}/slices/{source_slice_id}/reject
```

- Body: `{ "reason": str }` (required, max 1000 chars)
- Precondition: slice `status == "pending_approval"`
- Action: `status → "rejected"`, `approval_rejection_reason = reason`;
  `AuditEvent(event_type="source_slice_rejected", payload={"reason": reason})`
- Response: `200` with updated `SourceSliceResponse`
- Error: `409 slice_not_pending`

### Resubmit

```
POST /projects/{project_id}/sources/{source_definition_id}/slices/{source_slice_id}/resubmit
```

- Body: `{ "encoding": str | null, "parse_settings": dict | null }` (all optional)
- Precondition: slice `status == "rejected"`
- Action:
  1. Supersede any existing `"pending_approval"` slice for this `SourceDefinition`
     (set their status to `"rejected"`, reason `"superseded_by_resubmit"`)
  2. Re-parse the original file using the new encoding/parse_settings
  3. Create a new `SourceSlice` record (new ID, `version = old_version + 1`) with
     `status = "pending_approval"`
- Response: `201` with new `SourceSliceResponse`
- Error: `409 slice_not_rejected` if the source slice being resubmitted is not in `"rejected"` state
- Error: `422 parse_failed` if the re-parse fails; body includes parse error detail

---

## What the Approver Sees

The approval UI surfaces these fields from `SourceSlice` (no row-level data):

| Field | Display |
|---|---|
| `row_count` | "12,450 rows" |
| `encoding` | "utf-8" |
| `parse_warnings` | amber list if non-empty, else hidden |
| `source_type` | "csv" / "fixed_length_file" |
| `uploaded_at` (created_at) | monospace timestamp |
| `source_slice_id` | monospace + copy icon |

`parse_warnings` is a `list[str]` column populated by the 001q parse step (e.g.
`"3 rows skipped: missing required field"`). Defined in the Data Model Changes section above.

---

## UI

### Approvals page (`/approvals`)

A new top-level page. The nav already has an "Approvals" link with an amber count badge
(stitch 06 guardrail). This page is the global approval inbox.

**Table columns:** Project | Source label | Source type | Rows | Uploaded | Warnings | Actions

- **Actions** (inline): `Approve` (green button) + `Reject` (red outline button)
- Reject opens a small modal with a required `reason` text area
- Empty state: "No pending approvals"
- Filtered to `central_team` role; `project_stakeholder` and `read_only_auditor` see a
  read-only view of approved/rejected slices for their projects

**Amber badge count** = number of rows where `status = "pending_approval"` across all
sources visible to the user.

### Project detail — Artifacts tab

The Artifacts tab (stitch 06) already lists artifacts per stage. Source slice rows:

| Column | Content |
|---|---|
| Stage | "Source intake" |
| Artifact | "Source slice" |
| Version | monospace pill (`v1`, `v2`, …) |
| Status chip | `pending_approval` (amber) / `approved` (green) / `rejected` (red) |
| Produced | monospace timestamp |
| Actions | Approve + Reject (if `pending_approval`); Resubmit (if `rejected`) |

Resubmit opens a small modal:
- Optional encoding override (text field, default shows current encoding)
- Optional parse_settings override (JSON textarea, default empty)
- Submit button

---

## Error Codes

| Code | HTTP | When |
|---|---|---|
| `slice_not_pending` | 409 | Approve/reject called on non-pending slice |
| `slice_not_rejected` | 409 | Resubmit called on non-rejected slice |
| `parse_failed` | 422 | Resubmit re-parse failed; body has detail |
| `slice_not_found` | 404 | Slice does not belong to this project/source |

---

## Audit Events

| event_type | Payload |
|---|---|
| `source_slice_approved` | `{source_slice_id, source_definition_id}` |
| `source_slice_rejected` | `{source_slice_id, source_definition_id, reason}` |
| `source_slice_resubmitted` | `{old_slice_id, new_slice_id, source_definition_id}` |

---

## Testing

- Approve transitions `pending_approval → approved`; subsequent approve returns `409`
- Reject requires non-empty reason; transitions to `rejected`
- Resubmit on rejected slice creates a new slice with `version = old + 1`
- Resubmit when another pending slice exists supersedes it automatically
- Resubmit on a non-rejected slice returns `409`
- Parse failure during resubmit returns `422` with error detail
- `AuditEvent` is created for every state transition
- Approvals page count badge reflects live pending count
- `central_team` can approve/reject; `project_stakeholder` and `read_only_auditor` cannot

---

## Implementation Notes

- The file referenced by a rejected slice must be retained in storage so resubmit can
  re-parse it. Do not delete files on rejection.
- Resubmit uses the same file (via `file_storage_path` on the rejected slice) with
  potentially different parse settings — it does not require a new file upload. If
  `file_storage_path` is null on the rejected slice, the resubmit endpoint returns
  `422 file_not_retained` and the operator must upload a new file via the normal upload flow.
- `pin_snapshots()` in 001t should query `status = "approved"` ordered by `created_at DESC`
  to get the latest approved slice.
