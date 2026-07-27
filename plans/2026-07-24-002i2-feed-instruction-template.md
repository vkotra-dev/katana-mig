# Plan 002i2 — Feed Instruction Template

Task: [002i2](../tasks/002i2-feed-instruction-template.md)
Domain: (none — internal prompt structure only)

## Current State

`user_prompt.txt.j2:24-27` does a raw dump of `source_definition.transformation_instructions` into the user prompt. No template file, no renderer function.

## Objective

Create YAML template + Python renderer (following `coding_standards.py` pattern) that wraps user text with consistent AI-facing context. Integrate into `_build_user_prompt()`.

## Out of Scope

- Multi-table codegen loop
- One-proc-per-table prompt rules
- Cross-proc FK resolution
- Any other prompt changes

## Blast Radius

- Low — two new files, one file modified (service.py), one Jinja2 template updated
- No API surface changes
- No frontend changes

## File Changes

| File | Change |
|------|--------|
| `engine/src/migrations_engine/ai/prompts/feed_transformation_instructions.yaml` | **New** — YAML template |
| `engine/src/migrations_engine/codegen/feed_instructions.py` | **New** — Renderer function |
| `engine/src/migrations_engine/codegen/service.py` | Import renderer, call in `_build_user_prompt()` |
| `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2` | Replace raw injection with `feed_instructions` |

## Tests

- Unit: `render_feed_instructions_template(None)` → "(none)"
- Unit: `render_feed_instructions_template("strip leading/trailing spaces")` → wraps in template

## Verification

1. `cd engine && .venv/bin/python -m pytest -xvs` — zero new failures
2. `cd web && npx tsc --noEmit` — zero errors

## Pitfalls

- Renderer must handle `None` input gracefully
- Template guard `{% if feed_instructions %}` replaces `{% if source_definition.transformation_instructions %}`

## Commit

"feat(codegen): add YAML template for feed-specific transformation instructions"
