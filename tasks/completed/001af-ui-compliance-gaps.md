# Task 001af — UI Compliance Gaps

**Plan:** `plans/2026-06-30-001af-ui-compliance-gaps.md`

## Domain

- `docs/domain/ui.md` — authoritative screen contract; gaps are measured against this document only

## Scope

Fix the gaps between the current web implementation and `docs/domain/ui.md`. Gaps were
identified by auditing all implemented screens against the domain spec. Only gaps that
`ui.md` explicitly requires are in scope — mockmigration-only aesthetic differences are
not fix obligations.

## Gap 1 — Portfolio dashboard missing columns and filter (ui.md lines 68–77)

`ui.md` requires per-row: project name, source type, current lifecycle stage,
stage entered date, days in current stage, blocked indicator with reason,
action required badge.

Current `PortfolioTable.tsx` shows: project name, goal (60 chars), target DB,
environments, status, last updated.

Missing from web:
- **source type** column — available on `ProjectRecord` if returned by `GET /projects`
- **current lifecycle stage** column — requires `RunRecord.current_stage` for the
  project's latest run; needs new field in `GET /projects` response or a separate
  per-project run summary endpoint
- **stage entered date** — from `RunRecord.updated_at` when `current_stage` last changed,
  or from `RunRecord.created_at` as a proxy
- **days in current stage** — computed from stage entered date to now
- **blocked indicator** — `RunRecord.status == "paused"` with `pause_metadata.gate`
- **action required badge** — `RunRecord.status == "awaiting_approval"`

Also missing: source type filter (`csv | fixed_length_file | database | xls | composite`).

Backend change required: `GET /projects` response must include `latest_run_summary`:
`{current_stage, status, source_type, stage_entered_at}`.

## Gap 2 — Project detail missing stage timeline and history tabs (ui.md lines 82–88)

`ui.md` requires: stage timeline, artifacts per stage, active CRs and status,
knowledge-freeze history, execution run history with reconciliation status.

Current `web/app/projects/[id]/page.tsx` has three tabs: Overview, Sources, Artifacts.

Missing:
- **Stage timeline** (lifecycle stepper) — circular stage indicators, current stage
  highlighted, passed stages marked, days-in-stage display
- **Change Requests tab** — list of open/closed CRs for the project
- **Knowledge-freeze history tab** — list of freeze events

The Artifacts tab and Sources tab already exist and cover "artifacts per stage" and
"execution run history" partially.

Stage timeline data source: sequence of stages from domain spec; current stage
from latest `RunRecord.current_stage`; stage entry dates from run history.

## Gap 3 — globals.css Tailwind v4 utility class registration

Several utility classes are used across components but produce no CSS output because
they are not registered as `@theme` variables in Tailwind v4:

Used but missing from `@theme` or hand-written utilities:
- `bg-primary` — used in buttons, active nav states
- `bg-error` / `text-error` / `border-error` — used in error banners
- `text-warning` — used in SummaryStrip pending-approvals accent
- `bg-primary-container` / `text-on-primary-container` — used in hover states

`text-primary` works because it is hand-written at line 44 of globals.css. The rest
must be added either as `@theme` tokens or as hand-written `.bg-primary { ... }` rules.

## Acceptance criteria

- [ ] `GET /projects` returns `latest_run_summary` per project (or equivalent)
- [ ] `PortfolioTable` renders source type, lifecycle stage, days in stage,
      blocked indicator, action required badge
- [ ] Source type filter with domain values works in `PortfolioTable`
- [ ] Project detail page has a stage timeline / lifecycle stepper component
- [ ] `globals.css` registers all used utility classes so they generate CSS output
- [ ] No visual regressions in existing screens

## Notes

- Change Requests tab and Knowledge-freeze tab are lower priority within this task;
  they require new backend endpoints to list CRs and freeze events per project
- Stage timeline can use a simple horizontal step indicator; it does NOT need
  the `animate-pulse` from mockmigration (that is not doc-specified)
- The `latest_run_summary` can be a nullable field on `ProjectRecord` — projects with
  no runs yet show empty stage/status cells
- Do not add columns or filters that are not in `ui.md` even if mockmigration shows them
