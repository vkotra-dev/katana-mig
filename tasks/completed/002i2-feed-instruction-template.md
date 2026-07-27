---
id: 002i2
title: Create YAML template for feed-specific transformation instructions
status: completed
created: 2026-07-24
priority: medium
depends-on: []
domain: engine
---

# Task 002i2 — Feed Instruction Template

## Context

User-entered transformation instructions are dumped raw into the user prompt (`user_prompt.txt.j2:24-27`) without consistent framing. Unlike coding standards (which go through `render_coding_standards_template()`), there is no YAML template to control prompt structure. Users type free text into a textarea and the system just concatenates it.

This task creates a standardized YAML template that wraps user text with consistent AI-facing context, following the existing `lookup_mapping.yaml` pattern.

## Domain Updates Required

- None — this is purely an internal prompt structure change, no domain concepts change

## Current State

- `user_prompt.txt.j2:24-27` does a raw dump: `{{ source_definition.transformation_instructions.strip() }}`
- No template file, no renderer function
- User text has no framing: the AI doesn't know these are "FEED-SPECIFIC TRANSFORMATION RULES" or that they must be applied

## Objective

1. Create `engine/src/migrations_engine/ai/prompts/feed_transformation_instructions.yaml`
2. Create `engine/src/migrations_engine/codegen/feed_instructions.py` renderer
3. Integrate into `_build_user_prompt()` — pass rendered feed instructions to Jinja2 template
4. Update `user_prompt.txt.j2` to use the `feed_instructions` variable

## Files Changed

| File | Change |
|------|--------|
| `engine/src/migrations_engine/ai/prompts/feed_transformation_instructions.yaml` | **New** — YAML template |
| `engine/src/migrations_engine/codegen/feed_instructions.py` | **New** — Renderer function |
| `engine/src/migrations_engine/codegen/service.py` | Import renderer, call it in `_build_user_prompt()` |
| `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2` | Replace raw injection with `feed_instructions` variable |

## Tests

- Unit test: render with None input → returns "(none)"
- Unit test: render with sample text → wraps in template structure
- No regression: existing feeds with/without transformation instructions must produce valid prompts

## Verification

1. `cd engine && .venv/bin/python -m pytest -xvs` — zero new failures
2. No TypeScript errors in frontend

## Pitfalls

- The renderer function must handle `None` input gracefully (no transformation instructions set)
- The Jinja2 template already has `{% if source_definition.transformation_instructions %}` guard — the new `feed_instructions` variable uses the same guard

## Commit

"feat(codegen): add YAML template for feed-specific transformation instructions"
