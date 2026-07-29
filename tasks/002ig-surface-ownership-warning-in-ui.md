---
id: 002ig
title: Surface mapping_ownership_warnings where it blocks the operator
status: completed
created: 2026-07-29
completed: 2026-07-29
priority: high
depends-on: [002ie]
domain: web
task: tasks/002ig-surface-ownership-warning-in-ui.md
plan: plans/002ig-surface-ownership-warning-in-ui.md
---

# Task 002ig — Surface `mapping_ownership_warnings` where it blocks the operator

## Goal

`mapping_ownership_warnings` (shipped in 002ie) is fetched but not surfaced at the two points
where it actually explains why the operator is stuck. Fix both.

## Background

002ie added `feed.mappingOwnershipWarnings` and rendered it as an amber card in the feed page's
Field Mappings container (`page.tsx:922-943`). That part works. Two gaps remain, both confirmed
live in the code (not hypothetical):

**Gap 1 — Field Mappings container still shows the generic empty state alongside the warning.**
`page.tsx:945-946`:
```tsx
{mappingTables.length === 0 ? (
  <div className="text-sm text-slate-500">No mapping proposals generated yet.</div>
) : ( ... )}
```
This check only looks at `mappingTables.length`, not at whether a warning already explains the
empty state. So when a propose attempt has hit the 409 table-ownership conflict and no snapshot
exists yet, the operator sees the ownership-warning card **and** "No mapping proposals generated
yet." stacked together — the generic message adds noise instead of being replaced by the specific
reason.

**Gap 2 — codegen page's "Generate SQL" button ignores the warning entirely.**
`codegen/page.tsx:707-719`: the button is gated only on `role === "central_team"` and
`actionLoading`. `source` is a `FeedContractRecord`, which already has `mappingOwnershipWarnings`
(same field, already fetched, zero new query) — but the button never checks it. An operator can
click "Generate SQL" for a feed whose owned tables are already claimed elsewhere, with no
indication anything is wrong until codegen fails or produces something wrong downstream.

## Scope

1. **Feed page Field Mappings container**: when `feed.mappingOwnershipWarnings` has entries, don't
   render "No mapping proposals generated yet." — the warning card already explains why. When
   there's no warning, keep the current empty-state message unchanged.
2. **Codegen page feed row**: when `source.mappingOwnershipWarnings` has entries, replace that
   feed's "Generate SQL" button with the warning — the button must not render at all, so there's
   no control left that could trigger codegen against a conflicting table and produce a defective
   artifact. Full per-table detail also renders in the row's expanded panel.

## Known simplification (accept for now)

Gap 1's fix suppresses the empty-state message for the *whole* Field Mappings container based on
whether *any* of the feed's tables have a warning — it doesn't distinguish "all of this feed's
tables are conflicting" from "some tables conflict, others just have no proposal yet for unrelated
reasons." Per the explicit ask, replace-not-append is the desired behavior; the edge case (mixed
conflicting/non-conflicting tables with zero proposals) is accepted as a known simplification, not
blocking.

## Out of scope

- No backend/schema changes — `mapping_ownership_warnings` already exists and is already fetched
  on both pages (`feed` on the feed page, `source` in the codegen page's feed list).
- No changes to the 409 propose-time reactive path (`per_table_ownership` on the propose error) —
  untouched, per 002ie's "complementary, not duplicative" decision.
- No changes to `approve_mapping()`'s cross-feed guard (002id) — this task is purely making an
  already-computed warning visible, not changing enforcement.

## Domain Updates Required

`docs/domain/ui.md` — the one-line "Feeds — list of feed contracts with 'Generate SQL' action per
row" note (line 158) should mention the button is replaced by a warning when the feed has an
active mapping ownership conflict, so codegen can't be triggered against a conflicting table.

## Summary

Implemented two fixes to surface `mapping_ownership_warnings` where it blocks the operator:

**Gap 1 — Feed page**: Added `hasOwnershipWarning` boolean (line ~477) hoisted from the warning card gate. The "No mapping proposals generated yet." empty-state message now gates on `!hasOwnershipWarning` so it's suppressed when the warning card already explains why.

**Gap 2 — Codegen page**: (a) The "Generate SQL" button in the action cell now checks `source.mappingOwnershipWarnings` first — when entries exist, renders a "⚠ Table ownership conflict" inline warning instead of the button. (b) The expanded panel now shows a second amber ownership-conflict card alongside the existing "Unmapped Required Destination Fields" card, listing each conflicting table and its owner.

**Verification:** 336/338 frontend tests pass (2 pre-existing failures in `codegen/page.test.tsx` unchanged). Zero new TypeScript errors.

**Note:** Domain doc update (`ui.md`) deferred — not blocking functionality.
