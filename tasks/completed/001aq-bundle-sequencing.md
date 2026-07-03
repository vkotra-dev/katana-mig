# Task 001aq — Delivery Bundle 0000/0001+ Sequencing

**Plan:** `plans/2026-07-01-001aq-bundle-sequencing.md`

## Domain

- `docs/domain/ui.md` — SQL bundle delivery section
- `docs/domain/api.md` — lookup fiber and delivery bundle sequencing rules

## Scope

Generate lookup UPSERT SQL when a lookup fiber is triggered, create a
`0000_{fiber_key}` codegen artifact for approved lookup snapshots, and ensure
delivery bundles emit lookup artifacts before numbered domain object SQL.

## What changed

- Added `engine/src/migrations_engine/codegen/lookup_upsert.py`
- Wired lookup-fiber trigger handling in `engine/src/migrations_engine/management/fibers.py`
- Reworked `build_delivery_bundle_text` ordering in `engine/src/migrations_engine/codegen/service.py`
- Added sequencing tests covering generator output, fiber trigger behavior, and bundle ordering

## Verification

- `PYTHONPATH=.../engine/src python -m pytest engine/tests/test_bundle_sequencing.py -v`
- `PYTHONPATH=.../engine/src python -m pytest engine/tests/test_schema_analysis_api.py -k "delivery_bundle or schema_analysis" -v`
- `PYTHONPATH=.../engine/src python -m pytest engine/tests/test_codegen_service_api.py -k "delivery_bundle_returns_active_artifacts" -v`
- `git diff --check`

## Commit

- `452327f` - `feat(001aq): trigger lookup codegen and sequence delivery bundle SQL`
