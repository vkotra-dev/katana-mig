# Task Summary — 001bq-operator-mapping-edit-submit

Enabled operators to edit destination field bindings from the feed details workspace page and submit them for review to stakeholders.

## Changes

- **Schema & Serialization**: Added `destination_fields` to `MappingSnapshotResponse` in the backend schemas and routes so the field list is serializable on the snapshots list GET endpoint.
- **Frontend Types**: Included `destinationFields` on `MappingSnapshotRecord` in [mapping-api.ts](file:///Users/vjkotra/projects/katana/web/lib/mapping-api.ts). Also added the optional `destinationObjectName` query parameter to the `patchMappingSnapshot` endpoint client call.
- **Feed Details workspace UI**: Refactored [page.tsx](file:///Users/vjkotra/projects/katana/web/app/projects/[id]/feeds/[feedId]/page.tsx):
  - Allowed editing mapping row destination columns using `<select>` dropdowns when `role === "central_team"` and the snapshot is a draft.
  - Added a "Save" button per table to submit edited bindings via `patchMappingSnapshot`.
  - Added a "Submit for review" button that displays a confirmation message.
- **Unit Tests**: Updated and extended unit tests in [page.test.tsx](file:///Users/vjkotra/projects/katana/web/app/projects/[id]/feeds/[feedId]/page.test.tsx) to cover accordion expansion, dropdown interaction, saving mappings, and review submission.
