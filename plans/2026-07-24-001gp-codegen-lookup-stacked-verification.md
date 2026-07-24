# Plan: Task 001gp — Codegen Invalidation & Multi-Dialect DML Tests for Stacked Lookup Mappings

- **Task**: [001gp-codegen-lookup-stacked-verification.md](file:///Users/vjkotra/projects/katana/tasks/001gp-codegen-lookup-stacked-verification.md)

---

## Goal Description

Verify and test that stacked source value modifications (add/remove alias) correctly trigger snapshot invalidation and generate valid DML SQL statements across all supported SQL engines (`postgresql`, `mysql`, `mssql`, `oracle`). Source values only — no destination-group delete action exists (see [[001gn]] scope note).

---

## Step-by-Step Build Instructions (Agent Executable)

---

### Step 1: Add Snapshot Invalidation Assertion in `test_lookup_mapping_api.py`

**File**: [engine/tests/test_lookup_mapping_api.py](file:///Users/vjkotra/projects/katana/engine/tests/test_lookup_mapping_api.py)

Add a test `test_patch_lookup_value_map_resets_approved_snapshots_to_draft()` verifying that calling `PATCH /projects/{project_id}/lookup-maps/{lookup_value_map_id}` with `add_source_value` or `remove_source_value` automatically invalidates a related **approved** `LookupSnapshot` record back to `draft`. Reuse the generate+approve recipe already used in `test_lookup_routes_enforce_auth_and_contract` (same file, ~line 214) — `_seed_project()` seeds a mapping snapshot for lookup name `"status_code"` that `generate_lookup_snapshot` can find. Requires both `admin_token` and `stakeholder_token` fixtures (approval requires the stakeholder role, same as the existing test).

```python
def test_patch_lookup_value_map_resets_approved_snapshots_to_draft(
    admin_token: str, stakeholder_token: str
) -> None:
    project_id, source_definition_id = _seed_project()

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [{"id": "ACTIVE", "label": "Active"}],
            "source_value_map": {"A": "ACTIVE"},
        },
    )
    assert create.status_code == 201, create.text
    map_id = create.json()["lookup_value_map_id"]

    generate = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/lookup-snapshots",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"lookup_name": "status_code"},
    )
    assert generate.status_code == 201, generate.text
    snapshot_id = generate.json()["lookup_snapshot_id"]

    approve = client.post(
        f"/projects/{project_id}/lookup-snapshots/{snapshot_id}/approve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"

    # add_source_value should reset the approved snapshot to draft
    patch_add = client.patch(
        f"/projects/{project_id}/lookup-maps/{map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"add_source_value": {"dest_id": "ACTIVE", "source_value": "B"}},
    )
    assert patch_add.status_code == 200, patch_add.text

    with SessionLocal() as db:
        snapshot = db.get(LookupSnapshot, snapshot_id)
        assert snapshot.status == "draft"
        assert snapshot.approved_at is None

    # Re-approve, then confirm remove_source_value also resets it
    reapprove = client.post(
        f"/projects/{project_id}/lookup-snapshots/{snapshot_id}/approve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert reapprove.status_code == 200, reapprove.text

    patch_remove = client.patch(
        f"/projects/{project_id}/lookup-maps/{map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"remove_source_value": {"dest_id": "ACTIVE", "source_value": "B"}},
    )
    assert patch_remove.status_code == 200, patch_remove.text

    with SessionLocal() as db:
        snapshot = db.get(LookupSnapshot, snapshot_id)
        assert snapshot.status == "draft"
```

Note: `SessionLocal` is already imported (line 10). `LookupSnapshot` is not — add it to the `from migrations_engine.db.models import (...)` block (lines 14-25), alongside `LookupValueMap`.

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
    assert "('A', 'ACTIVE')" in mysql_sql
    assert "('B', 'ACTIVE')" in mysql_sql
    assert "ON DUPLICATE KEY UPDATE dest_val = VALUES(dest_val);" in mysql_sql

    mssql_sql = generate_lookup_upsert_sql("status_code", stacked_map, "mssql")
    assert "('A', 'ACTIVE')" in mssql_sql
    assert "('B', 'ACTIVE')" in mssql_sql
    assert "MERGE status_code_ref AS target" in mssql_sql

    oracle_sql = generate_lookup_upsert_sql("status_code", stacked_map, "oracle")
    assert "('A', 'ACTIVE')" in oracle_sql
    assert "('B', 'ACTIVE')" in oracle_sql
    assert "MERGE" in oracle_sql
    assert "WHEN MATCHED THEN UPDATE SET" in oracle_sql
```

---

## Verification Plan

```bash
cd engine && source ../.venv/bin/activate
pytest tests/test_lookup_mapping_api.py tests/test_bundle_sequencing.py -v
pytest -v
```
