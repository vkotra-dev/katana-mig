# Task 001bn — Fix Mapping Snapshot Uniqueness (Per-Feed)

**Plan:** `plans/2026-07-05-001bn-fix-mapping-snapshot-uniqueness.md`

## Context

With 4 feeds in the same project, only Feed 1 can get a mapping proposal. The `mapping_snapshots` unique index is scoped to `(project_id, destination_object_name, version)` — `source_definition_id` is excluded. The `propose_mapping` guard also queries snapshots project-wide, so once any feed has snapshots for all DDL tables, every other feed is rejected with a 409.

## Scope

- New Alembic migration `0024_fix_mapping_snapshot_uniqueness.py`: drop the old project-scoped index, create a new feed-scoped index `(project_id, source_definition_id, destination_object_name, mapping_snapshot_version)`
- `review.py`: add `source_definition_id` filter to `already_mapped_tables` guard query; remove workaround comment
- `snapshots.py`: add `source_definition_id` to `create_approved_mapping_snapshot` pre-flight conflict check

## Out of Scope

- Mapping review/approval flow
- Frontend changes
- Backfilling existing snapshot rows

## Acceptance Criteria

- `alembic upgrade head` runs cleanly
- Each feed in a project can independently propose its own mapping snapshot for `policy_master` and `policy_claims`
- No `mapping_already_proposed` 409 errors when analyzing Feeds 2–4 after Feed 1

## Pitfalls

- `_next_snapshot_version` already queries by `source_definition_id` — no change needed there
- MySQL allows multiple NULLs in a unique index, so nullable `source_definition_id` rows from the legacy `create_approved_mapping_snapshot` path are safe

## Commit

- `feat(001bn): fix mapping snapshot uniqueness to be per-feed not per-project`
