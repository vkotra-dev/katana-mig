# Plan 002i1 — Lookup Snapshot Collection Bug Fix

Task: [002i1](../tasks/002i1-lookup-snapshot-collect-bug-fix.md)
Domain: `source-model.md`

## Current State

`_select_lookup_snapshot_version()` (service.py:426-449) iterates through all lookup names from a mapping snapshot but returns on the first successful snapshot lookup. The return type is `str | None`. The single lookup name is passed to `user_prompt.txt.j2` where it shows only one lookup name.

## Objective

Collect ALL matching lookup snapshots into a list, return `list[dict[str, str]]`, update the user prompt template to iterate over the list.

## Out of Scope

- Feeds that use multiple destination tables (that's handled by task 002i3)
- Feed transformation instructions (handled by task 002i4)
- One-proc-per-table (handled by task 002i5)

## Blast Radius

- Low — single function change + one Jinja2 template update
- No new files
- No API surface changes
- No frontend changes

## File Changes

| File | Change |
|------|--------|
| `engine/src/migrations_engine/codegen/service.py` | Modify `_select_lookup_snapshot_version()` and `_build_user_prompt()` signature |
| `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2` | Iterate over `lookup_snapshots` list |

## Tests

- Unit test: mock 3 lookups, verify list of 3 returned
- Integration: seed feed with 2 lookups, verify both appear in prompt

## Verification

1. `cd engine && .venv/bin/python -m pytest -xvs` — zero new failures
2. `cd web && npx tsc --noEmit` — zero errors

## Pitfalls

- `_build_user_prompt()` parameter signature must change — ensure caller passes correct type
- Empty list is valid — template must handle `lookup_snapshots | length == 0`

## Commit

"fix(codegen): collect all lookup snapshots instead of returning first match"
