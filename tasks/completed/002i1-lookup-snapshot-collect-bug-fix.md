---
id: 002i1
title: Fix lookup snapshot collection to return all matching snapshots
status: completed
created: 2026-07-24
priority: high
depends-on: []
domain: engine
---

# Task 002i1 — Lookup Snapshot Collection Bug Fix

## Context

`_select_lookup_snapshot_version()` (service.py:426-449) iterates through all lookup names from a mapping snapshot but returns on the first successful snapshot lookup. This means when a feed uses multiple lookup tables (e.g., `claim_status` and `insurance_plan`), only the first one gets included in the codegen prompt, and the AI never generates DDL/seed for the rest.

This bug affects every feed that uses more than one lookup table. It is independent of the multi-table codegen loop — it affects single-table feeds with multiple lookups as well.

## Domain Updates Required

- `docs/domain/source-model.md` — Update the "Code generation artifact" section to note that `lookup_snapshot_version` is now a list (no longer a single string)

## Current State

- `_select_lookup_snapshot_version()` at `engine/src/migrations_engine/codegen/service.py:426-449` returns on first match (line 448: `return snapshot.lookup_snapshot_version` inside a for-loop)
- Return type is `str | None`
- `_build_user_prompt()` passes a single `lookup_snapshot_version` string to the Jinja2 template
- The user prompt template iterates over a single string value (shows only one lookup name)

## Objective

1. Change `_select_lookup_snapshot_version()` to collect ALL matching lookup snapshots into a list
2. Return `list[dict[str, str]]` with entries `{"lookup_name": ..., "snapshot_version": ...}`
3. Update `_build_user_prompt()` to pass `lookup_snapshots` list to the Jinja2 template
4. Update `user_prompt.txt.j2` to iterate over the list instead of displaying a single value

## Files Changed

| File | Change |
|------|--------|
| `engine/src/migrations_engine/codegen/service.py` | Modify `_select_lookup_snapshot_version()` to collect all snapshots |
| `engine/src/migrations_engine/codegen/service.py` | Update `_build_user_prompt()` call to pass `lookup_snapshots` list |
| `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2` | Iterate over `lookup_snapshots` list |

## Tests

- Add unit test: mock a mapping snapshot with 3 lookup fields, verify `_select_lookup_snapshot_version()` returns 3 entries
- Add integration-style test: seed a feed with 2 approved lookups, trigger codegen, verify both lookup names appear in the user prompt
- No existing tests should break — this is a pure bug fix with no behavioral change for single-lookup feeds

## Verification

1. Run `cd engine && .venv/bin/python -m pytest -xvs` — zero new failures
2. No TypeScript errors in frontend (`cd web && npx tsc --noEmit`)
3. `grep -n "lookup_snapshot_version" engine/src/migrations_engine/codegen/service.py` — verify return type and usage are consistent

## Pitfalls

- The return type change from `str | None` to `list[dict[str, str]]` affects the Jinja2 template — must update `user_prompt.txt.j2`
- The `_build_user_prompt()` function receives `lookup_snapshot_version: str | None` as a parameter — this signature must change to `lookup_snapshots: list[dict[str, str]]`
- Be careful not to break feeds with zero lookups (empty list is valid)

## Commit

"fix(codegen): collect all lookup snapshots instead of returning first match"
