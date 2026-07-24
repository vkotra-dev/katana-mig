# Plan: Task 001fk — Populate dest_label in destination_mappings from backend

- **Task**: [001fk-destination-labels-empty-in-backend.md](../tasks/001fk-destination-labels-empty-in-backend.md)
- **Domain**: [governance.md](../docs/domain/governance.md)
- **Related**: 001fj (frontend destination mappings UI), 001fb (AI prompt contract)

---

## Current State

When the review page displays lookup mappings, each group's destination value column should render `"Label (ID)"` (e.g., `"Bronze Standard (1)"`). The feed page does this correctly because `proposed_mappings` include full `destRow` objects.

The review page receives `destination_mappings` from the backend API. When `destination_mappings` is populated, the `dest_label` field should contain the human-readable label. However, **every code path in the backend that creates or rebuilds `destination_mappings` groups hardcodes `"dest_label": ""`**.

The backend already has `_extract_destination_label(row: dict)` at line 538 of `lookup_mapping.py` — a multi-strategy function that checks `label`, `name`, `description`, `desc`, `val`, `value`, `display`, substring matches, and fallback concatenation. It is **never called** when building `destination_mappings`.

---

## Root Cause

`_extract_destination_label()` exists but is unused in group-building paths. The 5 locations that create new `destination_mappings` groups hardcode `"dest_label": ""`:

| File | Line | Path | Label Source |
|---|---|---|---|
| `fibers.py` | 256 | Auto-creation from `proposed_mappings` | `dest_row_data` available |
| `lookup_mapping.py` | 118 | `add_source_value` fallback | `destination_table` available |
| `lookup_mapping.py` | 145 | `remove_source_value` fallback | `destination_table` available |
| `lookup_mapping.py` | 188 | `move_source_value` fallback | `destination_table` available |
| `lookup_mapping.py` | 211 | `move_source_value` new group | `destination_table` available |

---

## Implementation Plan

### Step 1: `fibers.py` — Auto-creation path

**File**: `engine/src/migrations_engine/management/fibers.py`
**Line**: 254-256

**Change**: Add import and use `_extract_destination_label`.

```python
# Add import at top of file (after existing from ..management imports)
from .lookup_mapping import _extract_destination_label

# Change line 254-256 from:
dest_mappings_by_id[dest_id] = {
    "dest_id": dest_id,
    "dest_label": "",
    "dest_row": dest_row_data or {},
    ...
}

# To:
dest_label = _extract_destination_label(dest_row_data) if dest_row_data else ""
dest_mappings_by_id[dest_id] = {
    "dest_id": dest_id,
    "dest_label": dest_label,
    "dest_row": dest_row_data or {},
    ...
}
```

**Circular import check**: `fibers.py` is in `management/`, `lookup_mapping.py` is in `management/`. `lookup_mapping.py` does not import from `fibers.py`. One-way import `fibers → lookup_mapping` is safe.

### Step 2: `lookup_mapping.py` — add_source_value fallback (line ~116)

**File**: `engine/src/migrations_engine/management/lookup_mapping.py`
**Line**: 116-122

**Context**: When `add_source_value` is called and no existing `destination_mappings` groups exist, a new group is created. `lookup_map.destination_table` is available.

**Change**: Look up the destination row from `destination_table` and extract label.

```python
# Change line 116-122 from:
mappings.append({
    "dest_id": dest_id,
    "dest_label": "",
    "dest_row": {},
    "source_values": [src_val],
    "status": "draft",
})

# To: find the matching row in destination_table
dest_row_data = {}
for row in (lookup_map.destination_table or []):
    row_id = row.get("id") or row.get("destination_id")
    if str(row_id) == str(dest_id):
        dest_row_data = row
        break

label = _extract_destination_label(dest_row_data) if dest_row_data else ""
mappings.append({
    "dest_id": dest_id,
    "dest_label": label,
    "dest_row": dest_row_data,
    "source_values": [src_val],
    "status": "draft",
})
```

### Step 3: `lookup_mapping.py` — remove_source_value fallback (line ~143)

**File**: `engine/src/migrations_engine/management/lookup_mapping.py`
**Line**: 143-149

**Change**: Same pattern — look up from `destination_table`, extract label.

```python
# Change from:
mappings.append({
    "dest_id": dest_id,
    "dest_label": "",
    "dest_row": {},
    "source_values": [],
    "status": "draft",
})

# To:
dest_row_data = {}
for row in (lookup_map.destination_table or []):
    row_id = row.get("id") or row.get("destination_id")
    if str(row_id) == str(dest_id):
        dest_row_data = row
        break
label = _extract_destination_label(dest_row_data) if dest_row_data else ""
mappings.append({
    "dest_id": dest_id,
    "dest_label": label,
    "dest_row": dest_row_data,
    "source_values": [],
    "status": "draft",
})
```

