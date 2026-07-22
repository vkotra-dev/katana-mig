---
type: Task Plan
title: Wire "Suggest Standards" Button to the New Backend Endpoint
status: ready
---

# Task: 001es-wire-suggest-standards-button-to-backend-endpoint

## Context

Design spec: `docs/superpowers/specs/2026-07-22-codegen-coding-standards-prompt-extraction-design.md`.

`001er` (prerequisite, must land first) moves the coding-standards template content out of
`generateCodingStandardsTemplate` (`web/app/projects/[id]/codegen/page.tsx:81-179`) into a backend
YAML file plus a new `GET /projects/{project_id}/codegen-coding-standards-template` endpoint. This
task wires the existing "Suggest Standards" button to that endpoint instead of the local function,
and deletes the now-unused local function. **No behavior change from the user's point of view** —
same confirm-before-overwrite dialog, same result populated into the same editable textarea, same
Save button/flow.

## Requirements

1. `handleSuggestGlobalInstructions` (`page.tsx:477-491`) becomes async: keeps the exact same
   `window.confirm(...)` overwrite guard, but fetches the template from the new endpoint instead of
   calling `generateCodingStandardsTemplate` locally.
2. `generateCodingStandardsTemplate` (`page.tsx:81-179`, the ~100-line function) is deleted from
   `page.tsx` — its only call site is being replaced.
3. New frontend API function, `getCodegenCodingStandardsTemplate`, added to `web/lib/projects-api.ts`
   following the same pattern as the existing `getProject`/`saveCodegenInstructions` functions in
   that file.
4. Error handling: if the endpoint call fails, show it via the existing `setPageError` pattern
   already used elsewhere on this page (e.g. `handleSuggestFeedInstructions`'s catch block) — don't
   introduce a new error-display mechanism.
5. The editable textarea and `handleSaveGlobalInstructions` (unchanged, still saves to
   `codegen_instructions` via `saveCodegenInstructions`) are untouched.

## Out of Scope

- No change to the backend (`001er`'s scope, already landed by the time this task starts).
- No change to the per-feed "Feed-specific transformation instructions" flow
  (`generateTransformationInstructionsTemplate`, `handleSuggestFeedInstructions`) — separate
  feature, untouched.
- No change to `handleSaveGlobalInstructions`/the Save button.

## Dependencies

Depends on `001er` landing first — this task calls the endpoint `001er` creates. Before starting,
confirm it's live:
`grep -n "codegen-coding-standards-template" engine/src/migrations_engine/routes/projects.py`
must return a match. If it doesn't, stop; `001er` hasn't shipped yet.
