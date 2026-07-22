# Design: Extract Codegen Coding Standards Template into a Backend Prompt File

## Context

The codegen page's "Coding Standards & Global Instructions" section has a "Suggest Standards"
button (`handleSuggestGlobalInstructions`, `web/app/projects/[id]/codegen/page.tsx:477-491`) that
populates the editable `globalInstructions` textarea (backed by
`ProjectDefinition.codegen_instructions`, which flows into `system_prompt.txt.j2` for the actual
codegen AI call — this field functions as the project-level "system prompt", while the per-feed
`transformation_instructions` field functions as the "user prompt", confirmed via
`codegen/templates/system_prompt.txt.j2:54-56` and `user_prompt.txt.j2:13-15`).

The button's content comes from `generateCodingStandardsTemplate` (`page.tsx:81-179`), ~100 lines
of hardcoded template text living entirely in frontend TypeScript, including a very large
MSSQL-specific block (~90 lines, shipped under task `001ct` — XACT_ABORT, THROW syntax, MERGE
OUTPUT logging to `mig_upsert_log`, duplicate-key checks, idempotent DDL, etc.) plus much shorter
blocks for PostgreSQL, MySQL, and Oracle. Three values get interpolated: destination schema name,
staging schema name, and a display name for the DB engine, each with a fallback default when the
project's config doesn't specify one.

## Objective

Move this content out of frontend TypeScript into a backend-owned prompt file, without changing
the button's behavior from the user's perspective — same confirm-before-overwrite dialog, same
result populated into the same editable field.

## Decision: file shape

**One YAML file, one section per database engine** —
`engine/src/migrations_engine/ai/prompts/codegen_coding_standards.yaml` — rather than a separate
file per engine. Sections: `shared_header`, `shared_footer` (schema-scoping intro and
general-best-practices text, common to every engine today) plus `mssql`, `postgresql`, `mysql`,
`oracle` (each engine's specific-standards block, transcribed verbatim from the current `if/else`
branches).

## Decision: loading mechanism

**A small, dedicated loader function — not the existing `Prompt` class** (`ai/prompt.py`).
`Prompt.__init__` hardcodes a fixed `system`/`user` key shape per file
(`ai/prompt.py:21-24`: `self._system = data["system"]`, `self._user = data["user"]`) — built for
files backing one actual AI call's system/user prompt pair. This file's shape is fundamentally
different: a menu of alternative sections selected by engine name, and its output is human-facing
reference/seed text that a user edits before it ever reaches an AI call, not a prompt sent directly
to a model. Forcing this into `Prompt` would mean either generalizing a class real AI call sites
depend on (`mapping.yaml`, `feed_field_mapping.yaml`, `source_analysis.yaml`, etc.) for a shape it
was never designed for, or bolting an awkward exception onto it. A separate loader keeps the same
conventions that matter (same directory, same YAML format, same `$name`/`${name}` merge-field
substitution via `string.Template`) without touching or complicating the class other prompts
depend on.

The loader:
1. Reads `codegen_coding_standards.yaml`.
2. Looks up the section for `db_engine.lower()` (falls back to no engine-specific block if
   unrecognized, matching today's behavior where an unmatched `lowerEngine` just leaves
   `specificStandards` empty).
3. Substitutes `$dest`/`$stg`/`$engineName` into `shared_header` via `string.Template`, using the
   same fallback defaults as today ("destination"/"staging"/"target database" when the project
   config value is empty).
4. Concatenates `shared_header` + the engine-specific block + `shared_footer`, matching the exact
   current concatenation shape (the engine block appends directly onto the end of the "Database
   Engine Conventions" paragraph in `shared_header`, no extra blank line — mirroring today's
   `` `...pertinent to ${engineName}.${specificStandards}` `` string interpolation).

## New endpoint

`GET /projects/{project_id}/codegen/coding-standards-template` — reads
`ProjectDefinition.domain_config` (`targetDbEngine`, `stagingSchema`, `destinationSchema`), calls
the loader, returns the rendered text as a plain string in the response body.

## Frontend change

`handleSuggestGlobalInstructions` (`page.tsx:477-491`) becomes async: same
`window.confirm(...)` overwrite guard, but calls the new endpoint instead of the local
`generateCodingStandardsTemplate` function, then `setGlobalInstructions(template.trim())` exactly
as today. `generateCodingStandardsTemplate` itself is deleted from `page.tsx` once the endpoint
call replaces its only call site. The editable textarea and `handleSaveGlobalInstructions`
(saving to `codegen_instructions` via `saveCodegenInstructions`) are unchanged — this task only
relocates where the *suggested* text comes from, not how it's edited or saved.

## Out of Scope

- No change to `codegen_instructions`/`transformation_instructions`'s consumption in
  `system_prompt.txt.j2`/`user_prompt.txt.j2` — unaffected.
- No change to the per-feed "Generate Instructions" flow (`001en`'s work) — a separate button,
  separate field, separate template function (`generateTransformationInstructionsTemplate`),
  untouched by this task.
- No change to the `Prompt` class or any existing `ai/prompts/*.yaml` file used by a real AI call.
- No new merge fields beyond the 3 that already exist (`dest`, `stg`, `engineName`) — this is a
  relocation of existing content and logic, not a content redesign.

## Testing

- Backend: new test(s) for the loader function — one per engine (mssql/postgresql/mysql/oracle)
  asserting the rendered text contains the engine-specific block and the substituted schema names;
  one for an unrecognized/empty engine falling back to just the shared header/footer with default
  placeholder names ("destination"/"staging"/"target database").
- Backend: new test for the endpoint — asserts 200 and that the response body matches the loader's
  output for a project with a known `domain_config`.
- Frontend: update the existing `"suggests coding standards template when clicking Suggest
  Standards"` test (`page.test.tsx`, exact name to confirm when writing the plan) to mock the new
  endpoint call instead of asserting on the local template function's output directly; confirm the
  overwrite-confirm dialog behavior is unchanged.
