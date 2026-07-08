# Task Summary — 001cb (Promote LookupValueMap to Project Scope)

## Changes

1. **Alembic Database Migration**:
   - Created migration `2149fa46cde2_promote_lookup_value_maps_to_project_scope.py`.
   - Added nullable `project_id` column to `lookup_value_maps` table.
   - Backfilled `project_id` by joining with `source_definitions`.
   - Deduped overlapping maps by retaining the latest `created_at` row per `(project_id, lookup_name)`.
   - Set `project_id` to `NOT NULL`.
   - Dropped the old `source_definition_id` column and foreign key constraint.
   - Added a new unique constraint `uq_lookup_value_maps_project_name` on `(project_id, lookup_name)`.

2. **Core Database Models**:
   - Refactored `LookupValueMap` in [db/models.py](file:///Users/vjkotra/projects/katana/engine/src/migrations_engine/db/models.py) to reference `project_id` and have a foreign key to `project_registry`.

3. **Backend Service & Routes**:
   - Refactored `create_lookup_value_map`, `list_lookup_value_maps`, and snapshot lookup logic in [lookup_mapping.py](file:///Users/vjkotra/projects/katana/engine/src/migrations_engine/management/lookup_mapping.py).
   - Updated list endpoint query in [routes/lookup.py](file:///Users/vjkotra/projects/katana/engine/src/migrations_engine/routes/lookup.py) to serve `/projects/{project_id}/lookup-maps`.
   - Updated Fiber Approval bridge in [fibers.py](file:///Users/vjkotra/projects/katana/engine/src/migrations_engine/management/fibers.py) to write to the project-scoped map and merge mappings without overwriting.
   - Adjusted `change_requests.py` and `gates.py` lookup map lookups to filter by project scope.

4. **Backend Tests**:
   - Updated model tests in `test_lookup_mapping_models.py`.
   - Updated service tests in `test_lookup_mapping_service.py`.
   - Updated API tests in `test_change_requests_api.py`, `test_gates_api.py`, and `test_lookup_mapping_api.py`.
   - Updated integration test `test_lookup_fiber_approval_bridges_to_lookup_value_map` in `test_lookup_fiber_api.py` to match the project-scoped model.

5. **Frontend Client & Pages**:
   - Refactored API client in [lookup-api.ts](file:///Users/vjkotra/projects/katana/web/lib/lookup-api.ts) and its tests in [lookup-api.test.ts](file:///Users/vjkotra/projects/katana/web/lib/lookup-api.test.ts).
   - Enhanced [page.tsx](file:///Users/vjkotra/projects/katana/web/app/projects/%5Bid%5D/feeds/%5BfeedId%5D/page.tsx) to:
     - Render project-level inherited mappings inside a read-only **Already mapped in project** section in the lookup card workspace when loaded.
     - Filter out already-mapped values from the AI proposed mappings list to avoid duplicate review items.

## Verification

- **Backend tests**: Passed 98/98 unit tests successfully.
- **Frontend tests**: Passed 268/268 vitest tests successfully.
- **Production Build**: Successfully compiled Next.js bundle without compilation or TypeScript errors.
