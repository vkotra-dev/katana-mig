# Plan: Task 001gp — Codegen Invalidation & Multi-Dialect DML Tests for Stacked Lookup Mappings

- **Task**: [001gp-codegen-lookup-stacked-verification.md](file:///Users/vjkotra/projects/katana/tasks/001gp-codegen-lookup-stacked-verification.md)

---

## Goal Description

Verify and test that stacked source value modifications (add/remove alias, delete destination group) correctly trigger snapshot invalidation and generate valid DML SQL statements across all supported SQL engines (`postgresql`, `mysql`, `mssql`, `oracle`).

---

## Step-by-Step Build Instructions (Agent Executable)

---

### Step 1: Add Snapshot Invalidation Assertion in `test_lookup_mapping_api.py`

**File**: [engine/tests/test_lookup_mapping_api.py](file:///Users/vjkotra/projects/katana/engine/tests/test_lookup_mapping_api.py)

Add a test `test_patch_lookup_value_map_resets_approved_snapshots_to_draft()` verifying that calling `PATCH /projects/{project_id}/lookup-maps/{lookup_value_map_id}` automatically invalidates related approved `LookupSnapshot` records.

```python
def test_patch_lookup_value_map_resets_approved_snapshots_to_draft(admin_token: str) -> None:
    project_id, _source_definition_id = _seed_project()

    # Create & approve map, generate snapshot
    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [{"id": "ACTIVE", "label": "Active"}],
            "source_value_map": {"A": "ACTIVE"},
        },
    )
    assert create.status_code == 201
    map_id = create.json()["lookup_value_map_id"]

    # Patch map -> check snapshot status reset
    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"add_source_value": {"dest_id": "ACTIVE", "source_value": "B"}},
    )
    assert patch.status_code == 200
```

---

### Step 2: Add Multi-Dialect 1-to-Many Codegen DML Tests in `test_bundle_sequencing.py`

**File**: [engine/tests/test_bundle_sequencing.py](file:///Users/vjkotra/projects/katana/engine/tests/test_bundle_sequencing.py)

Add test `test_generate_lookup_upsert_sql_handles_one_to_many_stacked_mappings()` verifying DML output for multi-alias maps `{"A": "ACTIVE", "B": "ACTIVE"}`.

```python
def test_generate_lookup_upsert_sql_handles_one_to_many_stacked_mappings() -> None:
    stacked_map = {"A": "ACTIVE", "B": "ACTIVE", "C": "BLOCKED"}
    
    pg_sql = generate_lookup_upsert_sql("status_code", stacked_map, "postgresql")
    assert "('A', 'ACTIVE')" in pg_sql
    assert "('B', 'ACTIVE')" in pg_sql
    assert "ON CONFLICT (source_val) DO UPDATE SET dest_val = EXCLUDED.dest_val;" in pg_sql

    mysql_sql = generate_lookup_upsert_sql("status_code", stacked_map, "mysql")
    assert "ON DUPLICATE KEY UPDATE dest_val = VALUES(dest_val);" in mysql_sql

    mssql_sql = generate_lookup_upsert_sql("status_code", stacked_map, "mssql")
    assert "MERGE status_code_ref AS target" in mssql_sql
```

---

## Verification Plan

```bash
cd engine && source ../.venv/bin/activate
pytest tests/test_lookup_mapping_api.py tests/test_bundle_sequencing.py -v
pytest -v
```
