---
id: 002ie
title: Persistent cross-feed table-ownership warning on FeedResponse
status: completed
created: 2026-07-28
completed: 2026-07-28
priority: medium
depends-on: [002ic, 002id]
domain: engine
task: tasks/002ie-mapping-ownership-warnings.md
plan: plans/2026-07-28-002ie-mapping-ownership-warnings.md
---

# Task 002ie — `mapping_ownership_warnings` on `FeedResponse`

## Summary

Implemented `mapping_ownership_warnings` — a persistent, load-time cross-feed ownership warning
on `FeedResponse`. Every time a feed is loaded or listed, the backend queries approved
`MappingSnapshot` rows for the feed's destination tables and returns ownership details keyed by
`destination_object_name`. The frontend renders these as amber warning cards in the Field Mappings
section so operators always see the current ownership state, not just what a failed propose/approve
call reported at one moment.

## What was shipped

**Backend (Python):**
- `engine/src/migrations_engine/api/schemas.py`: `MappingOwnership` Pydantic model + `mapping_ownership_warnings` field on `FeedResponse`
- `engine/src/migrations_engine/management/feeds.py`: `_compute_ownership_warnings()` (single-feed) + `_batch_ownership_warnings()` (batch, one query) — both reuse the `outerjoin(Feed, ...)` / `or_(is_(None), and_(!= feed_id, status != "discarded"))` pattern from the 002id guard. Wired into `_source_contract_response()` and `list_source_contracts()`.

**Frontend (TypeScript/React):**
- `web/lib/feeds-api.ts`: `MappingOwnershipRecord` interface, `mappingOwnershipWarnings` on `FeedContractRecord`, raw param type + mapper (all three spots — no field-by-field cast bugs)
- `web/app/projects/[id]/feeds/[feedId]/page.tsx`: Deleted dead `conflictOwnership` state, simplified `handleAnalyzeWithAi`'s conflict catch to just reload data, added amber warning card (with proper `router.push` client-side navigation and "omit parenthetical when project-scoped" handling)

**Docs:**
- `docs/domain/api.md`: `MappingOwnership` model + field docs + render contract + null-owner gap fix
- `docs/domain/source-model.md`: Note on `mapping_ownership_warnings` as the persistent counterpart to the 002id guard

**Tests:**
- `engine/tests/test_mapping_ownership_warnings.py`: 6 tests (cross-feed warning, no-conflict null, project-scoped snapshot, discarded feed excluded, batch list matches single-feed, self-warning exclusion)

## Verification

- 6/6 new tests pass
- Full backend suite: 462 passed
- Frontend: 15 feeds-api tests pass
- TypeScript: 28 errors (same pre-existing baseline, no new errors)
- OKF validation: zero warnings

## Notes

- The `conflictOwnership` dead code in `page.tsx` was removed — it was computed but never rendered.
- The ownership link uses `router.push` for client-side navigation (consistent with rest of file).
- `per_table_ownership` on the propose 409 is kept as-is (complementary: "why did my action fail now" vs "does this feed have a problem right now").
