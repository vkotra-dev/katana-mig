# 001ah — Delivery Bundle Sequencing

Implemented project schema analysis for delivery bundle ordering.

What changed:
- Added `ProjectSchemaAnalysis` plus migration `0016_project_schema_analysis`
- Added `POST`/`GET /projects/{project_id}/schema-analysis`
- Ordered delivery bundles by dependency sequence and numbered SQL blocks when analysis exists
- Added Sources tab analysis banner and codegen-page report panel
- Added frontend API helpers and tests

Verification:
- `python -m alembic upgrade head`
- `pytest engine/tests/test_schema_analysis_api.py -q`
- `npm test -- --run lib/codegen-api.test.ts components/projects/__tests__/SourceList.test.tsx 'app/projects/[id]/codegen/page.test.tsx'`
