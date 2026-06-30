# Summary: Task 001y — Code Generation Service

## What changed
- Added a code generation backend slice in `engine/src/migrations_engine/codegen/service.py`.
- Added `POST /projects/{project_id}/sources/{source_definition_id}/codegen`,
  `GET /projects/{project_id}/codegen-artifacts`, `GET /projects/{project_id}/codegen-artifacts/{codegen_artifact_id}`,
  and `GET /projects/{project_id}/delivery-bundle` in `engine/src/migrations_engine/routes/codegen.py`.
- Extended `engine/src/migrations_engine/api/schemas.py` with `CodegenTriggerResponse`,
  `CodegenArtifactResponse`, and `DeliveryBundleResponse`.
- Registered the new router in `engine/src/migrations_engine/app.py`.
- Added frontend client helpers in `web/lib/codegen-api.ts`.
- Added the new code generation page in `web/app/projects/[id]/codegen/page.tsx`.
- Added backend and frontend coverage in:
  - `engine/tests/test_codegen_service_api.py`
  - `web/lib/codegen-api.test.ts`
  - `web/app/projects/[id]/codegen/page.test.tsx`
- Added API domain documentation for the new codegen endpoints in `docs/domain/api.md`.
- Added lightweight AI SDK shims in `engine/src/migrations_engine/ai/anthropic_adapter.py`
  and `engine/src/migrations_engine/ai/openai_adapter.py` so the local test environment can import
  the app without the provider packages installed.

## Verification
- `source ../../../.venv/bin/activate && PYTHONPATH=src KATANA_BOOTSTRAP_ADMIN_EMAIL=admin@example.com KATANA_BOOTSTRAP_ADMIN_PASSWORD=adminpass python -m pytest tests/test_ai_adapter.py tests/test_codegen_service_api.py -q`
- `npm test -- lib/codegen-api.test.ts 'app/projects/[id]/codegen/page.test.tsx'`
- `npm run build`

## Notes
- Codegen generation uses the `script_generation` AI slot.
- Lookup snapshots are optional; the backend proceeds even when no approved lookup snapshot exists.
- The delivery bundle downloads as `delivery-bundle.sql`.
