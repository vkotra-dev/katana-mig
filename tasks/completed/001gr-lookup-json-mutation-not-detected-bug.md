---
id: 001gr
title: Fix Silent No-Op on Existing-Group Mutations in Lookup PATCH Actions (SQLAlchemy JSON Mutation-Detection Bug)
status: active
created: 2026-07-25
priority: critical
domain: backend / lookup-mapping / sqlalchemy
depends-on: [001gq]
---

# Task 001gr — Fix Silent No-Op on Existing-Group Mutations in Lookup PATCH Actions

## Context

[[001gq]] fixed a camelCase/snake_case key mismatch that made `add_source_value`/`remove_source_value`/`move_source_value` no-op at the HTTP-body level. This task fixes a **second, independent, more severe** bug in the same handlers that survives that fix: a classic SQLAlchemy JSON-column mutation-detection pitfall. It was found by directly answering the question "are we sure we're actually stacking source values under one destination?" with a real test against the real endpoint, rather than trusting a read of the code.

### Root cause

`LookupValueMap.destination_mappings` (`engine/src/migrations_engine/db/models.py:415`) is a plain SQLAlchemy `JSON` column — not wrapped in `sqlalchemy.ext.mutable.MutableList`/`MutableDict`. All three PATCH action handlers in `engine/src/migrations_engine/management/lookup_mapping.py` follow this pattern:

```python
mappings = list(lookup_map.destination_mappings or [])   # shallow copy: inner dicts are the SAME objects
for group in mappings:
    if group["dest_id"] == dest_id:
        group["source_values"].append(src_val)             # mutates the ORM-tracked dict IN PLACE
        break
lookup_map.destination_mappings = mappings                 # reassignment — but too late
```

`list(...)` only copies the *outer* list; the `group` dicts inside are the exact same objects SQLAlchemy is already tracking as the column's current value. Mutating `group["source_values"]` in place, *before* the reassignment, corrupts SQLAlchemy's before/after comparison — by the time `lookup_map.destination_mappings = mappings` runs, the "old" and "new" values are structurally identical (they share the same mutated sub-objects), so SQLAlchemy's flush-time change detection concludes nothing changed and **never emits an `UPDATE` for that column**. The request still returns `200 OK`; the DB write is silently dropped.

This was confirmed with a minimal, app-independent SQLAlchemy repro (10 lines, plain `JSON` column, sqlite in-memory) — in-place mutation of a shared dict + reassignment does not persist; the same operation using `copy.deepcopy` first, or calling `sqlalchemy.orm.attributes.flag_modified(obj, "column")` after, does persist correctly. Both are valid fixes; `flag_modified` is the recommended one here since it's a one-line addition per call site and avoids deep-copying `destination_table`/`dest_row` blobs unnecessarily.

### Scope — which branches are actually broken

| Handler | Branch | Mechanism | Persists today? |
|---|---|---|---|
| `add_source_value` (line ~102-128) | `dest_id` not yet in `destination_mappings` | `mappings.append({...new dict...})` — brand new dict, never shared with the tracked value | ✅ yes |
| `add_source_value` | `dest_id` already has a group (**the actual "stacking" case**) | `group["source_values"].append(src_val)` on a shared dict | ❌ **no — silently dropped** |
| `remove_source_value` (line ~131-156) | group exists (the only real case) | `group["source_values"] = [...]` — key-reassignment on a shared dict, same pitfall | ❌ **no — silently dropped** |
| `move_source_value` (line ~177-225) | remove from old group | same shared-dict key-reassignment | ❌ **no — silently dropped** |
| `move_source_value` | add to new group, when new group already exists | same shared-dict `.append()` | ❌ **no — silently dropped** |
| `move_source_value` | add to new group, when new group doesn't exist yet | new dict appended | ✅ yes |
| full `destination_mappings` overwrite (line ~158-169, `body.destination_mappings is not None`) | always | builds an entirely new list of new dicts from `body.destination_mappings` (Pydantic models), never touches the old tracked objects | ✅ yes (verified safe, not in scope to change, but see Requirement 4 for optional defensive hardening) |

