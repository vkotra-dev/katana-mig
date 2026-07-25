---
id: 001go
title: Fix removeSourceValue Patch Key Bug and Wire Add/Remove Source Value Actions Through ReviewGrid
status: completed
created: 2026-07-24
priority: high
domain: frontend / review-page / review-grid
depends-on: [001gn]
---

# Task 001go — Fix `removeSourceValue` Patch Key Bug and Wire Add/Remove Source Value Actions Through ReviewGrid

## Context

`web/app/projects/[id]/feeds/[feedId]/review/page.tsx` already defines `handleAddSourceByLookup` and `handleRemoveSourceByLookup`, but they are dead code — never passed into `<ReviewGrid>`. `ReviewGridProps` doesn't declare `onAddSourceValue`/`onRemoveSourceValue` at all, and `<LookupMappingTable>` is invoked without them, so the add/remove buttons in the lookup grid render with no effect.

Separately, `web/lib/lookup-api.ts` has a live bug: `patchLookupValueMap`'s `removeSourceValue` action is serialized as `body.removeSourceValue` (camelCase) instead of `body.remove_source_value` (snake_case, matching every other field in that function and what the backend's PATCH handler in `lookup_mapping.py` actually checks for). This means "remove source value" silently no-ops today — the request succeeds but the backend ignores it.

**Scope note**: Source values only — no destination-group delete action exists or is wired here (see [[001gn]]). Review Page only; `feeds/[feedId]/page.tsx` does not use `ReviewGrid` or `LookupMappingTable` and is untouched.

## Requirements

1. **Bug fix**: In `web/lib/lookup-api.ts`, fix the `removeSourceValue` action to serialize as `remove_source_value` (snake_case) in the PATCH body.
2. **ReviewGridProps**: Add `onAddSourceValue` and `onRemoveSourceValue` to `ReviewGridProps` and forward them to `<LookupMappingTable>`.
3. **Review Page Wiring**: Pass the existing `handleAddSourceByLookup` and `handleRemoveSourceByLookup` into `<ReviewGrid>`.

## Files to Change

1. `web/lib/lookup-api.ts` — Fix the `removeSourceValue` → `remove_source_value` key bug.
2. `web/components/projects/ReviewGrid.tsx` — Update `ReviewGridProps` and forward callbacks to `LookupMappingTable`.
3. `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` — Pass existing handlers into `ReviewGrid`.

## Verification

```bash
cd web && npm test -- --run
```

---
Plan: plans/2026-07-24-001go-lookup-review-grid-wiring.md
Summary: tasks/summary/001go-lookup-review-grid-wiring.md
