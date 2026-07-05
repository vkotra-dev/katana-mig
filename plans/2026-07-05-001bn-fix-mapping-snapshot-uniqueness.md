# Plan: 001bn — Fix Mapping Snapshot Uniqueness (Per-Feed)

- **Task Link:** [001bn-fix-mapping-snapshot-uniqueness.md](file:///Users/vjkotra/projects/katana/tasks/001bn-fix-mapping-snapshot-uniqueness.md)
- **Domain Link:** [source-model.md](file:///Users/vjkotra/projects/katana/docs/domain/source-model.md)

## Current State

The `mapping_snapshots` table has a unique index `ix_mapping_snapshots_project_dest_version` on `(project_id, destination_object_name, mapping_snapshot_version)`. `source_definition_id` is excluded. This means the combination of destination table name + version is unique per project — not per feed.

The `propose_mapping` guard in `review.py` also queries `already_mapped_tables` project-wide (no `source_definition_id` filter), so any feed that already proposed mappings for all DDL tables blocks every other feed with a 409.

With 4 feeds in the same project, only Feed 1 can ever get a mapping proposal.

## Objective

Allow each feed (`source_definition_id`) to independently hold its own mapping snapshot per destination table. Narrow the unique constraint and the guard to be feed-scoped.

## Out of Scope

- Changing the mapping review or approval flow
- Frontend changes
- Backfilling existing snapshots (existing Feed 1 rows are unaffected)

## Blast Radius

- `engine/migrations/versions/0024_mapping_per_feed.py` (new)
- `engine/src/migrations_engine/mapping/review.py` (guard query only)
- `engine/src/migrations_engine/mapping/snapshots.py` (pre-flight query only)

## File Changes

### New: `engine/migrations/versions/0024_mapping_per_feed.py`

Drop `ix_mapping_snapshots_project_dest_version`, create `ix_mapping_snapshots_source_dest_version` on `(project_id, source_definition_id, destination_object_name, mapping_snapshot_version)`.

`down_revision = "0023_mapping_snapshot_source_id"` (confirmed from file chain).

```python
def upgrade() -> None:
    op.drop_index("ix_mapping_snapshots_project_dest_version", table_name="mapping_snapshots")
    op.create_index(
        "ix_mapping_snapshots_source_dest_version",
        "mapping_snapshots",
        ["project_id", "source_definition_id", "destination_object_name", "mapping_snapshot_version"],
        unique=True,
    )

def downgrade() -> None:
    op.drop_index("ix_mapping_snapshots_source_dest_version", table_name="mapping_snapshots")
    op.create_index(
        "ix_mapping_snapshots_project_dest_version",
        "mapping_snapshots",
        ["project_id", "destination_object_name", "mapping_snapshot_version"],
        unique=True,
    )
```

MySQL allows multiple NULLs in a unique index column, so nullable `source_definition_id` rows won't collide.

### `engine/src/migrations_engine/mapping/review.py` — guard (lines ~301-310)

Add `MappingSnapshot.source_definition_id == source_definition_id` to `already_mapped_tables` query. Remove the workaround comment. The per-table skip and IntegrityError catch reuse `already_mapped_tables` and inherit the fix automatically.

### `engine/src/migrations_engine/mapping/snapshots.py` — pre-flight (~lines 32-43)

Add `MappingSnapshot.source_definition_id == source_definition_id` to the `create_approved_mapping_snapshot` conflict check so it matches the new constraint scope.

## Tests

No existing automated tests cover `propose_mapping` duplicate detection. Manual verification per Verification section.

## Verification

1. `alembic upgrade head` runs cleanly
2. With Feed 1 already having snapshots, click "Analyze with AI" on Feeds 2, 3, 4
3. Each feed independently gets `policy_master-v1` and `policy_claims-v1` with its own `source_definition_id`
4. No `mapping_already_proposed` 409 errors in engine logs
5. Each feed workspace shows both tables in the Field Mappings section

## Pitfalls

- The `_next_snapshot_version` function already queries by `source_definition_id` correctly — no change needed there.
- MySQL NULL behavior: `source_definition_id = NULL` rows from the `create_approved_mapping_snapshot` path are not subject to the new constraint (each NULL is treated as unique), which is the desired behavior.

## Commit

- `feat(001bn): fix mapping snapshot uniqueness to be per-feed not per-project`
