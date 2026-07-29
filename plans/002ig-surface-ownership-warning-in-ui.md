---
id: 002ig
title: Surface mapping_ownership_warnings where it blocks the operator
task: tasks/002ig-surface-ownership-warning-in-ui.md
domain: web
status: completed
created: 2026-07-29
---

# Plan — 002ig: Surface `mapping_ownership_warnings` where it blocks the operator

## Task / Domain Links

- Task: `tasks/002ig-surface-ownership-warning-in-ui.md`
- Domain: `docs/domain/ui.md` (Feeds screen note, line 158)

## Current State

**Feed page** (`web/app/projects/[id]/feeds/[feedId]/page.tsx`):
- `mappingOwnershipWarnings` warning card renders at lines 922-943 when `feed.mappingOwnershipWarnings`
  has entries.
- Immediately below it, lines 945-946 render `"No mapping proposals generated yet."` whenever
  `mappingTables.length === 0` — with no awareness of the warning card above it. `mappingTables` is
  `Object.values(mappingTablesMap)` (line 476), built from `allMappingSnapshots`.
- Result: when a propose attempt has hit the 409 ownership conflict and no snapshot exists, both
  the warning card and the generic empty message render together.

**Codegen page** (`web/app/projects/[id]/codegen/page.tsx`):
- `source` (type `FeedContractRecord`) already carries `mappingOwnershipWarnings` — fetched, unused.
- "Generate SQL" button (lines 707-719) is gated only on `role === "central_team"` and
  `actionLoading === source.sourceDefinitionId`.
- Each feed row is a `<Fragment>` with a collapsed `<tr>` (the row with the button) and, when
  `expandedFeed === source.sourceDefinitionId`, an expanded `<tr colSpan={6}>` (lines 722-745)
  that already renders a near-identical blocking-condition warning box — "Unmapped Required
  Destination Fields" — amber card, IIFE-guarded, "this will cause codegen to fail" framing. This
  is the established pattern for a per-feed blocking warning in this table.

## Objective

1. Feed page: when `feed.mappingOwnershipWarnings` has entries, suppress the generic
   `"No mapping proposals generated yet."` message — the warning card already explains why.
2. Codegen page: when `source.mappingOwnershipWarnings` has entries, (a) replace that feed's
   "Generate SQL" button with the warning — the button must not render at all, so there's no way
   to trigger codegen against a conflicting table and produce a defective artifact — and (b) show
   the full per-table detail in the expanded panel, reusing the existing "Unmapped Required
   Destination Fields" box's visual pattern for consistency.

## Out of Scope

- No backend/schema changes — `mapping_ownership_warnings` already exists on both `FeedResponse`
  and the list endpoint (002ie), already fetched on both pages.
- No changes to the propose-time 409 reactive path (`per_table_ownership`) — untouched.
- No changes to `approve_mapping()`'s cross-feed guard (002id).
- No changes to `mappingStatus` / the "Mapping" column badge (002ic) — separate, unrelated field.

## Blast Radius

Narrow, two files, both frontend-only, both purely additive conditionals around existing renders:

| File | Change | Risk |
|------|--------|------|
| `web/app/projects/[id]/feeds/[feedId]/page.tsx` | Gate one `<div>` render on an existing field | Low — no new state, no new fetch |
| `web/app/projects/[id]/codegen/page.tsx` | Gate button `disabled`, add two warning renders | Low — no new state, no new fetch; mirrors existing unmapped-fields box |

## File Changes

### 1. `web/app/projects/[id]/feeds/[feedId]/page.tsx` (~line 945)

```tsx
const hasOwnershipWarning = feed?.mappingOwnershipWarnings && Object.keys(feed.mappingOwnershipWarnings).length > 0;
...
{mappingTables.length === 0 ? (
  hasOwnershipWarning ? null : (
    <div className="text-sm text-slate-500">No mapping proposals generated yet.</div>
  )
) : ( ... unchanged ... )}
```
(`hasOwnershipWarning` can reuse the same expression already used to gate the warning card at
line 922, hoisted once to avoid computing `Object.keys(...)` twice.)

### 2. `web/app/projects/[id]/codegen/page.tsx`

**Action cell (~line 707-719)** — replace the button with the warning, don't just disable it, so
there's no control that could produce a defective artifact against a conflicting table:

