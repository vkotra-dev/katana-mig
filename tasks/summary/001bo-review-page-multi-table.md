# Task Summary — 001bo-review-page-multi-table

Fixed the mapping review page to properly display all destination tables associated with the feed's approved mapping snapshots, resolving the issue where only a single snapshot/table was rendered.

## Changes

- **Multiple Snapshots Resolution**: Replaced the single `getMappingSnapshot` call with `getAllApprovedMappingSnapshots(..., true)` in the review page loader.
- **Accords & Render**: Grouped snapshots by `destinationObjectName` to build a clean accordion view of mapping tables.
- **Housekeeping**: Completed role renaming/checks mapping `"business_user"` to `"project_stakeholder"` and corrected type signature constraints on TipTap editors, payload builders, and status chips.
