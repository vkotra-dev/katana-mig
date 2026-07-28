Task: tasks/completed/001fb-lookup-prompt-id-value-contract.md
Plan: plans/2026-07-23-001fb-lookup-prompt-id-value-contract.md

## Housekeeping note

This task's `status: active` was stale and it wasn't tracked in `TASK_INDEX.md` at all — found
during a broader audit of tasks that were implemented but never closed out. Verified the full
contract fix against the current code before writing this summary; everything in the task's
"Correct Output Contract" and "Objective" sections is already shipped.

## Changes Made (as found in the codebase)

- `_LookupProposal` (`management/fibers.py:82-86`) — `dest_id: str` (business key, e.g. `"3"`),
  `dest_value: str` (human label, e.g. `"Approved"`), not the old `dest_id: UUID` shape.
- `ai/prompts/lookup_mapping.yaml` — explicit, example-driven prompt asking for exactly
  `{dest_id, dest_value, source_value, confidence_score}` per destination row, including the
  worked example from the task spec (APPROVED/PENDING/CANCELLED, ids 3/1/6). Deduplicated
  destination rows are sent (`deduped_dest_rows`, `fibers.py:791`), not raw repeated CSV rows.
- `dest_row` construction (`fibers.py:862-865`) — `{"id": proposal.dest_id, "label": proposal.dest_value}`,
  clean business key + AI-extracted label, no heuristic guessing on raw multi-column rows.
- Downstream consumers (`_sync_lookup_value_map_from_proposed_mappings`, the fiber-healing sync
  in `list_fibers`) still call the old `_extract_destination_label()` heuristic, but since
  `dest_row` is now always `{"id": ..., "label": ...}`, the heuristic's first priority match
  (`row.get("label")`) hits immediately and returns the correct value — confirmed this is not a
  latent bug, just a redundant-but-harmless call on already-clean data.
- `FakeLookupAdapter` (`engine/tests/test_lookup_fiber_api.py:24-47`) already returns the current
  contract shape; explicit assertions on `dest_row["id"]`/`dest_row["label"]` and the
  business-key-not-UUID invariant exist (lines 191-193, 307).

## Domain Updates Required

- `docs/domain/source-model.md` ("Lookup mapping" section, lines 446-459) — **Verified, no change
  needed**. Already accurately describes the current `dest_id`/`dest_value`/`source_value`/
  `confidence_score` AI proposal contract and the `_sync_lookup_value_map_from_proposed_mappings`
  flow — this page was kept in sync with the real implementation even though the task file itself
  was never closed.

## Tests

```
.venv/bin/python -m pytest engine/tests/test_lookup_fiber_api.py -q
6 passed, 2 warnings
```

`.venv/bin/python scripts/validate_okf.py` — zero warnings (no domain page changed, none needed).
