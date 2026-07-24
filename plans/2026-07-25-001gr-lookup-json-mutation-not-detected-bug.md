# Plan: Task 001gr — Fix Silent No-Op on Existing-Group Mutations in Lookup PATCH Actions

- **Task**: [001gr-lookup-json-mutation-not-detected-bug.md](file:///Users/vjkotra/projects/katana/tasks/001gr-lookup-json-mutation-not-detected-bug.md)

---

## Goal Description

`LookupValueMap.destination_mappings` is a plain (unwrapped) SQLAlchemy `JSON` column. All three PATCH action handlers build their new value by shallow-copying the existing list (`list(lookup_map.destination_mappings or [])`) and then mutating an *existing, shared* group dict in place (`group["source_values"].append(...)` or `group["source_values"] = [...]`) before reassigning the column. Because the shared dict was mutated before the reassignment, SQLAlchemy's change tracking sees no difference between old and new values at flush time and silently skips the `UPDATE` for that column. The HTTP response still looks correct (it reflects the in-memory, not-yet-persisted mutation) but the database is never actually updated.

Three tests already exist in `engine/tests/test_lookup_mapping_api.py` proving this against the real API and are currently failing. This plan fixes the three broken call sites with `sqlalchemy.orm.attributes.flag_modified`, the minimal, standard fix for this exact SQLAlchemy pitfall, and adds one more regression test for `move_source_value` (the third handler, not yet covered by an existing-group test).

**Scope check already done — do not re-investigate this**: `engine/src/migrations_engine/management/fibers.py` (lines ~375-403) is the only other place in the codebase that assigns `LookupValueMap.destination_mappings`. It builds the entire value from a fresh local dict (`dest_mappings_by_id`, populated from scratch in a loop, never read from the existing `val_map.destination_mappings`) before assigning it — this is the safe pattern (brand-new objects, not shared with anything SQLAlchemy is tracking) and needs no change. The bug is confirmed scoped entirely to the three action handlers in `lookup_mapping.py`.

---

## Step 0: Environment setup (do this first — do not skip)

This repo's `pyproject.toml` (at repo root, not inside `engine/`) declares the installable package `katana-engine`, with `engine/src` as the package root. **`.venv/` is gitignored** — in a fresh checkout it will not exist yet, and running the test suite without it will fail.

Check whether a working venv already exists at the repo root:

```bash
.venv/bin/python -c "import migrations_engine; print(migrations_engine.__file__)"
```

- If this prints a path under **this repo** (`.../katana/engine/src/migrations_engine/__init__.py`), the venv is already correctly set up — skip to Step 1.
- If the command fails (`.venv` doesn't exist), create it:
  ```bash
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -e ".[dev]"
  ```
- **Do not use a bare `python`/`pytest` on this machine without `.venv/`.** The global Python environment here has an unrelated editable install of a *different, similarly-named* package (`migrations-engine`, from a sibling repo at `/Users/vjkotra/projects/migrations/engine`) already on `sys.path` ahead of anything else. Using bare `python -m pytest` will fail with `ModuleNotFoundError: No module named 'migrations_engine.db'` because it silently imports the wrong package. Always invoke `.venv/bin/python` / `.venv/bin/pytest` explicitly, never a bare `python`/`pytest`, for every command in this plan.

---

## Step-by-Step Build Instructions (Agent Executable)

### Step 1: Confirm the starting (red) state

```bash
.venv/bin/python -m pytest engine/tests/test_lookup_mapping_api.py -k "stacks_into_existing or stacks_when_destination or preseeded_group" -v
```

Expect **3 failures**. If any of these three already pass, stop and re-investigate before proceeding — the premise of this plan would be wrong.

---

### Step 2: Add the `flag_modified` import

**File**: [engine/src/migrations_engine/management/lookup_mapping.py](file:///Users/vjkotra/projects/katana/engine/src/migrations_engine/management/lookup_mapping.py)

```diff
 from sqlalchemy import select
 from sqlalchemy.orm import Session
+from sqlalchemy.orm.attributes import flag_modified
```

---

### Step 3: Fix `add_source_value` (currently lines 102-128)

```diff
             if not found:
                 label, dest_row_data = _lookup_dest_label(lookup_map, dest_id)
                 mappings.append({
                     "dest_id": dest_id,
                     "dest_label": label,
                     "dest_row": dest_row_data,
                     "source_values": [src_val],
                     "status": "draft",
                 })
             lookup_map.destination_mappings = mappings
+            flag_modified(lookup_map, "destination_mappings")
             # Sync flat source_value_map for backward compat
             svm = dict(lookup_map.source_value_map or {})
             svm[src_val] = dest_id
             lookup_map.source_value_map = svm
```

---

### Step 4: Fix `remove_source_value` (currently lines 131-156)

```diff
             if not found:
                 # Group may not exist yet (e.g. legacy maps without destination_mappings)
                 label, dest_row_data = _lookup_dest_label(lookup_map, dest_id)
                 mappings.append({
                     "dest_id": dest_id,
                     "dest_label": label,
                     "dest_row": dest_row_data,
                     "source_values": [],
                     "status": "draft",
                 })
             lookup_map.destination_mappings = mappings
+            flag_modified(lookup_map, "destination_mappings")
             # Also remove from flat source_value_map
             svm = dict(lookup_map.source_value_map or {})
             svm.pop(src_val, None)
             lookup_map.source_value_map = svm
```

---

### Step 5: Fix `move_source_value` (currently lines 177-225)

The unique anchor text `"dest_id": new_dest_id` (the variable name `new_dest_id` only appears in this block, nowhere else in the file) distinguishes this `mappings.append({...})` from the visually similar ones in Steps 3 and 4:

```diff
                     mappings.append({
                         "dest_id": new_dest_id,
                         "dest_label": label,
                         "dest_row": dest_row_data,
                         "source_values": [src_val],
                         "status": "draft",
                     })
             lookup_map.destination_mappings = mappings
+            flag_modified(lookup_map, "destination_mappings")
             # Sync flat source_value_map
             svm = dict(lookup_map.source_value_map or {})
             svm.pop(src_val, None)
             svm[src_val] = new_dest_id
             lookup_map.source_value_map = svm
```

---

### Step 6 (defensive, optional but recommended): full-overwrite block (currently lines 158-169)

This block already builds a fresh list of fresh dicts from `body.destination_mappings` (Pydantic models), so it's verified safe today — it does not need this fix to pass the tests in Step 8. But it shares the same fragile "safe only because the objects happen to be new" invariant as the three broken blocks did. Add the same call for consistency and to guard against future refactors reintroducing this bug:

```diff
     if body.destination_mappings is not None:
         lookup_map.destination_mappings = [
             {
                 "dest_id": str(g.dest_id),
                 "dest_label": str(g.dest_label),
                 "dest_row": g.dest_row if isinstance(g.dest_row, dict) else dict(g.dest_row) if g.dest_row else {},
                 "source_values": list(g.source_values) if g.source_values else [],
                 "status": str(g.status),
             }
             for g in body.destination_mappings
         ]
+        flag_modified(lookup_map, "destination_mappings")
         # Rebuild flat source_value_map from destination_mappings
```

---

### Step 7: Add the missing `move_source_value` regression test

**File**: [engine/tests/test_lookup_mapping_api.py](file:///Users/vjkotra/projects/katana/engine/tests/test_lookup_mapping_api.py)

Add this test function after `test_patch_remove_source_value_from_preseeded_group` (search for that function name to find the insertion point — do not guess a line number, the file has been edited during investigation and line numbers have shifted):

```python
def test_patch_move_source_value_between_preseeded_groups(admin_token: str) -> None:
    """Moving a source value between two destinations that already each have
    a value must persist on both ends — not silently no-op on the shared-dict
    mutation, matching the add/remove regression tests above."""
    project_id, _source_definition_id = _seed_project()

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [
                {"id": "ACTIVE", "label": "Active"},
                {"id": "BLOCKED", "label": "Blocked"},
            ],
            "source_value_map": {"A": "ACTIVE", "B": "ACTIVE", "C": "BLOCKED"},
            "destination_mappings": [
                {"dest_id": "ACTIVE", "dest_label": "Active", "dest_row": {}, "source_values": ["A", "B"], "status": "draft"},
                {"dest_id": "BLOCKED", "dest_label": "Blocked", "dest_row": {}, "source_values": ["C"], "status": "draft"},
            ],
        },
    )
    assert create.status_code == 201, create.text
    lookup_map_id = create.json()["lookup_value_map_id"]

    # Move "B" from ACTIVE (which already has A and B) to BLOCKED (which already has C)
    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"move_source_value": {"source_value": "B", "old_dest_id": "ACTIVE", "new_dest_id": "BLOCKED"}},
    )
    assert patch.status_code == 200, patch.text
    data = patch.json()

    groups_by_dest = {g["dest_id"]: g for g in data["destination_mappings"]}
    assert groups_by_dest["ACTIVE"]["source_values"] == ["A"], groups_by_dest["ACTIVE"]["source_values"]
    assert set(groups_by_dest["BLOCKED"]["source_values"]) == {"C", "B"}
    assert data["source_value_map"]["B"] == "BLOCKED"
```

Indent it at module level (no leading whitespace on `def`), with one blank line before and after, matching the style of the surrounding test functions.

---

### Step 8: Verify

```bash
.venv/bin/python -m pytest engine/tests/test_lookup_mapping_api.py -v
.venv/bin/python -m pytest engine/tests -q
```

**Exact expected counts** (measured against `HEAD` before this task's changes, so you can confirm your starting point matches): running `.venv/bin/python -m pytest engine/tests -q` before any code changes in this plan (but with the 3 existing regression tests from Step 1 already present in the file, which they are) gives:

```
3 failed, 387 passed
```

After Steps 2-7 of this plan are complete, running the same command must give:

```
391 passed
```

(387 previously-passing + 3 previously-red regression tests now passing + 1 new `test_patch_move_source_value_between_preseeded_groups` test = 391, zero failures.)

If you get a different total test count, do not assume it's fine — figure out why before declaring success (a different count means either a test was accidentally deleted/duplicated, or the repo has changed since this plan was written and the assumption needs re-checking).

---

## Verification Plan

```bash
.venv/bin/python -m pytest engine/tests -q
```

Must print `391 passed` with zero failures (see exact expected counts in Step 8).

This is a pure backend persistence fix — no frontend changes, no wire-format changes, nothing for `web/` tests to catch or regress; do not run or modify anything under `web/` for this task. The pytest suite exercises the real ORM/DB layer (via `sqlite_test_support`), which is exactly where the original bug lived, so passing tests here are direct proof of the fix (unlike the [[001gq]] key-casing fix, which needed a browser-level check because it lived above a mocked-fetch boundary). A manual browser check remains good practice before closing out the parent user-facing issue, but is not required to validate this specific task.
