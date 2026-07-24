---
id: 001gs
title: Reconcile destination_mappings from source_value_map When Empty (add_source_value / remove_source_value)
status: active
created: 2026-07-25
priority: critical
domain: backend / lookup-mapping
depends-on: [001gr]
---

# Task 001gs — Reconcile `destination_mappings` from `source_value_map` When Empty

## Context

[[001gr]] fixed a SQLAlchemy JSON-column mutation-detection bug (`flag_modified`) that made edits to an *already-populated* `destination_mappings` group silently fail to persist. While verifying that fix, a **second, independent, still-unfixed bug** was found and confirmed with throwaway tests against `HEAD` (after [[001gr]]'s fix was applied and committed) — not guessed at.

### Root cause

`create_lookup_value_map` (`engine/src/migrations_engine/management/lookup_mapping.py:30-77`) only populates the `destination_mappings` column if the caller explicitly passes a `destination_mappings` array in the request body:

```python
destination_mappings = []
if body.destination_mappings:
    destination_mappings = [...]
```

If a lookup map is created with only `source_value_map` (no explicit `destination_mappings` — the common case: this is exactly what happens when a map is seeded from the AI/fiber-approval flow via `source_value_map` alone, or any caller that only sends the flat map), `destination_mappings` starts as `[]` even though `source_value_map` already has real entries.

`add_source_value` and `remove_source_value` (`lookup_mapping.py:103-159`) both start by shallow-copying the *stored* `destination_mappings`:

```python
mappings = list(lookup_map.destination_mappings or [])   # [] if never explicitly seeded
```

When `mappings` starts empty, neither handler ever consults `source_value_map` to recover the groups that should already exist. The result:

- **`add_source_value`**: hits the "not found" branch and creates a *brand-new* group containing *only* the newly added value — every other source value already mapped to that `dest_id` via the flat `source_value_map` is silently dropped from `destination_mappings` (though it remains, now orphaned/inconsistent, in the flat map).
- **`remove_source_value`**: same "not found" branch, but for removal it's worse — it creates a new group with `source_values: []`, silently discarding *every* sibling value that should have stayed, not just failing to add one.

**`move_source_value` (`lookup_mapping.py:186-196`) already has the correct fix for this**, and it is the reference pattern for this task:

```python
mappings = list(lookup_map.destination_mappings or [])
# Build destination_mappings from source_value_map if empty
if not mappings and lookup_map.source_value_map:
    dest_groups: dict[str, dict[str, Any]] = {}
    for src_v, dest_v in lookup_map.source_value_map.items():
        did = str(dest_v)
        if did not in dest_groups:
            label, dest_row_data = _lookup_dest_label(lookup_map, did)
            dest_groups[did] = {"dest_id": did, "dest_label": label, "dest_row": dest_row_data, "source_values": [], "status": "draft"}
        dest_groups[did]["source_values"].append(src_v)
    mappings = list(dest_groups.values())
```

This task extracts that logic into a shared helper and uses it in all three handlers, fixing `add_source_value`/`remove_source_value` and removing the duplication in `move_source_value`.

### Confirmed with throwaway tests against current HEAD (not committed — run these yourself to reproduce before starting)

**`add_source_value`, no pre-seeded `destination_mappings`**: create with `source_value_map: {"A": "ACTIVE"}` only, then `add_source_value(dest_id="ACTIVE", source_value="B")` → response's `ACTIVE` group has `source_values == ["B"]`, **"A" is missing**.

**`remove_source_value`, no pre-seeded `destination_mappings`**: create with `source_value_map: {"A": "ACTIVE", "B": "ACTIVE"}` only, then `remove_source_value(dest_id="ACTIVE", source_value="B")` → response's `ACTIVE` group has `source_values == []`, **"A" is missing** (it should still be there — only "B" was supposed to be removed).

**`move_source_value`, no pre-seeded `destination_mappings` (control — already correct, do not break this)**: create with `source_value_map: {"A": "ACTIVE", "C": "ACTIVE"}` only, then `move_source_value(source_value="C", old_dest_id="ACTIVE", new_dest_id="BLOCKED")` → response's `ACTIVE` group correctly has `source_values == ["A"]`. This already works today because of the reconciliation block quoted above.

## Requirements

1. Add a new module-level helper function in `engine/src/migrations_engine/management/lookup_mapping.py`, e.g. `_reconcile_destination_mappings(lookup_map: LookupValueMap) -> list[dict[str, Any]]`, containing exactly the logic currently inlined in `move_source_value` (quoted above under Root Cause): shallow-copy `lookup_map.destination_mappings`, and if that's empty but `lookup_map.source_value_map` has entries, rebuild groups from the flat map. Place it near `_lookup_dest_label` (`lookup_mapping.py:573-579`), which it depends on.
2. In `add_source_value`, replace `mappings = list(lookup_map.destination_mappings or [])` (currently line 107) with `mappings = _reconcile_destination_mappings(lookup_map)`.
3. In `remove_source_value`, replace `mappings = list(lookup_map.destination_mappings or [])` (currently line 137) with `mappings = _reconcile_destination_mappings(lookup_map)`.
4. In `move_source_value`, replace the entire inline reconciliation block (currently lines 186-196) with `mappings = _reconcile_destination_mappings(lookup_map)`. This is a pure refactor for this handler — its behavior must not change; the new committed test in Requirement 5 (third bullet) exists specifically to pin that down through the refactor.
5. Add three new regression tests to `engine/tests/test_lookup_mapping_api.py`, based on the throwaway tests already confirmed above:
   - `add_source_value` reconciles from `source_value_map` when `destination_mappings` was never seeded (currently fails — must pass after the fix).
   - `remove_source_value` reconciles from `source_value_map` when `destination_mappings` was never seeded (currently fails — must pass after the fix).
   - `move_source_value` still reconciles correctly after the refactor (already passes today — this test guards against a regression during Requirement 4's refactor).
6. Do not touch `web/` — backend-only, no wire-format changes.
7. Keep the [[001gr]] `flag_modified` calls exactly as they are — they remain necessary for the case where `destination_mappings` is already non-empty (populated by a prior successful action) and a group within it gets mutated. This task's fix and [[001gr]]'s fix are complementary, not overlapping: this task ensures `mappings` starts correct; [[001gr]] ensures the eventual write is actually detected and persisted.

## Files to Change

1. `engine/src/migrations_engine/management/lookup_mapping.py` — add the `_reconcile_destination_mappings` helper; use it in all three action handlers (`add_source_value`, `remove_source_value`, `move_source_value`).
2. `engine/tests/test_lookup_mapping_api.py` — add the three regression tests from Requirement 5.

## Environment

Same as [[001gr]]: use `.venv/bin/python` for everything, never a bare `python`/`pytest` (see [[001gr]]'s task file for why — stale global editable install of an unrelated sibling package).

## Verification

```bash
.venv/bin/python -m pytest engine/tests/test_lookup_mapping_api.py -v
.venv/bin/python -m pytest engine/tests -q
```

Baseline before this task's changes (with the 3 new tests already added and red, 2 of them): `.venv/bin/python -m pytest engine/tests -q` should show `391 passed` for existing tests, then adding the 3 new tests should show `2 failed, 392 passed` (the move-control test passes immediately since it needs no code change; the add/remove tests are red until the fix lands). After the fix: `394 passed`, zero failures.

If you get a different count at any checkpoint, do not assume it's fine — stop and figure out why before proceeding.
