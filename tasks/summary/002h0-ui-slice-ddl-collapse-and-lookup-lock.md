Task: tasks/completed/002h0-ui-slice-ddl-collapse-and-lookup-lock.md
Plan: plans/2026-07-24-002h0-ui-slice-ddl-collapse-and-lookup-lock.md

## Housekeeping note

Task was `status: pending` despite both pieces being fully implemented. An earlier pass in this
session incorrectly flagged the lookup-lock half as missing — the search only checked
`feeds/[feedId]/page.tsx` and missed `ReviewGrid.tsx`/`LookupMappingTable.tsx`, where the actual
implementation lives. Verified directly against the code before writing this summary.

## Changes Made (as found in the codebase)

- Source DDL collapse (`feeds/[feedId]/page.tsx:732-766`) — collapsible block at the bottom of the
  Slice section, collapsed by default via `useState`, "Show Source DDL" / "Hide Source DDL" toggle.
- Lookup lock (`components/projects/ReviewGrid.tsx:347,776-779`) —
  `isLocked = lookupStatus && (lookupStatus.centralTeam?.signed || lookupStatus.projectStakeholder?.signed)`
  (OR logic, matches the task's spec exactly), passed as `locked={isLocked}` to `LookupMappingTable`.
- `LookupMappingTable.tsx:11,39,103,115` — `locked` prop gates the add/remove source-value controls
  (`!locked && editingEnabled && ...`), additive to the existing `editingEnabled` ball-holder check,
  matching pitfall #3's stated design.

## Domain Updates Required

- `docs/domain/ui.md` — **Updated**. Added the Source DDL collapse note to the Feed Detail
  workspace's slice-status-panel bullet, and the lookup-lock OR-logic behavior to the Review
  grid's "Lookup value mapping grids" bullet. `timestamp` already 2026-07-28 (same-day edit).

## Tests

No dedicated unit tests exist for either behavior — `ReviewGrid.test.tsx` has no assertions on
`locked`/`isLocked`/sign-off-driven lock state, and there's no test file for the feed page's Source
DDL collapse. The task's own "Tests" section calls for both. Left as a known gap rather than
silently closed as fully covered — flagged to the user, who marked adding them as optional for
this housekeeping pass.

`.venv/bin/python scripts/validate_okf.py` — zero warnings, 12/12 domain pages compliant.
