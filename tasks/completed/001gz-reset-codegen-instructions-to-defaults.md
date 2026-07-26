---
id: 001gz
title: Reset Codegen Instructions to Defaults
status: ready
created: 2026-07-26
priority: medium
domain: backend / frontend / codegen
depends-on: []
---

# Task 001gz — Reset Codegen Instructions to Defaults

- **Plan**: [2026-07-24-001gz-reset-codegen-instructions-to-defaults.md](../plans/2026-07-24-001gz-reset-codegen-instructions-to-defaults.md)
- **Domain**: [api.md](../docs/domain/api.md), [project.md](../docs/domain/project.md)

## Context

The codegen page has a "Coding Standards & Global Instructions" textarea that stores `project_definition.codegen_instructions`. On first load, it is pre-populated from `render_coding_standards_template()` which merges both `codegen_coding_standards.yaml` and `codegen_logging_standards.yaml`. Users can edit and save custom text.

Currently the "Suggest Standards" button only previews the template in the textarea — it does not save. There is no way to reset the saved value back to the YAML template defaults.

## Objective

Replace the "Suggest Standards" button with a "Reset to defaults" button that, when clicked (with confirmation), calls a new backend endpoint that renders the YAML template and saves it as `project_definition.codegen_instructions`, overwriting any custom text the user has saved.

## Out of Scope

- Do NOT change the existing "Save" button behavior
- Do NOT change how the YAML files themselves are structured
- Do NOT add per-feed-level reset — only global project-level reset
- Do NOT modify the PATCH `codegen-instructions` endpoint (it stays for normal save operations)
- Do NOT touch the system_prompt.txt.j2 Jinja template — the pipeline already reads `project_definition.codegen_instructions`

## Blast Radius

| File | Action | What changes |
|------|--------|-------------|
| `engine/src/migrations_engine/routes/projects.py` | modify | Add `reset_codegen_instructions` POST endpoint |
| `web/lib/projects-api.ts` | modify | Add `resetCodegenInstructions()` function |
| `web/app/projects/[id]/codegen/page.tsx` | modify | Replace "Suggest Standards" with "Reset to defaults" button at bottom-left of textarea |
| `engine/tests/test_codegen_system_prompt.py` | modify | Add test for reset endpoint |
| `tasks/TASK_INDEX.md` | modify | Add entry for 001gz |

## Domain Updates Required

- `docs/domain/api.md` — document the new POST `/projects/{project_id}/codegen-instructions/reset` endpoint
- `docs/domain/project.md` — update `codegen_instructions` section to mention reset behavior

## Files to Read Before Execution

- `engine/src/migrations_engine/routes/projects.py` (lines 136-167) — existing routes to follow pattern
- `web/lib/projects-api.ts` (lines 350-565) — existing API functions
- `web/app/projects/[id]/codegen/page.tsx` (lines 387-423, 557-594) — existing handler and UI
- `engine/src/migrations_engine/codegen/coding_standards.py` (lines 12-41) — `render_coding_standards_template()`
- `docs/domain/api.md` — existing API docs
- `docs/domain/project.md` — existing project docs

## Verification

```bash
# Backend: run the new test and full suite
.venv/bin/python -m pytest engine/tests/test_codegen_system_prompt.py -q
.venv/bin/python -m pytest engine/tests -q

# Frontend: verify no type errors (no dedicated test file exists for this page)
cd web && npx tsc --noEmit
```

## Pitfalls

- Do NOT delete the existing `patch_codegen_instructions` endpoint — it handles normal save operations
- The reset endpoint must use `get_central_team_user` guard (same as existing PATCH endpoint)
- The "Suggest Standards" button must be completely replaced, not kept alongside the new button
- The confirmation dialog must match the existing pattern (`window.confirm` with clear message)
