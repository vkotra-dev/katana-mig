# Task 001bt — Project Copy

**Plan:** `plans/2026-07-07-001bt-project-copy.md`

## Context

Migrations recur — same source system, new data extract each quarter. Today an operator must create a project from scratch, re-enter all constraints, re-define all feeds, and re-type all mapping hints before they can upload fresh data and re-run analysis. A project copy operation eliminates that toil by cloning all configuration into a new project that starts in the "awaiting upload" state.

## Scope

**Backend:**
- `POST /projects/{project_id}/copy` route (`central_team` only)
- `copy_project(db, *, actor, source_project_id, name, stakeholder_user_ids)` management function
- Copies: `ProjectRegistry` fields, `ProjectDefinition` (constraints, assumptions, model_policy, domain_config, project_resources, lexicon_scope), all `Feed` rows including `mapping_hints`
- Does NOT copy: `FeedSlice`, `FeedSliceRow`, `MappingSnapshot`, `RunRecord`, `FeedComment`, fiber data, lookup snapshots
- Assigns specified `stakeholder_user_ids` as `project_stakeholder` memberships on the new project
- Returns the new `ProjectResponse`

**Frontend:**
- Project list page: replace "New Project" button with a dropdown button — options: **New Project** (existing flow) and **Copy from…**
- "Copy from…" opens a two-step modal:
  - **Step 1:** Searchable list of active (non-archived) projects to copy from
  - **Step 2:** Editable name field (pre-filled "Copy of [source name]") + optional stakeholder assignment (blank by default — stakeholders from source project are not carried over)
  - Confirm → `POST /projects/{id}/copy` → redirect to `/projects/[newProjectId]`
- New `copyProject(token, sourceProjectId, { name, stakeholderUserIds })` function in `web/lib/projects-api.ts`

## Key Design Decisions

- `central_team` users have global project access — no membership records needed for operators; only stakeholder assignments are configurable at copy time
- Feeds land in the empty "no slices uploaded" state — 001bu's amber/upload flow handles the forcing function
- `mapping_hints` carries over verbatim — this is the primary value of copy for recurring migrations
- Source project's stakeholders are NOT pre-populated in step 2 — each cycle assigns its own business reviewers

## Out of Scope

- Copying `FeedSlice`, `MappingSnapshot`, `RunRecord`, or any execution history
- Bulk copy of multiple projects
- Scheduled / automated recurrence

## Acceptance Criteria

- Admin clicks "Copy from…", picks a source project, edits name and optional stakeholders, confirms
- New project appears in the list with all config (constraints, feed definitions, mapping hints, destination DDL) copied
- All feeds have no slices — workspace shows "No slices uploaded yet"
- Stakeholders from the source project do NOT appear on the new project unless explicitly added in step 2
- Redirect lands on the new project's detail page
- TypeScript compiles with no new errors

## Pitfalls

- `ProjectDefinition` is the frozen definition — copy all relevant fields into a new row with a new `definition_id`; do not mutate or re-point the original
- Feed `copybook_artifact` (fixed-length file layout) should be copied — it is structural config, not data
- Validate that `source_project_id` is not archived before copying; reject with 422 if so
- The modal's step 1 list should exclude archived projects

## Commit

- `feat(001bt): add project copy with config and mapping hints carry-forward`
