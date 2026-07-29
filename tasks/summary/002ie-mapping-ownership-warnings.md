# Summary: 002ie — `mapping_ownership_warnings` on `FeedResponse`

## Goal

Persistent, load-time cross-feed ownership warning on `FeedResponse`. Every time a feed is loaded or listed, the backend queries approved `MappingSnapshot` rows for the feed's destination tables and returns ownership details keyed by `destination_object_name`. The frontend renders these as amber warning cards.

## What was shipped

**Backend (Python):**
- `engine/src/migrations_engine/api/schemas.py` — `MappingOwnership` Pydantic model + `mapping_ownership_warnings` field on `FeedResponse`
- `engine/src/migrations_engine/management/feeds.py` — `_compute_ownership_warnings()` (single-feed) + `_batch_ownership_warnings()` (batch, one query) — both reuse the `outerjoin(Feed, ...)` / `or_(is_(None), and_(!= feed_id, status != "discarded"))` pattern from the 002id guard. Wired into `_source_contract_response()` and `list_source_contracts()`.

**Frontend (TypeScript/React):**
- `web/lib/feeds-api.ts` — `MappingOwnershipRecord` interface, `mappingOwnershipWarnings` on `FeedContractRecord`, raw param type + mapper (all three spots — no field-by-field cast)
- `web/app/projects/[id]/feeds/[feedId]/page.tsx` — Deleted dead `conflictOwnership` state, simplified `handleAnalyzeWithAi`, added amber warning card with proper `router.push` client-side navigation and "omit parenthetical when project-scoped" handling

**Docs:**
- `docs/domain/api.md` — `MappingOwnership` model + field docs + render contract + null-owner gap fix
- `docs/domain/source-model.md` — Note on `mapping_ownership_warnings` as persistent counterpart to the 002id guard

**Tests:**
- `engine/tests/test_mapping_ownership_warnings.py` — 6 tests (cross-feed warning, no-conflict null, project-scoped snapshot, discarded feed excluded, batch list matches single-feed, self-warning exclusion)

## Verification

- 6/6 new tests pass
- Full backend suite: 462 passed
- Frontend: 15 feeds-api tests pass
- TypeScript: zero new errors introduced
- OKF validation: zero warnings

## Notes

- The `conflictOwnership` dead code in `page.tsx` was removed — computed but never rendered.
- The ownership link uses `router.push` for client-side navigation (consistent with rest of file).
- `per_table_ownership` on the propose 409 is kept as complementary: "why did my action fail now" vs "does this feed have a problem right now".
