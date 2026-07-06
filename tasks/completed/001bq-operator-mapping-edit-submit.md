# Task 001bq — Operator Mapping Edit and Submit for Review

**Plan:** `plans/2026-07-07-001bq-operator-mapping-edit-submit.md`

## Context

The current feed workspace shows AI-proposed field bindings as a read-only accordion. There is no way for the admin (central_team) to correct wrong destination field assignments, nor to explicitly submit the mapping for business user review. This means:

1. If AI maps `CUST_ID → customer_name` but it should be `CUST_ID → customer_id`, the admin has no UI to fix it
2. There is no "Submit for review" action — the stakeholder just sees a draft with no signal that the operator has finished reviewing it
3. The `patchMappingSnapshot` backend endpoint exists (`PATCH /mapping`) but is not wired to any UI in the feed workspace

## Scope

**Feed workspace** (`web/app/projects/[id]/feeds/[feedId]/page.tsx`):
- Each binding row in the field mapping accordion gets an editable destination field selector (dropdown of valid destination columns from the snapshot's DDL)
- A "Save mapping" button per table (or globally) calls `patchMappingSnapshot`
- A "Submit for review" button appears after mappings have been saved, which triggers a notification to the project stakeholder

**No backend changes** — `patchMappingSnapshot` already exists. The "submit for review" notification may require a new backend notification event or can reuse an existing pattern.

## Out of Scope

- Editing on the review page (review page stays read-only)
- Adding new field bindings (only correcting existing AI-proposed ones)
- Lookup fiber editing (already has its own UI)

## Acceptance Criteria

- Admin can change the destination field for any binding row in the feed workspace
- Changes are saved via `patchMappingSnapshot`
- Admin can click "Submit for review" to signal to the stakeholder the mapping is ready
- Stakeholder receives a notification (or the button at minimum changes the UI state)

## Pitfalls

- `patchMappingSnapshot` requires `field_bindings` as a full replacement — must send ALL bindings, not just the changed ones
- Destination field options must come from the destination DDL — need to fetch or derive valid column names per table
- Draft snapshots are already visible to stakeholders; "submit for review" is a workflow signal, not a visibility gate

## Commit

- `feat(001bq): add operator field-binding edit and submit-for-review to feed workspace`
