# Task 001bw Summary — Dashboard Health View

Implemented project health summaries in the backend database mapping and surfaced them in the dashboard's summary cards and portfolio table.

## Details
1. **API Schema**:
   - Added `HealthStatus` literal type (`"healthy" | "pending_review" | "needs_attention"`).
   - Added `ProjectHealthSummary` schema (holding `feed_status`, `mapping_status`, and `lookup_status`).
   - Extended `ProjectResponse` with an optional `health` field.
2. **Backend database queries**:
   - Implemented `_load_project_health_summaries` in `management/projects.py` to batch-load health states for lists of project IDs.
   - **Feed status**: Joined `Feed` and the latest `FeedSlice` via a `max(created_at)` subquery. Checks if any feed has no slices/rejected slices (`"needs_attention"`), pending approvals (`"pending_review"`), or approved slices (`"healthy"`).
   - **Mapping status**: Joined `Feed` and the latest `MappingSnapshot` via a `max(created_at)` subquery. Checks for rejected mappings (`"needs_attention"`), draft mappings (`"pending_review"`), or approved mappings (`"healthy"`).
   - **Lookup status**: Evaluated `ProjectFiber` statuses directly for lookup types: deferred maps to `"needs_attention"`; inputs_ready/mapped/operator_assigned map to `"pending_review"`; business_approved/operator_triggered/codegen_complete map to `"healthy"`.
   - Updated `list_projects` to query and attach health summaries.
3. **Frontend changes**:
   - Exposed `ProjectHealthSummary` types and mapped camelCase properties.
   - Extended `<SummaryStrip>` from 3 cards to 5 cards (adding "Needs Attention" and "Pending Review" metrics) and updated grid width layout.
   - Extended `<PortfolioTable>` columns to display dynamic health chips columns for **Feeds**, **Mappings**, and **Lookups**.
4. **Tests**:
   - Added `test_project_health_summaries` in the backend python suite (all 134 python tests pass).
   - Updated and extended `SummaryStrip.test.tsx` and `PortfolioTable.test.tsx` (all 267 frontend tests pass).
