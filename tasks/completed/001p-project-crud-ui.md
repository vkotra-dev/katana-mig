# 001p-project-crud-ui

**Plan:** `plans/2026-06-29-001p-project-crud-ui.md`

## Domain

- [ui.md](../docs/domain/ui.md)
- [project.md](../docs/domain/project.md)
- [api.md](../docs/domain/api.md)
- `docs/design/stitch/07-project-initiation.md` — wizard layout and step definitions
- `docs/design/stitch/06-project-detail.md` — project detail screen

## Objective

Build the project CRUD UI: a five-step project initiation wizard (stitch 07) that
collects all project and source configuration, and the project list + detail pages.

## Scope

- `web/lib/projects-api.ts` — typed fetch wrappers for all project endpoints;
  `createProject` payload includes domain_config fields and source declaration data
- `web/components/projects/ProjectTable.tsx` — sortable project list with status chips
- `web/components/projects/ProjectInitiationWizard.tsx` — five-step wizard (see below)
- `web/app/projects/page.tsx` — projects list page with "Initiate project" button
- `web/app/projects/new/page.tsx` — full-page wizard route
- `web/components/projects/ProjectDetailView.tsx` — overview panel for a single project
- `web/app/projects/[id]/page.tsx` — project detail page with tab shell
- Vitest tests for all of the above

## Wizard steps (stitch 07)

Left-rail step indicator. Each step validates before advancing.

**Step 1 — Identity**

Fields: project name (required), goal, stakeholder email, central-team assignee email,
lawful basis for processing (required). Maps to `ProjectCreateRequest` core fields.

**Step 2 — Source**

Source type selector: `database` | `fixed_length_file` | `csv` | `xls` | `composite`.
Type-specific fields shown conditionally:
- `fixed_length_file`: file path/pattern, record length, encoding, header/trailer rules,
  fixed-width spec document upload field (label only — actual file upload is in 001q's
  Sources tab; this step captures the declaration metadata for `SourceContractCreateRequest`)
- `csv` / `xls`: delimiter, sheet name, headers flag, column hints
- `database`: connection ref, schema/table, filters, key hints
- `composite`: repeatable list of backing source labels

Maps to `POST /projects/{id}/source-contracts` (called after project is created on submit).

**Step 3 — Destination**

Large textarea + file upload for destination schema DDL. Operator pastes or uploads the
client-owned target DB schema (e.g. `CREATE TABLE Customer (...)`). Stored verbatim as
`domain_config.destination_schema_ddl`. A note reads:
_"The destination schema is client-owned and will not be invented by Katana."_

**Step 4 — Environments**

Ordered, addable list of environment names (e.g. `dev`, `uat`, `prod`). Drag-to-reorder.
Maps to `domain_config.environments`.

**Step 5 — Review & submit**

Read-only summary of all fields across steps 1–4. Primary **Submit** button.
On submit:
1. `POST /projects` — creates project with all domain_config fields
2. `POST /projects/{id}/source-contracts` — declares source contract from step 2 data
3. On success: navigate to `/projects/{id}` and show "Project initiated — definition v1 created"
4. On failure: show error inline on step 5; do not reset wizard state

## Out of Scope

- Actual file upload for source data (001q — Sources tab)
- Run progress and artifact tabs on the detail page (001u)
- Approval workflows (001ab, 001w, 001x)
- Backend changes (001o)

## Acceptance Criteria

- Wizard advances step by step; back navigation preserves entered values
- Step 1 blocks advance until name and lawful basis are filled
- Step 2 shows only the fields relevant to the selected source type
- Step 5 shows a read-only summary of all entered data
- Submit makes two API calls in sequence; navigates to project detail on success
- Submit failure shows inline error without clearing wizard state
- "Initiate project" button on projects list is visible to `central_team` only
- `ProjectTable` renders name, goal excerpt, status chip, and created date
- Detail page loads project via `GET /projects/{id}` and renders overview panel including `domain_config` fields
- All API client functions handle `401` and `404` error codes

## Test Expectations

- Wizard: step 1 next button disabled until required fields filled
- Wizard: step 2 renders `fixed_length_file` fields when that type is selected; hides them for `csv`
- Wizard: step 5 displays values entered in steps 1–4
- Wizard: submit calls `createProject` then `declareSourceContract` in order
- Wizard: on submit error, wizard stays on step 5 with error message visible
- `ProjectTable` renders rows and shows empty state when list is empty
- `ProjectDetailView` renders name, goal, status, domain_config fields, and created date
- Detail page shows `project_not_found` error on 404
- "Initiate project" button absent for `project_stakeholder` and `read_only_auditor`
