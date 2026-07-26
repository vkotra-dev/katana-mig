---
id: 002b1
title: Sync docs/domain/runs.md against actual codebase
status: completed
created: 2026-07-24
priority: medium
domain: docs
depends-on: []
---

# Sync docs/domain/runs.md

## Objective

Update `docs/domain/runs.md` to accurately reflect the current run execution models. Last updated 2026-07-16.

## Scope

- `docs/domain/runs.md` only

## What to verify

1. **RunRecord fields** — Compare against ORM `RunRecord` class:
   - `run_id`, `project_id`, `destination_object_name`, `source_definition_reference`
   - `source_slice_version`, `mapping_snapshot_version`, `lookup_snapshot_version`
   - `lookup_snapshot_versions` (JSON) — verify this is a JSON map
   - `code_generation_input_snapshot_version`, `codegen_artifact_id`
   - `knowledge_freeze_version`
   - `status`, `current_stage`, `approvals` (JSON)
   - `environment`, `start/pause/resume/completion_metadata` (JSON)
   - Verify `lookup_snapshot_version` (singular) vs `lookup_snapshot_versions` (JSON) — doc only mentions the singular map, may need update

2. **RunCheckpoint** — Compare against ORM `RunCheckpoint` class:
   - `current_stage`, `current_object`, `current_environment`
   - `approved_snapshots` (JSON)
   - `last_completed_checkpoint_boundary`
   - `pause_reason`, `checkpoint_payload` (JSON)
   - Verify field names match

3. **Baton sequence** — Verify baton chain across stages matches actual conductor logic

4. **Execution flow** — Verify outer loop, inner loop, LookupDeltaCR interrupt match actual code

5. **Checkpoint boundary** — Verify "every 500 rows" rule is configurable

6. **ReconciliationReport** — Verify schema matches actual ORM:
   - `report_id`, `run_id`, `checks`, `overall_status`, `row_count_summary`
   - `source_rows`, `destination_rows`, `rejected`, `duplicated`, `partially_mapped`

7. **ReconciliationLineageRow** — Verify schema matches actual ORM

8. **Reconciliation endpoints** — Verify actual reconciliation routes exist

## Out of scope

- Any other domain doc files
- Backend implementation changes

## Acceptance criteria

- [x] RunRecord fields match ORM exactly
- [x] RunCheckpoint fields match ORM exactly
- [x] Baton sequence is accurate
- [x] Execution flow (outer/inner loops) is accurate
- [x] ReconciliationReport schema matches ORM
- [x] ReconciliationLineageRow schema matches ORM
- [x] Changelog updated
- [x] timestamp updated
