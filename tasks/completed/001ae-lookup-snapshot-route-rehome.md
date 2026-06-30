# Task 001ae — Lookup Snapshot Route Rehome

**Plan:** `plans/2026-06-30-001ae-lookup-snapshot-route-rehome.md`

## Domain

- `docs/domain/api.md` — machine-facing route contract
- `docs/domain/source-model.md` — lookup mapping ownership and approval flow
- `docs/domain/security.md` — project-scope boundaries

## Depends on

- 001x (lookup mapping flow exists)
- 001x follow-up discussion: keep `LookupSnapshot` project-scoped

## Scope

Move lookup snapshot approval to a project-scoped route while keeping lookup
drafts source-scoped. The data model stays project-scoped for snapshots; the URL
shape should reflect that ownership.

## Current State

- Draft lookup maps live under `/projects/{project_id}/sources/{source_definition_id}/lookup-maps`.
- Lookup snapshot approval still lives under the source-scoped path.
- The UI helper in `web/lib/lookup-api.ts` still constructs the source-scoped
  approval URL.
- The API docs do not yet describe the project-scoped snapshot route.

## Objective

Rehome lookup snapshot approval to `/projects/{project_id}/lookup-snapshots`
and update the frontend and docs to use the project-level route.

## Out of Scope

- Adding `source_definition_id` to `LookupSnapshot`
- Reworking the lookup draft route
- Changing lookup generation semantics beyond what is required for the route move
- Adding unrelated lookup features

## Blast Radius

- `docs/domain/api.md`
- `engine/src/migrations_engine/routes/lookup.py`
- `engine/src/migrations_engine/management/lookup_mapping.py`
- `web/lib/lookup-api.ts`
- `web/app/projects/[id]/sources/[sourceId]/lookup/page.tsx`
- `web/lib/lookup-api.test.ts`
- `web/app/projects/[id]/sources/[sourceId]/lookup/page.test.tsx`
- `engine/tests/test_lookup_mapping_api.py`

## File Changes

- Add a project-scoped lookup snapshot approval route.
- Keep draft lookup map endpoints source-scoped.
- Update the lookup API client and page to call the new approval route.
- Update the API docs to reflect the new resource ownership.
- Add or adjust regression tests for the new path.

## Tests

- `cd engine && PYTHONPATH=src pytest tests/test_lookup_mapping_api.py -q`
- `cd web && npm test -- --run 'lib/lookup-api.test.ts' 'app/projects/[id]/sources/[sourceId]/lookup/page.test.tsx'`

## Verification

- Lookup snapshot approval works through the project-scoped route.
- Draft lookup maps still work under the source-scoped route.
- The UI helper calls the new project-scoped snapshot route.
- The API docs describe the new lookup snapshot ownership.

## Pitfalls

- Do not add `source_definition_id` to `LookupSnapshot` just to satisfy the URL.
- Do not break the source-scoped draft flow.
- Do not leave the frontend pointing at the old source-scoped snapshot path.

## Commit

- `feat(lookup): rehome snapshot approval to project scope`
