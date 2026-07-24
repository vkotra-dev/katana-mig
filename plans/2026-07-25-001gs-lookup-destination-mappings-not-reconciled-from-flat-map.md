# Plan: Task 001gs — Reconcile `destination_mappings` from `source_value_map` When Empty

- **Task**: [001gs-lookup-destination-mappings-not-reconciled-from-flat-map.md](file:///Users/vjkotra/projects/katana/tasks/001gs-lookup-destination-mappings-not-reconciled-from-flat-map.md)

---

## Goal Description

`add_source_value` and `remove_source_value` both start by shallow-copying `lookup_map.destination_mappings`. If a lookup map was created with only `source_value_map` (no explicit `destination_mappings`), that column starts as `[]`, and neither handler falls back to reconstructing groups from `source_value_map` before mutating — so any pre-existing source values for that destination are silently dropped from the response and the DB. `move_source_value` already does this correctly via an inline reconciliation block. This plan extracts that block into a shared helper and uses it in all three handlers, fixing the two broken ones and de-duplicating the correct one.

This is a different, independent bug from [[001gr]] (SQLAlchemy JSON-column mutation detection, fixed via `flag_modified`). Both fixes are required together: this task ensures the *starting* `mappings` list is correct; [[001gr]] ensures a later *mutation* to an already-correct list actually gets persisted. Do not remove or alter the `flag_modified` calls from [[001gr]] while doing this task.

---

## Step 0: Environment setup

Identical to [[001gr]]'s Step 0. Verify or create `.venv` first:

```bash
.venv/bin/python -c "import migrations_engine; print(migrations_engine.__file__)"
```

If that fails or `.venv` doesn't exist:

```bash
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -e ".[dev]"
```

**Always use `.venv/bin/python`/`.venv/bin/pytest` explicitly. Never a bare `python`/`pytest`** — the global environment on this machine has an unrelated editable install of a similarly-named package from a sibling repo that will shadow the real one and produce a confusing `ModuleNotFoundError: No module named 'migrations_engine.db'`.

---

## Step-by-Step Build Instructions (Agent Executable)

### Step 1: Confirm current passing baseline

```bash
.venv/bin/python -m pytest engine/tests -q
```

Expect `391 passed` (this is [[001gr]]'s post-fix baseline). If you get a different number, stop and re-check you're starting from the right commit before proceeding.

---

### Step 2: Add the `_reconcile_destination_mappings` helper

**File**: [engine/src/migrations_engine/management/lookup_mapping.py](file:///Users/vjkotra/projects/katana/engine/src/migrations_engine/management/lookup_mapping.py)

Insert this new function immediately after `_lookup_dest_label` (search for `def _lookup_dest_label` to find the anchor — do not rely on a line number, it may have shifted):

```diff
 def _lookup_dest_label(lookup_map: LookupValueMap, dest_id: str) -> tuple[str, dict[str, Any]]:
     """Find the destination row in destination_table matching dest_id and return (label, dest_row)."""
     for row in (lookup_map.destination_table or []):
         row_id = row.get("id") or row.get("destination_id")
         if str(row_id) == str(dest_id):
             return (_extract_destination_label(row), row)
     return ("", {})
 
 
+def _reconcile_destination_mappings(lookup_map: LookupValueMap) -> list[dict[str, Any]]:
+    """Return the working copy of destination_mappings groups to mutate.
+
+    If destination_mappings was never explicitly seeded (empty) but
+    source_value_map already has entries, rebuild groups from source_value_map
+    first — otherwise those source values would be silently dropped the
+    moment a PATCH action rebuilds destination_mappings from an empty start.
+    """
+    mappings = list(lookup_map.destination_mappings or [])
+    if not mappings and lookup_map.source_value_map:
+        dest_groups: dict[str, dict[str, Any]] = {}
+        for src_v, dest_v in lookup_map.source_value_map.items():
+            did = str(dest_v)
+            if did not in dest_groups:
+                label, dest_row_data = _lookup_dest_label(lookup_map, did)
+                dest_groups[did] = {"dest_id": did, "dest_label": label, "dest_row": dest_row_data, "source_values": [], "status": "draft"}
+            dest_groups[did]["source_values"].append(src_v)
+        mappings = list(dest_groups.values())
+    return mappings
+
+
 def _lookup_value_map_response(row: LookupValueMap, unmapped_row_count: int = 0) -> LookupValueMapResponse:
```

---

### Step 3: Use the helper in `add_source_value`

Find the `# Handle add_source_value action` block. Replace only the first line of the block body:

```diff
     if body.add_source_value:
         dest_id = body.add_source_value.get("dest_id", "")
         src_val = body.add_source_value.get("source_value", "")
         if dest_id and src_val:
-            mappings = list(lookup_map.destination_mappings or [])
+            mappings = _reconcile_destination_mappings(lookup_map)
             found = False
             for group in mappings:
```

---

### Step 4: Use the helper in `remove_source_value`

Find the `# Handle remove_source_value action` block. Replace only the first line of the block body:

```diff
     if body.remove_source_value:
         dest_id = body.remove_source_value.get("dest_id", "")
         src_val = body.remove_source_value.get("source_value", "")
         if dest_id and src_val:
-            mappings = list(lookup_map.destination_mappings or [])
+            mappings = _reconcile_destination_mappings(lookup_map)
             found = False
             for group in mappings:
```

---

### Step 5: Use the helper in `move_source_value` (refactor — replaces the inline block instead of adding a call)

Find the `# Handle move_source_value action` block:

```diff
         if src_val and old_dest_id and new_dest_id:
-            mappings = list(lookup_map.destination_mappings or [])
-            # Build destination_mappings from source_value_map if empty
-            if not mappings and lookup_map.source_value_map:
-                dest_groups: dict[str, dict[str, Any]] = {}
-                for src_v, dest_v in lookup_map.source_value_map.items():
-                    did = str(dest_v)
-                    if did not in dest_groups:
-                        label, dest_row_data = _lookup_dest_label(lookup_map, did)
-                        dest_groups[did] = {"dest_id": did, "dest_label": label, "dest_row": dest_row_data, "source_values": [], "status": "draft"}
-                    dest_groups[did]["source_values"].append(src_v)
-                mappings = list(dest_groups.values())
+            mappings = _reconcile_destination_mappings(lookup_map)
             src_moved = False
             for group in mappings:
```

Double-check after this edit that `move_source_value`'s behavior is unchanged — Step 8's regression test specifically checks this.

---

### Step 6: Add the three regression tests

**File**: [engine/tests/test_lookup_mapping_api.py](file:///Users/vjkotra/projects/katana/engine/tests/test_lookup_mapping_api.py)

Add these three functions after `test_patch_move_source_value_between_existing_groups` (search for that function name — do not guess a line number):

```python
def test_patch_add_source_value_reconciles_from_source_value_map_when_destination_mappings_empty(
    admin_token: str,
) -> None:
    """When destination_mappings was never explicitly seeded (only source_value_map
    was provided at create time), adding a new source value to a dest_id that
    already has one (via source_value_map) must not drop the existing one."""
    project_id, _source_definition_id = _seed_project()

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [{"id": "ACTIVE", "label": "Active"}],
            "source_value_map": {"A": "ACTIVE"},
            # NOTE: no destination_mappings provided — this is the whole point of this test.
        },
    )
    assert create.status_code == 201, create.text
    lookup_map_id = create.json()["lookup_value_map_id"]

    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"add_source_value": {"dest_id": "ACTIVE", "source_value": "B"}},
    )
    assert patch.status_code == 200, patch.text
    data = patch.json()

    active_groups = [g for g in data["destination_mappings"] if g["dest_id"] == "ACTIVE"]
    assert len(active_groups) == 1, active_groups
    assert set(active_groups[0]["source_values"]) == {"A", "B"}, active_groups[0]["source_values"]


def test_patch_remove_source_value_reconciles_from_source_value_map_when_destination_mappings_empty(
    admin_token: str,
) -> None:
    """When destination_mappings was never explicitly seeded, removing one source
    value must not drop its siblings that were only known via source_value_map."""
    project_id, _source_definition_id = _seed_project()

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [{"id": "ACTIVE", "label": "Active"}],
            "source_value_map": {"A": "ACTIVE", "B": "ACTIVE"},
        },
    )
    assert create.status_code == 201, create.text
    lookup_map_id = create.json()["lookup_value_map_id"]

    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"remove_source_value": {"dest_id": "ACTIVE", "source_value": "B"}},
    )
    assert patch.status_code == 200, patch.text
    data = patch.json()

    active_groups = [g for g in data["destination_mappings"] if g["dest_id"] == "ACTIVE"]
    assert len(active_groups) == 1, active_groups
    assert active_groups[0]["source_values"] == ["A"], active_groups[0]["source_values"]


def test_patch_move_source_value_reconciles_from_source_value_map_when_destination_mappings_empty(
    admin_token: str,
) -> None:
    """Regression guard for the _reconcile_destination_mappings refactor: this
    already passed before the refactor (move_source_value had its own inline
    version of this logic) and must keep passing after."""
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
            "source_value_map": {"A": "ACTIVE", "C": "ACTIVE"},
        },
    )
    assert create.status_code == 201, create.text
    lookup_map_id = create.json()["lookup_value_map_id"]

    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"move_source_value": {"source_value": "C", "old_dest_id": "ACTIVE", "new_dest_id": "BLOCKED"}},
    )
    assert patch.status_code == 200, patch.text
    data = patch.json()

    active_group = next(g for g in data["destination_mappings"] if g["dest_id"] == "ACTIVE")
    assert active_group["source_values"] == ["A"], active_group["source_values"]
```

---

### Step 7: Verify

```bash
.venv/bin/python -m pytest engine/tests/test_lookup_mapping_api.py -v
.venv/bin/python -m pytest engine/tests -q
```

**Exact expected count**: `394 passed`, zero failures (391 from the [[001gr]] baseline + 3 new tests in this task, all passing — including the move-reconciliation test, which passes both before and after Step 5's refactor since it's a behavior-preservation guard, not a bug-catching test).

If the count differs, do not assume it's fine — figure out why before declaring success.

---

## Verification Plan

```bash
.venv/bin/python -m pytest engine/tests -q
```

Must print `394 passed` with zero failures. Backend-only change — do not run or modify anything under `web/`. As with [[001gr]], the pytest suite exercises the real ORM/DB layer directly, which is exactly where this bug lives, so a green suite here is direct proof of the fix without needing a browser-level check.
