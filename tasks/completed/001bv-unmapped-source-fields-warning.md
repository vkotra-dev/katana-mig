# Task 001bv — Unmapped Source Fields Warning

**Plan:** `plans/2026-07-07-001bv-unmapped-source-fields-warning.md`

## Context

When `propose_mapping` runs, the AI maps source columns to destination fields. Source columns that have no binding in any destination table are silently dropped during migration. Reviewers approve mappings with no visibility into what data is being lost. This task surfaces unmapped source columns as an informational amber warning — not blocking, but clearly visible — on both the review page and the feed workspace.

## Scope

**Frontend only — no backend changes:**

1. **Review page** (`/feeds/[feedId]/review`): After all destination table binding sections, show an amber "Unmapped source fields" panel listing every source column that appears in `headerCsv` but has no binding across any snapshot for this feed. Show sample values from `sampleValues` (already available from 001bs). Informational only — does not gate approval.

2. **Feed workspace** (`/feeds/[feedId]/page.tsx`): Below each table accordion's binding list, show the same warning for source columns that are unmapped across all loaded snapshots. Gives the operator visibility before submit-for-review.

## Key Design Decisions

- "Unmapped" = source column that appears in NO binding in ANY destination table snapshot for the feed. A column bound in table A but not table B is not considered unmapped.
- `allSourceColumns` is derived from `FeedSlice.headerCsv` (already fetched). Computation is: `headerColumns - Set(allBindings.map(b => b.sourceField.toLowerCase()))`.
- Warning is amber, not red — data loss is intentional in many cases (audit columns, row checksums, internal IDs). The flag is purely informational.
- No new props needed on `ReviewGrid` beyond what 001bs already added (`sampleValues`). Pass `allSourceColumns` as an additional prop.

## Out of Scope

- Per-table unmapped analysis (e.g. "column X is in table A but not table B")
- Blocking approval on unmapped fields
- Backend storage of unmapped fields
- AI prompt changes

## Acceptance Criteria

- Review page shows an amber "Unmapped source fields" section when at least one source column has no binding
- Section lists each unmapped column name with up to 3 sample values
- If all source columns are mapped, the section is not shown
- Feed workspace shows the same warning in the field mapping area
- Warning is informational only — approve/reject controls are unaffected
- TypeScript compiles with no new errors

## Pitfalls

- `headerCsv` may be null (no approved slice yet) — guard and skip computation if absent
- Source field names in bindings may be a subset of header names due to the AI choosing not to bind certain columns — this is the expected case the warning surfaces
- Case-insensitive comparison needed (same as 001bs sampleValues key lookup)
- Feed workspace may have no snapshots yet — guard with `allMappingSnapshots.length === 0` before computing

## Commit

- `feat(001bv): show informational warning for unmapped source fields on review and workspace pages`
