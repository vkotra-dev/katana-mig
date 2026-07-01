# Task 001ak — Fiber + Lookup Entity Models

**Plan:** `plans/2026-07-01-001ak-fiber-models.md`

## Scope

Add the fiber model layer used by the lookup AI flow:

- `ProjectFiber`
- `LookupSourceEntry`
- `LookupDestFeed`
- `LookupDestEntry`
- `LookupMapping`

Also add the API schemas, fiber routes, management service, and migration
`0019_fiber_models`.

## What changed

- Added the five ORM models and wired them to the existing feed/project model
  graph.
- Added Pydantic request/response schemas for fiber creation and lookup data.
- Added fiber create/list/get routes under `/projects/{project_id}/feeds/{feed_id}/fibers`.
- Added the migration that creates the new tables.
- Added tests covering the new models and API paths.
- Documented the new fiber layer in domain docs.

## Verification

- `python -m pytest tests/test_fiber_models.py -q`
- `python -m alembic upgrade head`
- `python -m alembic current`

