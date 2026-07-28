---
id: 002ic
title: Duplicate feed mapping detection — per-table ownership report
status: completed
created: 2026-07-28
completed: 2026-07-28
depends-on: [002ib]
---

# 002ic: Duplicate feed mapping detection — per-table ownership report

## Summary

Completed the `per_table_ownership` detail on the propose 409 and the frontend card that displays it.

## What was shipped

### Part 1: Backend (proposal.py) — ✅ Already shipped in previous commit
Attach `per_table_ownership` dict to the 409 response when all AI-proposed tables are already approved elsewhere.

### Part 2: Frontend ownership card (page.tsx + feeds-api.ts) — ✅ Completed this session
- Added `detail` field to `FeedApiError` to capture the full raw error detail object
- Updated `parseApiError` to store the detail on the error instance
- Added `perTableOwnership` state in the feed page
- When the 409 from `proposeMappingSnapshot` contains `per_table_ownership`, it's extracted and rendered as an amber "Duplicate mappings found" card
- The card lists each table with a link to the owning feed's page
- State is cleared on the next "Analyze with AI" click

### Part 3: Codegen mapping status badge — ✅ Already shipped in previous commit
Added "Mapping" column to the codegen page's sources table, reading `mappingStatus` from the feed contract response.

### Part 4: Docs
`docs/domain/api.md` already documents `per_table_ownership` in the propose 409 from the design exploration — verified against implementation.

## Verification

- 462/462 backend tests pass
- 15/15 frontend feeds-api tests pass
- TypeScript: same pre-existing error baseline, no new errors

## Notes

- The `mapping_ownership_warnings` field on `FeedResponse` (002ie) complements this: that shows persistent warnings on every load, while this card shows immediate feedback at the moment of a failed propose action.
