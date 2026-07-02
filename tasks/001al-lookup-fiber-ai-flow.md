# Task 001al — Lookup Fiber AI Flow

**Plan:** `plans/2026-07-01-001al-lookup-fiber-ai-flow.md`

## Domain

- `docs/domain/api.md` — lookup fiber lifecycle; `deferred → inputs_ready → ai_running → mapped`

## Scope

Wire up the AI-powered lookup mapping flow for lookup-type fibers:

- New `lookup_mapping` AI slot in `engine.yaml` / `ai/config.py` / `ai/factory.py`
- `POST /fibers/{fiber_id}/lookup-inputs` — submit source CSV + destination CSV, trigger AI mapping proposals, store `LookupSourceEntry`, `LookupDestFeed`, `LookupDestEntry`, `LookupMapping` rows
- GET endpoints for source entries, dest feed, dest entries, mappings
- `PATCH /fibers/{fiber_id}/mappings/{mapping_id}` — operator overrides a proposed mapping
- Status transitions: `deferred → inputs_ready` on submit; `inputs_ready → ai_running → mapped` on AI completion

## Tasks (2)

1. **AI slot** — extend `MigrationModelConfig` + `_SLOT_MAP` + both `engine.yaml` fixtures; update existing `test_ai_config.py` + `test_ai_adapter.py`.
2. **Service + routes** — `submit_lookup_inputs`, entity list helpers, `patch_mapping` in `management/fibers.py`; seven route handlers in `routes/fibers.py`.

## Success criteria

- `lookup_mapping` slot resolves via `get_adapter("lookup_mapping")`
- `POST .../lookup-inputs` with two CSVs returns proposed mappings
- `PATCH .../mappings/{id}` updates a mapping's `dest_entry_id` / `dest_row`
- All tests pass

## Execution order

Execute after 001ak. This is in the feed/fiber/comment/AI priority stream and
should land before the later-phase delivery tickets. Unblocks 001an.
