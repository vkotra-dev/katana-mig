# Summary: Task 001az — Per-Project Model Policy Overrides

## What changed
- Added a typed `ModelPolicy` model in `engine/src/migrations_engine/api/schemas.py`
  so project model overrides are no longer a freeform JSON blob.
- Added `resolve_model(task, policy, config)` in `engine/src/migrations_engine/ai/config.py`
  and threaded project policy through the AI adapter factory and all live AI call sites.
- Updated project create/update handling so `model_policy` is preserved, can be
  cleared explicitly, and is stored as structured JSON.
- Exposed the "Model Policy" section in `web/components/projects/ProjectEditForm.tsx`
  with 11 override inputs and placeholder text for the global default.
- Updated the project API client to map snake_case `model_policy` responses to the
  frontend model and serialize updates back to the backend shape.
- Added/updated tests in:
  - `engine/tests/test_model_policy.py`
  - `engine/tests/test_project_crud_api.py`
  - `web/lib/projects-api.test.ts`
  - `web/components/projects/__tests__/ProjectEditForm.test.tsx`
- Added a short project-domain note in `docs/domain/project.md` describing the
  per-project model policy behavior.

## Verification
- `PYTHONPATH=engine/src python -m pytest engine/tests/test_model_policy.py engine/tests/test_ai_adapter.py -q`
- `npm test -- lib/projects-api.test.ts components/projects/__tests__/ProjectEditForm.test.tsx components/projects/__tests__/CreateProjectDialog.test.tsx`

## Notes
- The DB-backed `engine/tests/test_project_crud_api.py` integration suite could not
  be rerun in this sandbox because the local MySQL endpoint was unavailable.
- The task commit is `ffcf417` (`feat(001az): add per-project model policy overrides with global fallback`).
