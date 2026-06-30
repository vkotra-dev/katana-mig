# 001h-ui-portfolio-project-screens

> **SCOPE NARROWED** — Original scope included project detail + run progress, both now
> covered by completed/planned tasks:
> - Project detail page → `001p` (project-crud-ui)
> - Run progress view → `001u` (runs-ui)
>
> **Remaining valid scope:** Portfolio dashboard only (stitch `02-portfolio-dashboard.md`) —
> the project list view with per-project stage badges, blocked indicators, and
> action-required chips that span multiple projects.

## Domain

- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)
- [project.md](/Users/vjkotra/projects/katana/docs/domain/project.md)
- [runs.md](/Users/vjkotra/projects/katana/docs/domain/runs.md)

## Objective

Build the portfolio and project screens that surface project stage, blocked
status, run progress, and project-local drilldown without widening the UI
scope beyond the operator views already described in the domain docs.

## Scope

- Portfolio dashboard
- Project detail page
- Run progress view
- Status chips, blocked indicators, and action-required badges
- Membership-filtered project lists

## Out of Scope

- Login flow
- Full approval workflows
- Mapping and reconciliation drilldowns beyond the project/run surfaces needed
  for the shell

## Acceptance Criteria

- The portfolio view lists projects with stage and blocked status
- The project detail view shows lifecycle, artifacts, CRs, and run history
- The run progress view shows queue, stage, pause reason, checkpoint, and
  completion state
- Project-stakeholder content remains filtered to member projects

## Test Expectations

- Portfolio rows render with compact status chips and blocked indicators
- Project detail includes the expected lifecycle and run sections
- Run progress reflects the current stage and pause reason
- Cross-project content is hidden or rejected for non-member users