### Step 4: `lookup_mapping.py` — move_source_value fallback + new group (lines 188 & 209)

**File**: `engine/src/migrations_engine/management/lookup_mapping.py`
**Lines**: 188 (build from `source_value_map`), 209 (create new group)

**Line 188 change** — the `source_value_map` rebuild path:

```python
# Change from:
dest_groups[did] = {"dest_id": did, "dest_label": "", "dest_row": {}, "source_values": [], "status": "draft"}

# To:
dest_row_data = {}
for row in (lookup_map.destination_table or []):
    row_id = row.get("id") or row.get("destination_id")
    if str(row_id) == str(did):
        dest_row_data = row
        break
label = _extract_destination_label(dest_row_data) if dest_row_data else ""
dest_groups[did] = {"dest_id": did, "dest_label": label, "dest_row": dest_row_data, "source_values": [], "status": "draft"}
```

**Line 209 change** — the new group append in `move_source_value`:

```python
# Change from:
mappings.append({
    "dest_id": new_dest_id,
    "dest_label": "",
    "dest_row": {},
    "source_values": [src_val],
    "status": "draft",
})

# To:
new_dest_row_data = {}
for row in (lookup_map.destination_table or []):
    row_id = row.get("id") or row.get("destination_id")
    if str(row_id) == str(new_dest_id):
        new_dest_row_data = row
        break
new_label = _extract_destination_label(new_dest_row_data) if new_dest_row_data else ""
mappings.append({
    "dest_id": new_dest_id,
    "dest_label": new_label,
    "dest_row": new_dest_row_data,
    "source_values": [src_val],
    "status": "draft",
})
```

### Step 5: Extract common helper to avoid duplication

Since the label-extraction logic is identical in 4 places inside `lookup_mapping.py`, refactor into a private helper:

```python
def _lookup_dest_label(lookup_map: LookupValueMap, dest_id: str) -> tuple[str, dict]:
    """Find dest_row in destination_table by dest_id and return (label, dest_row)."""
    for row in (lookup_map.destination_table or []):
        row_id = row.get("id") or row.get("destination_id")
        if str(row_id) == str(dest_id):
            return (_extract_destination_label(row), row)
    return ("", {})
```

Then all 4 call sites become:
```python
label, dest_row_data = _lookup_dest_label(lookup_map, dest_id)
mappings.append({... "dest_label": label, "dest_row": dest_row_data, ...})
```

This is cleaner and reduces duplication. The helper lives inside `lookup_mapping.py` so it has access to `_extract_destination_label`.

### Step 6: Update tests

**File**: `engine/tests/test_lookup_mapping_api.py`

**`test_patch_add_source_value`** (line 488):
- Currently verifies `source_value_map["B"] == "BLOCKED"` and that "B" is in the BLOCKED group's `source_values`
- Add assertion: `assert blocked_group["dest_label"] == "Blocked"`

**`test_patch_remove_source_value`** (line 521):
- Verify that the removed source is gone and remaining groups have `dest_label` populated
- `assert active_group["dest_label"] == "Active"`

**`test_patch_move_source_value`** (line 603):
- After the move, both groups should have `dest_label` populated
- `assert active_group["dest_label"] == "Active"`
- `assert blocked_group["dest_label"] == "Blocked"` (or check for the new label)

**New test for auto-creation path** (in `test_fiber_ai_flow.py` or `test_lookup_mapping_api.py`):
- Create a fiber with `proposed_mappings` that include `dest_row` with a `name` field
- Verify that when `lookup_value_map` is auto-created from the fiber, `destination_mappings` has `dest_label` populated

### Step 7: Run full test suite

```bash
cd engine && pytest -x
```

All existing tests must pass. New assertions should verify `dest_label` is populated.

---

## Files Changed

| File | Lines | Change |
|---|---|---|
| `engine/src/migrations_engine/management/lookup_mapping.py` | ~538-562 (existing), ~105-216 (modifications) | Add `_lookup_dest_label()` helper, replace 4 `"dest_label": ""` occurrences |
| `engine/src/migrations_engine/management/fibers.py` | ~254, imports | Import `_extract_destination_label`, populate `dest_label` |
| `engine/tests/test_lookup_mapping_api.py` | ~488, ~521, ~603 | Add `dest_label` assertions |
| `engine/tests/` | new test | Verify auto-creation path populates `dest_label` |

## Verification

After implementing:
1. Backend test suite passes (all existing + new assertions)
2. Review page shows `"Label (ID)"` instead of raw UUIDs for lookup destination columns
3. Feed page continues to work as before (no regression — it already extracts labels correctly)
4. Legacy data (maps created before `destination_mappings` column existed) now gets labels on first user interaction (add/remove/move source value)
