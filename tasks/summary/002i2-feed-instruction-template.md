Task: tasks/completed/002i2-feed-instruction-template.md
Plan: plans/2026-07-24-002i2-feed-instruction-template.md
Commits: a90944e (implementation), d122e1d (fix placeholder leak), fba7208 (plan + task files)

## Changes Made

### `engine/src/migrations_engine/ai/prompts/feed_transformation_instructions.yaml` (new)
- YAML template that wraps user-entered feed transformation instructions with consistent
  AI-facing context and framing.

### `engine/src/migrations_engine/codegen/feed_instructions.py` (new)
- `render_feed_instructions_template(text: str | None) -> str`: renders user text through the
  Jinja2 template, returns "(none)" for empty/None input.

### `engine/src/migrations_engine/codegen/service.py`
- Imported `render_feed_instructions_template` from `feed_instructions.py`.
- Called the renderer in `_build_user_prompt()` and passed the rendered value to Jinja2 context.

### `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2`
- Replaced raw `{{ source_definition.transformation_instructions.strip() }}` injection with the
  framed `feed_instructions` variable.

### `engine/tests/test_codegen_service_api.py`
- `test_render_feed_instructions_template_none`: verifies None/empty input returns "(none)".
- `test_render_feed_instructions_template_with_content`: verifies non-empty input is wrapped
  with template structure and placeholders don't leak.

## Deviations from Plan

None. Implementation matches the plan's File Changes section exactly.

## Domain Updates Required

- None — purely an internal prompt structure change, no domain concepts affected.

## Tests

`.venv/bin/python -m pytest engine/tests -q` — all tests pass, 0 failures.

## Verification

`scripts/validate_okf.py` — all 12 domain docs pass, 0 warnings.
