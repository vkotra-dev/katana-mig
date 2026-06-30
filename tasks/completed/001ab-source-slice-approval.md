# Task 001ab — Source Slice Approval

**Plan:** `plans/2026-06-29-001ab-source-slice-approval.md` _(to be written)_

**Spec:** `docs/superpowers/specs/2026-06-29-source-slice-approval-design.md`

## Domain

- `docs/domain/source-model.md` — Source slice status machine, approval API pattern,
  model fields (status, approval_rejection_reason, parse_warnings, file_storage_path)

## Depends on

- 001q (source intake — `source_slices` table + migration 0008 must exist)

## Scope

Add the human approval gate that converts a parsed source slice into an immutable,
consumable artifact. No new migration number — all new columns land in migration 0008
as part of the 001q scope (if 0008 is not yet shipped).

## Data model additions to `source_slices` (migration 0008 / 001q)

```python
status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_approval")
approval_rejection_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
parse_warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
file_storage_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
```

The upload endpoint (001q) must:
- set `status = "pending_approval"` on parse success
- write `file_storage_path` from the upload location
- populate `parse_warnings` from the parser

## New API routes (`routes/slice_approval.py`)

```
POST /projects/{project_id}/sources/{source_definition_id}/slices/{source_slice_id}/approve
  — status → "approved"; AuditEvent(source_slice_approved)
  — central_team only; 409 slice_not_pending if not pending

POST /projects/{project_id}/sources/{source_definition_id}/slices/{source_slice_id}/reject
  — body: {reason: str}
  — status → "rejected"; AuditEvent(source_slice_rejected)
  — central_team only; 409 slice_not_pending if not pending

POST /projects/{project_id}/sources/{source_definition_id}/slices/{source_slice_id}/resubmit
  — body: {encoding?: str, parse_settings?: dict}
  — precondition: slice status == "rejected"
  — auto-rejects any other pending_approval slice for this source_definition_id
  — re-parses file at file_storage_path with new settings
  — creates new SourceSlice at version v{n+1} with status "pending_approval"
  — 409 slice_not_rejected; 422 file_not_retained; 422 parse_failed
```

## New UI: Approvals page (`web/app/approvals/page.tsx`)

Global inbox. Nav link "Approvals" with amber count badge (count = pending slices
visible to current user).

Table columns: Project | Source label | Source type | Rows | Uploaded | Warnings | Actions

- Actions: `Approve` (green) + `Reject` (red outline)
- Reject opens modal with required `reason` textarea
- Empty state: "No pending approvals"
- `central_team` sees all projects; `project_stakeholder` sees only their projects (read-only)

## Artifacts tab integration (001p project detail)

In the project detail Artifacts tab, add source slice rows:

| Stage | Artifact | Version | Status | Produced | Actions |
|---|---|---|---|---|---|
| Source intake | Source slice | v1 | `pending_approval` (amber) | timestamp | Approve / Reject |

- `approved` rows: green chip, no action buttons
- `rejected` rows: red chip + rejection reason + Resubmit button
- Resubmit opens modal: encoding field + parse_settings JSON textarea

## Error codes

| Code | HTTP | When |
|---|---|---|
| `slice_not_pending` | 409 | Approve/reject on non-pending slice |
| `slice_not_rejected` | 409 | Resubmit on non-rejected slice |
| `file_not_retained` | 422 | Resubmit but `file_storage_path` is null |
| `parse_failed` | 422 | Re-parse failed; body has error detail |
| `slice_not_found` | 404 | Slice not in this project/source |

## Acceptance criteria

- [ ] Upload endpoint sets `status = "pending_approval"` and writes `file_storage_path`
- [ ] Approve transitions slice to `"approved"`; emits `AuditEvent`
- [ ] Reject requires non-empty reason; emits `AuditEvent`
- [ ] Resubmit creates new slice at `v{n+1}`; auto-rejects any other pending slice
- [ ] Resubmit returns `422 file_not_retained` when `file_storage_path` is null
- [ ] Approvals page shows amber count badge with live pending count
- [ ] Artifacts tab shows status chip + correct action buttons per slice state
- [ ] `pin_snapshots()` (001t) queries `status = "approved"` — confirm before closing task
- [ ] All tests pass against real SQLite test DB; no live API calls

## Notes

- `approved` is terminal and immutable — no endpoint to un-approve a slice
- The file at `file_storage_path` must not be deleted on rejection (required for resubmit)
- `pin_snapshots()` in 001t already filters by `status = "approved"` — verify this
  query exists before closing the task; add it if missing
- Feeds directly into 001v (source analysis) which requires an approved slice as input