```tsx
const hasOwnershipWarning = Boolean(source.mappingOwnershipWarnings && Object.keys(source.mappingOwnershipWarnings).length > 0);
...
<td className="px-4 py-3">
  {hasOwnershipWarning ? (
    <span className="text-xs font-semibold text-amber-700">⚠ Table ownership conflict</span>
  ) : role === "central_team" ? (
    <button
      className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
      disabled={actionLoading === source.sourceDefinitionId}
      onClick={() => void handleGenerate(source.sourceDefinitionId)}
      type="button"
    >
      Generate SQL
    </button>
  ) : (
    <span className="text-sm text-slate-500">No action</span>
  )}
</td>
```

**Expanded panel (~line 726, alongside the existing unmapped-fields IIFE)** — add a second block,
same visual treatment as the unmapped-fields box, listing each conflicting table and its owner
(same content/format as the feed page's card at `page.tsx:928-940`, since it's the same
`mappingOwnershipWarnings` shape):

```tsx
{source.mappingOwnershipWarnings && Object.keys(source.mappingOwnershipWarnings).length > 0 && (
  <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 mb-4">
    <p className="font-semibold mb-1">Table ownership conflicts</p>
    <ul className="list-disc list-inside space-y-0.5">
      {Object.entries(source.mappingOwnershipWarnings).map(([table, ownership]) => (
        <li key={table}>
          <strong>{table}</strong> is already mapped on{" "}
          {ownership.feedLabel || ownership.sourceDefinitionId?.slice(0, 8) || "this project"}
        </li>
      ))}
    </ul>
    <p className="text-xs text-amber-700 mt-1">
      Generate SQL is disabled for this feed until the conflict is resolved.
    </p>
  </div>
)}
```

No navigation link here (unlike the feed page's card) — keep this box read-only/simple since it's
a secondary surface; the feed page remains the place to act on the conflict.

## Tests

- `web/app/projects/[id]/feeds/[feedId]/page.test.tsx`: add a case with a feed fixture carrying
  `mappingOwnershipWarnings` populated and `allMappingSnapshots` empty — assert the warning card
  renders and `"No mapping proposals generated yet."` does not. Add/keep a case with no warnings
  and empty snapshots — assert the empty message still renders (regression guard).
- `web/app/projects/[id]/codegen/page.test.tsx`: add a case with a source fixture carrying
  `mappingOwnershipWarnings` populated — assert the "Generate SQL" button does not render (query
  returns null) and the inline warning text renders in its place. Add a case with no warnings —
  assert the button renders and is enabled (regression guard, since this file currently has no
  test touching `mappingStatus` or the button at all).

## Verification

```bash
cd web && npx tsc --noEmit   # confirm no new errors beyond the pre-existing baseline
cd web && npm test
.venv/bin/python scripts/validate_okf.py
```
Manually load the feed at the URL in the original report (a feed with a real ownership conflict)
and confirm: Field Mappings container shows only the warning card, no "No mapping proposals"
message; codegen page shows the inline warning in place of the "Generate SQL" button (button not
present in the DOM, not just disabled), plus the expanded-panel detail for that feed.

## Pitfalls

1. **Gap 1's suppression is feed-wide, not per-table** — if a feed has some conflicting and some
   non-conflicting destination tables with zero proposals on either, the empty message is
   suppressed entirely rather than partially. Accepted per the task's explicit "Known
   simplification" — replace, don't append, is the requested behavior.
2. **`Object.keys(...).length > 0` computed multiple times per render** — harmless at this table
   size (handful of feeds/tables), not worth memoizing.
3. **`ownership.sourceDefinitionId` can be `null`** (project-scoped snapshot, no owning feed) —
   the codegen-panel list must fall back to `"this project"`, matching the feed page's existing
   handling; already included in the snippet above.
4. **Don't duplicate the feed-page card's navigation link on the codegen page** — the codegen
   page's box is intentionally read-only (no `router.push` link) since acting on the conflict
   belongs on the feed page, not here. Keeps this task's diff from re-triggering the "duplicate
   warning display" pattern flagged earlier this session, just in a new location.

## Commit

One commit: "fix(web): suppress redundant empty-state and gate Generate SQL on mapping ownership
conflicts". Two independent frontend fixes to the same underlying gap (a fetched-but-unused
warning field), landed together since both are small and share the same root cause.
