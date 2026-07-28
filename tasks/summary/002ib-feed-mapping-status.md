Task: tasks/completed/002ib-feed-mapping-status.md
Plan: plans/2026-07-28-002ib-feed-mapping-status.md
Commits: 9aeaf19 (feat), a49fec2 (call_log commit-timing fix), 80e5753 (artifact_id fix)

## Housekeeping note

Fully implemented and committed across three commits, but never closed out — task file still said
`status: pending`, no summary existed, and it wasn't listed in `TASK_INDEX.md`. Re-verified the
implementation against current code before writing this summary; everything still matches.

## Changes Made (as found/verified in the codebase)

- `AuthApiError` (`api/deps.py`) gained an optional `detail: dict[str, Any] | None` parameter.
- `FeedResponse.mapping_status: Literal["draft", "partial", "approved"] | None`
  (`api/schemas.py:273`).
- `_dedup_snapshots`, `_compute_status_from_snapshots`, `_compute_mapping_status`,
  `_batch_mapping_status` (`management/feeds.py:474-560`ish) — dedup to latest snapshot per
  `(source_definition_id, destination_object_name)` (tuple-keyed, safe for both single-feed and
  cross-feed batch use), `"rejected"` pulls the summary toward `"partial"` rather than being
  silently excluded, batch path avoids N+1 queries on the feed-list endpoint.
- `proposal.py`'s `IntegrityError` 409 handler includes `detail.per_table_status`. The separate
  `if not snapshots:` 409 (all proposed tables already approved elsewhere) intentionally stayed a
  409 rather than becoming a 200 — traced the `already_mapped_tables` logic and confirmed that
  path really does mean "blocked by an existing approval," not a harmless no-op.
- `call_log` is now committed immediately after `log_ai_call()` succeeds
  (`proposal.py`, from `a49fec2`), so a later rollback/uncommitted-409 can never lose the AI call
  audit log — this fixed a real regression found during review, not part of the original plan.
- `artifact_id=source_definition_id` added to the mapping proposal's `log_ai_call()` call
  (`80e5753`) so the feed page's `AiLogViewer` (which queries by `artifact_id == feedId`) actually
  surfaces these log entries — verified against the existing `backfill_artifact_id(...,
  source_definition_id)` convention already used elsewhere in the same function.

## Domain Updates Required

- `docs/domain/api.md` — **Updated**. `SourceContractResponse`'s JSON example includes
  `mapping_status`, with a paragraph explaining its four values and the rejected/dedup rules
  (lines ~2050-2079).
- Found and fixed a separate, adjacent doc bug while closing this out: the propose endpoint's 409
  documentation (lines ~1014-1021) had drifted to describe **task 002ic's** planned
  `per_table_ownership` detail as if it were already live on the "all tables already approved"
  path — it isn't; 002ic hasn't been implemented. Corrected the doc to describe what's actually
  shipped today (`per_table_status` on the concurrent-duplicate path; no detail on the
  already-approved path) and marked 002ic's addition as planned/not-yet-live rather than
  documented as current behavior.

## Tests

```
.venv/bin/python -m pytest engine/tests/test_mapping_status.py -q
17 passed

.venv/bin/python -m pytest engine/tests -q
452 passed

.venv/bin/python scripts/validate_okf.py
✓ All files OKF-compliant. No issues found (12/12 domain pages).
```
