---
id: 002b2
title: Sync docs/domain/source-model.md against actual codebase
status: pending
created: 2026-07-24
priority: high
domain: docs
depends-on: []
---

# Sync docs/domain/source-model.md

## Objective

Update `docs/domain/source-model.md` to accurately reflect all current source-related models. Last updated 2026-07-25. This is the most critical doc to sync as it covers the most frequently changed models.

## Scope

- `docs/domain/source-model.md` only

## What to verify

1. **Feed model** — Compare against ORM `Feed` class (table: `source_definitions`):
   - `source_definition_id`, `project_id`, `source_type`
   - `source_contract_version`, `access_reference`
   - `selection_information`, `layout_information`, `destination_object_references` (JSON)
   - `sample_policy`, `source_details` (JSON)
   - `copybook_text` (Text)
   - `status`, `mapping_hints` (Text), `transformation_instructions` (Text)
   - **NEW**: `mapping_hints` field — verify
   - **NEW**: `transformation_instructions` field — verify

2. **FeedSlice model** — Compare against ORM `FeedSlice` class:
   - `header_csv`, `slice_payload` (JSON), `status`
   - `approval_rejection_reason`, `parse_warnings` (JSON list)
   - `data_profile` (JSON) — verify
   - `file_storage_path` — verify
   - `approved_at`, `approved_by_user_id` — verify

3. **FeedSliceRow model** — Verify: `row_index`, `row_csv`

4. **FeedComment model** — Verify: `comment_id`, `feed_id`, `user_id`, `body`, `source_slice_id`, `created_at`

5. **SourceSchemaArtifact model** — Verify:
   - `schema_artifact_id`, `source_definition_id`, `source_slice_version`
   - `columns` (JSON list)
   - **NEW**: `destination_ddl` (Text, nullable) — this was added in task 001h0

6. **SourceValueSummary model** — Verify:
   - `summary_id`, `source_definition_id`, `source_slice_version`, `field_name`
   - `value_counts` (JSON dict), `created_at`

7. **MappingSnapshot model** — Verify all fields:
   - `mapping_snapshot_id`, `project_id`, `source_definition_id` (nullable)
   - `destination_object_name`, `mapping_snapshot_version`
   - `field_bindings` (JSON list), `destination_fields` (JSON list, nullable)
   - `destination_columns` (JSON list, nullable)
   - `status` (default "approved"), `current_ball_role` (nullable)
   - `approved_at`, `approved_by_user_id`

8. **LookupSnapshot model** — Verify:
   - `lookup_snapshot_id`, `project_id`, `lookup_name`
   - `lookup_snapshot_version`, `value_map` (JSON dict)
   - `status` (default "approved"), `approved_at`, `approved_by_user_id`

9. **LookupValueMap model** — Verify all fields:
   - `lookup_value_map_id`, `project_id`, `lookup_name`
   - `destination_table` (JSON list) — verify
   - `source_value_map` (JSON dict, default {})
   - **NEW**: `destination_mappings` (JSON list, default []) — from task 001fi
   - **NEW**: `unmapped_source_values` (JSON list, default []) — from tasks 001gu, 001gs
   - `status` (default "draft")

10. **ProjectFiber model** — Verify:
    - `fiber_id`, `feed_id`, `project_id`
    - `fiber_type`, `fiber_key`
    - `status`, `source` (default "manual")
    - `proposed_mappings` (JSON list, nullable) — verify this is nullable
    - **NEW**: `field_bindings` (JSON list, nullable) — verify
    - `output_sql` (Text, nullable)
    - `created_at`, `updated_at`

11. **MappingArtifact model** — Verify fields

12. **DryRunArtifact model** — Verify fields

13. **ProjectSchemaAnalysis model** — Verify fields

14. **CodeGenerationArtifact model** — Verify fields

15. **AICallLog model** — Verify fields

16. **MappingBindingSignOff model** — Verify fields

17. **LookupSignOff model** — Verify fields

18. **Lookup fiber states** — Verify the state machine described in the doc matches actual fiber statuses

19. **Sign-off workflow** — Verify multi-party sign-off logic matches `MappingBindingSignOff` and `LookupSignOff` models

20. **API endpoints** — Verify all listed endpoints exist in routes

## Out of scope

- Any other domain doc files
- Backend implementation changes

## Acceptance criteria

- [ ] All Feed, FeedSlice, FeedSliceRow, FeedComment fields match ORM
- [ ] All SourceSchemaArtifact fields match ORM (including new destination_ddl)
- [ ] All SourceValueSummary fields match ORM
- [ ] All MappingSnapshot fields match ORM (including current_ball_role)
- [ ] All LookupSnapshot fields match ORM
- [ ] All LookupValueMap fields match ORM (including destination_mappings, unmapped_source_values)
- [ ] All ProjectFiber fields match ORM (including field_bindings, proposed_mappings nullable)
- [ ] All artifact models (MappingArtifact, DryRunArtifact, CodeGenerationArtifact, ProjectSchemaAnalysis, AICallLog) match ORM
- [ ] All sign-off models (MappingBindingSignOff, LookupSignOff) match ORM
- [ ] Fiber state machines are accurate
- [ ] Sign-off workflow is accurate
- [ ] Changelog updated
- [ ] timestamp updated
