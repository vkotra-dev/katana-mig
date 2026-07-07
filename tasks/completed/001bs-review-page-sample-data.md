# Task 001bs — Review Page Sample Data Context

**Plan:** `plans/2026-07-07-001bs-review-page-sample-data.md`

## Context

The review page (`/projects/[id]/feeds/[feedId]/review`) asks business users to approve or reject field mappings. Currently it shows only the binding pairs (source field → destination field) with no sample values from the actual data. Users have to approve on faith without seeing whether the mapping makes sense for real data. The approved `FeedSlice` already holds `headerCsv` (column names) and `previewRows` (CSV strings of masked sample rows) — both are returned by `listFeedSlices` which is already an existing client function.

## Scope

**Frontend only — no backend changes:**
- Review page calls `listFeedSlices` for the feed, finds the latest approved slice
- Parses `headerCsv` + `previewRows` to build `sampleValues: Record<string, string[]>` (source column name → up to 3 non-blank sample values)
- Passes `sampleValues` into `ReviewGrid` (or equivalent rendering logic)
- Each binding row displays the 2–3 sample values under the source field name in a muted chip/badge style

## Out of Scope

- Backend changes
- Sample data for destination fields
- Lookup value mapping sample display (separate concern)

## Acceptance Criteria

- Review page shows 1–3 masked sample values per source field alongside each binding row
- If the feed has no approved slice, the section renders gracefully with no sample data shown
- If a source field has no matching column in the slice header, it shows nothing (no crash)
- Business user (`project_stakeholder`) sees the data; operator (`central_team`) also sees it

## Pitfalls

- `previewRows` may be an empty array if the slice has no rows — guard before parsing
- CSV parsing must handle quoted fields (e.g. `"Smith, Jr."`) — use a simple split-on-comma only if values are known to be safe; otherwise use a CSV parser or the backend's already-split `previewRows` structure
- `headerCsv` may be null — guard, skip sample display if absent
- Source field names in bindings may not match header column names exactly (casing, whitespace) — do case-insensitive lookup when building the map

## Commit

- `feat(001bs): surface feed slice sample values on review page`
