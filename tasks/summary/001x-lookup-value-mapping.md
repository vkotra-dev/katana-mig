# Summary 001x — Lookup Value Mapping

Implemented the lookup mapping flow across engine and web:

- Added `LookupValueMap` persistence plus the `0012_lookup_value_maps` Alembic migration.
- Added lookup request/response schemas and a lookup management service for drafts, snapshot generation, and approval.
- Added `/projects/{project_id}/sources/{source_definition_id}/lookup-maps`, `/lookup-snapshots`, and `/lookup-snapshots/{id}/approve`.
- Registered the lookup router in the FastAPI app.
- Added the lookup contract docs to `docs/domain/source-model.md`.
- Wired the UI to a lookup entry screen at `/projects/[id]/sources/[sourceId]/lookup` with:
  - source value summaries
  - draft destination table entry
  - per-value mappings
  - generate snapshot
  - approve snapshot
- Added lookup API helpers and client tests.
- Added backend model, service, and API tests.

Verification:

- `cd engine && PYTHONPATH=src pytest tests/test_lookup_mapping_models.py tests/test_lookup_mapping_service.py tests/test_lookup_mapping_api.py -q`
- `cd web && npm test -- lib/lookup-api.test.ts 'app/projects/[id]/sources/[sourceId]/lookup/page.test.tsx'`

Result:

- 5 engine tests passed
- 5 web tests passed
