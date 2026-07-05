# Summary: 001bn — Fix Mapping Snapshot Uniqueness (Per-Feed)

## What Was Done

Fixed a bug where only the first feed in a project could ever get a mapping proposal. Root cause was a project-scoped unique index on `mapping_snapshots` and a project-wide guard query in `propose_mapping`.

### Migration `0024_mapping_per_feed`

- Dropped `ix_mapping_snapshots_project_dest_version` on `(project_id, destination_object_name, version)`
- Created `ix_mapping_snapshots_source_dest_version` on `(project_id, source_definition_id, destination_object_name, version)`
- Create-before-drop ordering used to keep MySQL FK constraints covered during the transition
- Revision ID kept ≤ 32 chars to fit `alembic_version.version_num` column

### `review.py` — propose_mapping guard

Added `source_definition_id` filter to `already_mapped_tables` query. Removed the workaround comment that documented the old project-scoped behavior.

### `snapshots.py` — create_approved_mapping_snapshot pre-flight

Added `source_definition_id` to the conflict-check query to match the new constraint scope.

## Result

Each feed can independently propose its own `policy_master-v1` and `policy_claims-v1` snapshots without conflicting with other feeds in the same project.