**Net effect**: the one UI action users actually exercise most — adding a *second* value to a destination that already has one, or removing *any* value from a group — silently fails today, even after [[001gq]]'s fix. The API returns success; nothing changes in the DB; the value reverts on next reload.

### Scope check: is anywhere else affected?

`engine/src/migrations_engine/management/fibers.py` (~lines 375-403) is the only other place in the codebase that assigns `LookupValueMap.destination_mappings`. It was checked and ruled out: it builds the value entirely from a fresh local dict (`dest_mappings_by_id`, populated from scratch, never reading `val_map.destination_mappings`) before assigning — the safe pattern, no shared-object mutation. No changes needed there.

### Existing test evidence (already committed, currently RED)

Three tests were added directly against the real API (not mocks) in `engine/tests/test_lookup_mapping_api.py` and confirmed failing before this task starts:

- `test_patch_add_source_value_stacks_into_existing_group`
- `test_patch_add_source_value_stacks_when_destination_mappings_preseeded`
- `test_patch_remove_source_value_from_preseeded_group`

Run `.venv/bin/python -m pytest engine/tests/test_lookup_mapping_api.py -k "stacks_into_existing or stacks_when_destination or preseeded_group" -v` to see them fail against current `HEAD`.

## Requirements

1. Import `flag_modified` from `sqlalchemy.orm.attributes` in `engine/src/migrations_engine/management/lookup_mapping.py`.
2. Call `flag_modified(lookup_map, "destination_mappings")` immediately after each `lookup_map.destination_mappings = mappings` assignment in the `add_source_value` block (~line 124).
3. Same for the `remove_source_value` block (~line 152).
4. Same for the `move_source_value` block (~line 220). Optionally (defensive, not required to pass tests): add the same call in the full-overwrite block (~line 169) too, so this whole function no longer relies on "the new list happens to contain fresh dict objects" as an implicit invariant — a future refactor could silently reintroduce this bug otherwise.
5. Add one new regression test for `move_source_value` mirroring the add/remove tests already in place: pre-seed `destination_mappings` with a group that already has a source value, move a *different* source value from one existing populated group to another existing populated group, and assert both groups end up with the correct, disjoint `source_values` lists after a real PATCH round-trip.
6. Do not touch `web/` — this is backend-only; the [[001gq]] frontend fix already produces the correct snake_case wire format that these handlers receive.

## Files to Change

1. `engine/src/migrations_engine/management/lookup_mapping.py` — add `flag_modified` import and calls at the 3 (or 4, see Requirement 4) mutation sites.
2. `engine/tests/test_lookup_mapping_api.py` — add the `move_source_value` regression test (Requirement 5). The three add/remove regression tests already exist and are currently red.

## Environment

This repo needs a local `.venv` (repo root `pyproject.toml` declares the `katana-engine` package with `engine/src` as its root). `.venv/` is gitignored, so a fresh checkout won't have one yet — see the plan's Step 0 for exact setup commands. **Never use a bare `python`/`pytest`** on the machine this was authored on: the global Python environment has an unrelated editable install of a different, similarly-named package (`migrations-engine`, from a sibling repo) shadowing the real one, which fails with `ModuleNotFoundError: No module named 'migrations_engine.db'`. Always use `.venv/bin/python` explicitly.

## Verification

```bash
.venv/bin/python -m pytest engine/tests/test_lookup_mapping_api.py -v
.venv/bin/python -m pytest engine/tests -q
```

All of the following must go green (currently red, except the new move test which doesn't exist yet):
- `test_patch_add_source_value_stacks_into_existing_group`
- `test_patch_add_source_value_stacks_when_destination_mappings_preseeded`
- `test_patch_remove_source_value_from_preseeded_group`
- the new move-value regression test from Requirement 5

Exact expected count: `.venv/bin/python -m pytest engine/tests -q` currently prints `3 failed, 387 passed` (the 3 regression tests above are already committed and red). After this task's fix plus the new move test, it must print `391 passed` with zero failures.

No frontend changes are needed to verify this — the bug is entirely below the API boundary. A browser-level manual check (add two values to one destination, reload, confirm both are present) remains valuable as final confirmation but is not required to prove this specific fix, since the new pytest tests hit the real DB through the real ORM layer (sqlite via `sqlite_test_support`), which is exactly where this bug lives.
