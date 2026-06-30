# Summary: Task 001ae — Lookup Snapshot Route Rehome

## What changed

- Moved lookup snapshot approval to `/projects/{project_id}/lookup-snapshots/{lookup_snapshot_id}/approve`.
- Kept lookup draft routes source-scoped under `/projects/{project_id}/sources/{source_definition_id}/lookup-maps`.
- Removed `source_definition_id` from lookup snapshot approval service flow and audit payload.
- Updated the frontend lookup API helper and lookup page to call the project-scoped approval route.
- Updated the engine and web tests to cover the new route shape.
- Documented the project-scoped lookup snapshot approval endpoint in `docs/domain/api.md`.

## Verification

- `cd engine && PYTHONPATH=src pytest tests/test_lookup_mapping_api.py -q`
- `cd web && npm test -- --run 'lib/lookup-api.test.ts' 'app/projects/[id]/sources/[sourceId]/lookup/page.test.tsx'`
- `git diff --check`

## Notes

- The lookup draft flow remains source-scoped.
- The snapshot model remains project-scoped.
