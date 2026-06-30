# 001h-ui-portfolio-project-screens

> **SCOPE NARROWED** — Project detail → `001p` (done). Run progress → `001u` (done).
> Remaining valid scope: portfolio dashboard at `/dashboard` only.

## Domain

- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)
- [project.md](/Users/vjkotra/projects/katana/docs/domain/project.md)

## Objective

Build the portfolio dashboard at `/dashboard` using `mockmigration/src/components/Portfolio.tsx`
as the visual and interaction template. The dashboard is the primary post-login landing
page: it shows a summary strip, a filterable project table, and role-aware affordances.

## Scope

- Replace the placeholder in `web/app/dashboard/page.tsx` with the real portfolio page
- `SummaryStrip` — 4 metric cards: Total, Active, Archived, Pending Approvals
- `PortfolioTable` — sortable table with inline filter bar (search, status, environment)
- "Initiate project" CTA for `central_team` and `project_stakeholder` roles
- Tests for all new components

## Out of Scope

- Stage, blocked status, or days-in-stage (requires new backend API; tracked as 001af)
- Source type column (lives on SourceDefinition, not available on project list)
- Modifying the existing `web/components/projects/ProjectTable.tsx` or `/projects` page

## API Used

| Call | Client function | Notes |
|---|---|---|
| `GET /projects?include_archived=true` | `listProjects(token, { includeArchived: true })` | Stakeholder filtering already handled by backend |
| `GET /approvals/count` | `getPendingApprovalCount(token)` | From `slice-approval-api.ts` |

## Portfolio Table Columns

| Column | Source |
|---|---|
| Project name + ID | `name`, `projectId` |
| Goal (truncated to 60 chars) | `goal` |
| Target DB | `domainConfig.targetDbEngine` |
| Environments | `executionEnvironments` (pill tags) |
| Status | `status` (active/archived chip) |
| Last Updated | `updatedAt` (date only) |
| Open Details | link to `/projects/[id]` |

## Acceptance Criteria

- Dashboard loads projects and pending approval count in parallel
- Summary strip shows correct totals derived from the full project list (including archived)
- Default filter is status=active; search and environment filter apply client-side
- `project_stakeholder` sees only their member projects (enforced by backend; no frontend change needed)
- `read_only_auditor` does not see the "Initiate project" button
- Sort by project name (default asc) and last updated (default desc) both work
- Loading state shown while data is fetching; error banner shown on failure
- No changes to `/projects` page or `ProjectTable.tsx`

## Test Expectations

- `SummaryStrip` renders 4 cards with correct values
- `PortfolioTable` filters by search term, status, and environment
- `PortfolioTable` sorts by name and updatedAt
- `PortfolioTable` hides "Initiate project" for `read_only_auditor`
- Dashboard page renders loading state, error state, and loaded state
