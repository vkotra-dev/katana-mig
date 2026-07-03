# Task 001am — Mapping Fiber AI Flow

**Plan:** `plans/2026-07-01-001am-mapping-fiber-ai-flow.md`

## Domain

- `docs/domain/api.md` — mapping fiber lifecycle; `created → ai_running → mapped`

## Scope

Wire up the AI-powered field binding flow for domain-object (mapping) fibers:

- New `feed_analysis` AI slot in `engine.yaml` / `ai/config.py` / `ai/factory.py`
- `POST /projects/{project_id}/feeds/{feed_id}/analyze` — reads the approved `FeedSlice` header CSV, calls AI to propose field bindings for every domain-object `ProjectFiber` attached to this feed, stores results in `fiber.field_bindings`, sets fiber statuses `created → mapped`
- Status transition: fibers transition `created → ai_running → mapped` during the analyze call

## Tasks (2)

1. **AI slot** — extend `MigrationModelConfig` + `_SLOT_MAP` + both `engine.yaml` fixtures; update existing AI config/adapter tests.
2. **Service + route** — `analyze_feed` service in `management/fibers.py`; `POST /feeds/{feed_id}/analyze` route in `routes/fibers.py`; register second router prefix in `app.py`.

## Success criteria

- `feed_analysis` slot resolves via `get_adapter("feed_analysis")`
- `POST .../feeds/{feed_id}/analyze` returns fiber list with `field_bindings` populated
- Unapproved feed slice returns 409
- All tests pass

## Execution order

Execute after 001ak. This is in the feed/fiber/comment/AI priority stream and
should land before the later-phase delivery tickets. Unblocks 001an.
