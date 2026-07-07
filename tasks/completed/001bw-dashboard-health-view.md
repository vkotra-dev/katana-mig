# Task 001bw — Dashboard Health View

**Plan:** `plans/2026-07-07-001bw-dashboard-health-view.md`

## Context

The dashboard shows high-level metrics via the `SummaryStrip` and a list of active projects in the `PortfolioTable`. However, currently, the project status is static ("active"/"archived") and does not give the operator or business stakeholders a visual indication of health: whether a feed lacks slices (needs upload), has rejected slices (needs replacement/revision), has draft mapping snapshots (needs review), or has pending lookups. Adding a dynamic health dashboard view helps team members identify bottlenecks and act quickly.

## Scope

**Backend:**
- Define `ProjectHealthSummary` schema with three fields: `feed_status`, `mapping_status`, and `lookup_status` (each representing `HealthStatus` which can be `"healthy" | "pending_review" | "needs_attention"`).
- Implement `_load_project_health_summaries` in `management/projects.py` using batch queries modeled exactly after `_load_latest_run_summaries`. It queries:
  - Feed status (needs attention if latest slice is rejected or no slices exist; pending review if latest slice is pending approval; healthy if latest slice is approved).
  - Mapping status (needs attention if mapping snapshot has draft/rejected status and action is required; pending review if snapshot is submitted but pending approval; healthy if approved).
  - Lookup status (needs attention if lookups are empty or rejected; pending review if lookups are draft or pending stakeholder response; healthy if all lookups are confirmed).
- Add keyword arg `health: Optional[ProjectHealthSummary] = None` to `_project_response` to remain compatible with all single project fetch/update call sites.
- Update `list_projects` to load project health summaries in batch and attach them to the response.

**Frontend:**
- Add `ProjectHealthSummary` interface in `web/lib/projects-api.ts` and attach optional `health?: ProjectHealthSummary` to `ProjectRecord`.
- Map response fields from snake_case to camelCase inside `mapProjectRecord`.
- Extend `<SummaryStrip>` from 3 cards to 5 cards to include:
  - **Needs Attention** (red/amber cards for projects with "needs_attention" health status in any category).
  - **Pending Review** (amber/blue cards for projects with "pending_review" health status).
- Update the Dashboard page to calculate these counts dynamically from the projects list.
- Extend `<PortfolioTable>` columns to display dynamic chips for **Feeds**, **Mappings**, and **Lookups** using a `healthChip` helper that renders green, amber, or red badges based on their health state.

## Key Design Decisions

- Health calculation logic runs on the database/backend during `list_projects` via optimized subqueries to avoid N+1 queries.
- Mapping and slice lookups join on `Feed` because slices and snapshots do not hold a direct `project_id`.
- The frontend dashboard remains fast by utilizing the pre-calculated health statuses in `ProjectRecord` instead of fetching full feeds for every project.

## Acceptance Criteria

- Dashboard shows 5 summary cards: Total Projects, Active Migrations, Needs Attention, Pending Review, and Completed (Archived).
- "Needs Attention" card counts projects where any health field (`feedStatus`, `mappingStatus`, or `lookupStatus`) is `"needs_attention"`.
- "Pending Review" card counts projects where any health field is `"pending_review"` and none are `"needs_attention"`.
- `<PortfolioTable>` renders 3 distinct health chip columns:
  - **Feeds**: red if no slices or rejected; amber if pending approval; green if approved.
  - **Mappings**: red if rejected/no mappings; amber if draft; green if approved.
  - **Lookups**: red if input needed/rejected; amber if pending; green if confirmed.
- TypeScript compiles cleanly with no warnings or errors.

## Pitfalls

- **No project_id**: Remember that `FeedSlice` and `MappingSnapshot` do not have a `project_id` column. They must be joined to `Feed` (via `source_definition_id`) which has `project_id`.
- **Keyword compatibility**: `_project_response` must default `health=None` so that calls in `get_project` or `create_project` do not break.

## Commit

- `feat(001bw): implement dashboard project health summaries and columns`
