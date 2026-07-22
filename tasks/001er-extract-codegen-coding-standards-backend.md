---
type: Task Plan
title: Extract Codegen Coding Standards Template into a Backend Prompt File (Backend)
status: ready
---

# Task: 001er-extract-codegen-coding-standards-backend

## Context

Design spec: `docs/superpowers/specs/2026-07-22-codegen-coding-standards-prompt-extraction-design.md`.

The codegen page's "Suggest Standards" button (`web/app/projects/[id]/codegen/page.tsx`) populates
the editable "Coding Standards & Global Instructions" textarea (backed by
`ProjectDefinition.codegen_instructions`) from `generateCodingStandardsTemplate`
(`page.tsx:81-179`), ~100 lines of hardcoded template text living entirely in frontend TypeScript.
This is backend-only preparatory work: move that content into a new backend-owned YAML file and
expose it via a new endpoint. The frontend button itself is not touched by this task — that's
`001es`.

Confirmed via the actual template files this session: `codegen_instructions` is already the
codegen system prompt (`codegen/templates/system_prompt.txt.j2:54-56`) and
`transformation_instructions` is already the user prompt (`user_prompt.txt.j2:13-15`) — this task
does not change that wiring at all, it only changes where the *suggested starter text* for
`codegen_instructions` comes from.

## Requirements

1. New file `engine/src/migrations_engine/ai/prompts/codegen_coding_standards.yaml` with this
   shape: `shared_header`, `shared_footer` (the schema-scoping intro and general-best-practices
   text, common to every engine today), plus `mssql`, `postgresql`, `mysql`, `oracle` (each
   engine's specific-standards block). Content transcribed verbatim from the current
   `generateCodingStandardsTemplate` function — see the plan for the exact text to copy.
2. A new, small, dedicated loader function — **not** the existing `Prompt` class
   (`ai/prompt.py`), which is built for actual AI system/user prompt pairs and has a fixed
   `system`/`user` key shape that doesn't fit a file with one section per engine. Same
   conventions (same directory, YAML format, `$name` merge-field substitution via
   `string.Template`), separate small function.
3. New endpoint `GET /projects/{project_id}/codegen-coding-standards-template` returning
   `{"template": "<rendered text>"}`, reading the project's `domain_config`
   (`target_db_engine`/`staging_schema`/`destination_schema`) to drive the render.
4. Rendered output must match `generateCodingStandardsTemplate`'s current output byte-for-byte for
   every engine value (mssql/postgresql/mysql/oracle/empty/unrecognized) — this is a relocation of
   existing content, not a rewrite of it.

## Out of Scope

- The frontend "Suggest Standards" button itself — still calls the local
  `generateCodingStandardsTemplate` function until `001es` lands. Do not remove or change
  `page.tsx` in this task.
- The `Prompt` class, or any existing `ai/prompts/*.yaml` file used by a real AI call
  (`mapping.yaml`, `feed_field_mapping.yaml`, etc.) — untouched.
- `codegen/templates/system_prompt.txt.j2` / `user_prompt.txt.j2` and the actual "Generate SQL"
  codegen trigger flow (`_build_system_prompt`/`_build_user_prompt` in `codegen/service.py`) —
  confirmed already correct, explicitly not touched by this work.
- The per-feed "Feed-specific transformation instructions" flow (`001en`'s work,
  `generateTransformationInstructionsTemplate`) — separate feature, untouched.

## Dependencies

None. Must land before `001es`.
