# Summary: 001gz — Reset Codegen Instructions to Defaults

## What was done

Added a "Reset to defaults" button to the codegen page's global instructions section.
When clicked with confirmation, it resets the project's saved `codegen_instructions`
to the merged YAML template defaults (coding_standards + logging_standards),
overwriting any custom edits.

## Changes

**Backend** (`engine/src/migrations_engine/routes/projects.py`):
- Added `POST /projects/{project_id}/codegen-instructions/reset` endpoint
- Renders YAML templates server-side and saves the result via `update_project()`
- Requires `central_team` role

**Frontend API** (`web/lib/projects-api.ts`):
- Added `resetCodegenInstructions(token, projectId)` calling the new POST endpoint

**Frontend UI** (`web/app/projects/[id]/codegen/page.tsx`):
- Replaced "Suggest Standards" button with "Reset to defaults" button
- Button placed at bottom-left of textarea (amber destructive styling)
- "Save" button stays at bottom-right
- Confirmation dialog before reset
- Loading state during API call
- Success/error toast messages

**Tests** (`engine/tests/test_codegen_system_prompt.py`):
- Added `test_reset_codegen_instructions_overwrites_with_yaml_template`
- Verifies endpoint overwrites custom text with merged YAML template
- Asserts coding standards header and logging standards are present

**Docs** (`docs/domain/api.md`, `docs/domain/project.md`):
- Documented new POST endpoint in api.md
- Updated codegen_instructions section in project.md to mention reset behavior
- Bumped api.md timestamp

## Verification

- Backend: 405 tests pass, 0 failures
- Frontend: no new type errors introduced in codegen/page.tsx
- Pre-existing type errors in other files unchanged

## Domain updates

- `docs/domain/api.md` — documented new POST endpoint, bumped timestamp
- `docs/domain/project.md` — documented reset behavior for codegen_instructions
