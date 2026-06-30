# Plan: 001ab-source-slice-approval

**Task:** [001ab-source-slice-approval](../tasks/001ab-source-slice-approval.md)
**Domain:** [docs/domain/source-model.md](../docs/domain/source-model.md)

## Current State

- Source intake is already wired and produces retained slices with approval metadata.
- The approval endpoints, inbox page, and project artifacts tab are partially implemented.
- The remaining work is to tighten contract alignment, clean up UI action handling, and verify the new approval flow with tests.

## Objective

Implement the source slice approval gate end-to-end:

- approve, reject, and resubmit actions for parsed slices
- global approvals inbox with pending-count badge
- project artifacts tab rows for slice decisions
- backend and UI tests for the approval flow

## Out of Scope

- New database migrations
- Broader auth/login wiring
- User-management CRUD beyond role-gated access required for this flow
- Reworking the source intake parser beyond what resubmit needs

## Blast Radius

- `engine/src/migrations_engine/api/schemas.py`
- `engine/src/migrations_engine/management/sources.py`
- `engine/src/migrations_engine/routes/slice_approval.py`
- `engine/src/migrations_engine/app.py`
- `engine/tests/test_source_slice_approval_api.py`
- `docs/domain/api.md`
- `web/lib/slice-approval-api.ts`
- `web/lib/sources-api.ts`
- `web/components/Topbar.tsx`
- `web/components/approvals/ApprovalsInbox.tsx`
- `web/components/projects/SourceArtifactsPanel.tsx`
- `web/app/approvals/page.tsx`
- `web/app/projects/[id]/page.tsx`

## File Changes

- Keep the slice approval service and router aligned with the source-model contract.
- Keep the web client and project detail views aligned with the approval API response shapes.
- Document the approval routes and response models in the API domain page.

## Tests

- Backend SQLite coverage for list, count, approve, reject, and resubmit flows.
- Web client tests for the approval API helpers and role-aware navigation surfaces.

## Verification

- Run the targeted backend pytest module for source slice approvals.
- Run the web test suite.
- Run the web production build to catch type and route regressions.
- Confirm `pin_snapshots()` still filters approved slices before closing the task.

## Pitfalls

- Resubmit must preserve retained upload bytes and fail closed if the file path is missing.
- Reject/resubmit dialogs should only close after a successful update.
- The approvals inbox must respect project membership for stakeholder users.
- Source slice response shapes now include version, rejection reason, warnings, and file storage path.

## Commit

- `feat(source): add slice approval, rejection, and resubmit flow`
