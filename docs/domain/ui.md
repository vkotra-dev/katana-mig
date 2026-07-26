---
type: Domain Spec
title: User Interface
description: The derived human-interface contract — operator screens, role-gated views, per-feed workspaces, multi-party sign-off review, dashboard health, notifications, and approval flows for all 5 platform roles.
tags:
  - ui
  - screens
  - workflow
  - review
  - dashboard
timestamp: 2026-07-26
---

# UI

This page is the derived human-interface bundle for the migration platform.

It consolidates the current UI-related behavior from the numbered specs and the
domain pages so there is one place to read the operator experience without
chasing the full spec archive.

**Derived from:** `docs/domain/auth.md`, `docs/domain/management.md`,
`docs/domain/project.md`, `docs/domain/runs.md`, `docs/domain/source-model.md`,
`docs/domain/security.md`, and the approval-service behavior in the harness
bundle.

This page is the working contract for the UI bundle. The numbered specs remain
the historical derivation archive only.

`service_account` is not a UI audience. It is a non-human integration principal
that submits approvals or API actions through automated channels, not through
the operator screens described here.

## Purpose

Provide the operator-facing contract for:

- project initiation
- project browsing and scoped access
- change request initiation
- approval actions for Gate 1, Gate 2, impact review, dry run, and lookup delta
- reconciliation visibility
- notification surfaces
- progress tracking for long-running runs

## Audience and roles

Five roles use the same application with role-determined views.

Role is session-scoped. `central_team` and `project_stakeholder` access is
membership-scoped (requires project membership).

| Role | Can do | Cannot do |
|------|--------|-----------|
| `admin` | User management, PM assignment (`/admin/assign-pm`), all `pm` capabilities | In-project operations without project membership |
| `pm` | Project create/edit/copy, member management, project oversight, assign stakeholders | Gate approvals, mapping edits (unless also `central_team` on project) |
| `central_team` | In-project operations: mapping, codegen, review, approval, feed slice approval (per-feed), Gate 1 approval, impact review, dry-run review, raise CRs — requires project membership | User management, PM assignment, see non-member projects |
| `project_stakeholder` | View and approve within assigned projects: Gate 2 approval, lookup-delta review, mapping/lookup review grid (approve or request revision per feed), raise CRs on member projects | See other projects, Gate 1 or feed slice approval actions, user management |
| `read_only_auditor` | View all artifacts, lineage, reconciliation, download artifact views | Approve, create, raise CRs, manage users or membership, download raw staging data |

## Entry points

- `admin` and `pm` land on the portfolio dashboard.
- `central_team` lands on the portfolio dashboard.
- `project_stakeholder` lands on their project home or filtered project view.
- `read_only_auditor` lands on a read-only selector or portfolio view.

## Vocabulary

| Term | Meaning |
|---|---|
| **Feed** | A single CSV file or one XLSX sheet — the raw data unit provided for migration. Formerly called "Source"; renamed in tasks 001bf/001aj. |
| **FeedSlice** | A windowed, PII-masked sample of a Feed; the working unit AI analyzes |
| **Lookup Fiber** | A unit of work mapping unique source values for one lookup column to destination reference rows |
| **Mapping Fiber** | A unit of work mapping source columns to destination table columns for one domain object |

The per-feed workspace lives at `/feeds/[feedId]` (within the project scope). Sections: slice status, field mapping (multi-table), lookup fibers, reviews.

Role-gated routing: `central_team` → full workspace; `project_stakeholder` → grid view.

## Screens

### Authentication

Audience: unauthenticated users.

Screens:

- login
- password-reset request
- password-reset confirmation

These screens are the entry point to the rest of the application and must use
the authoritative auth contract from `auth.md`.

### Portfolio dashboard

**SummaryStrip** — 5-card strip at the top of the dashboard showing aggregate counts (e.g. total projects, feeds pending, mappings in review, lookups outstanding, approvals waiting).

**`ProjectHealthSummary`** — health rollup widget per project with feed/mapping/lookup status indicators.

One row per project:

- project name
- source type
- current lifecycle stage
- stage entered date
- days in current stage
- blocked indicator with reason if blocked
- action required badge if a gate is waiting
- health chip columns (feed health, mapping health, lookup health)

Project IDs and feed IDs are no longer displayed in the portfolio table (tasks 001ci, 001cj).

This is the high-level operational surface for cross-project monitoring.

### Project detail

Full lifecycle view for one project. Four tabs:

- **Overview** — stage timeline, metadata layout (matching the edit form layout: goal, execution environments, target database engine, staging schema, destination schema, dry run, destination schema DDL, sample policy, constraints, unresolved questions, assumptions, lexicon scope), and a model policy block that shows the effective model and whether it came from a project override or `engine.yaml`
- **Feeds** — list of feeds with add-feed action; DDL analysis prompt banner (see below)
- **Artifacts** — feed slice versions and approval status
- **SQL Bundle** — navigates to the SQL bundle delivery page (see SQL bundle delivery)

The **DDL analysis prompt banner** appears in the Feeds tab when at least one feed exists but no schema analysis has been run yet. It shows a prompt with an "Analyze DDL" button. The button is disabled if the project has no `destination_schema_ddl` set. Clicking it triggers AI analysis and hides the banner on success.

The Overview tab also shows:
- active CRs and their status
- **knowledge-freeze history** — read-only panel listing runs where a knowledge freeze was recorded, newest first. Columns: date, run ID, destination object, environment, frozen artifact ID, run status. Empty state if no freezes yet.
- execution run history with reconciliation status

This is the project-local drilldown view.

### Project edit

Route: `/projects/[id]/edit`

The edit screen uses the same project metadata layout as the detail screen for
non-editable fields. The AI model policy section is displayed in a collapsed
accordion by default; detail and edit layouts are aligned (task 001bb).
Each model override input shows the current global default model name directly
below the input so operators can see what will be used if they leave the field
blank.

**Global Coding Standards** — a textarea on the project edit page where the
operator enters project-wide coding standards. These instructions are injected
into every codegen prompt for the project (task 001cn).

### SQL bundle delivery

Audience: all authenticated roles with project access.

Route: `/projects/{id}/codegen`

Panels:

- **Feeds** — list of feed contracts with "Generate SQL" action per row (`central_team` only)
- **Latest active artifact** — destination name, artifact ID, created date, feed slice version; "Copy SQL" and "Download delivery bundle" buttons; full SQL preview in a scrollable code block
- **Delivery bundle sidebar** — active artifact count; note that the download saves as `delivery-bundle.sql`
- **Schema dependency analysis** — shows identified / processed / pending counts for destination objects; "Re-analyze DDL" button to re-run AI analysis; "analyzed at" timestamp. Empty state if no analysis has been run.
- **Artifact history** — all artifacts (active and superseded) with timestamps

Delivery bundle sequencing:

- All lookup fiber SQL is prefixed `0000_<lookup_table_name>` — sorts to the top, runs in any order (reference data is independent)
- Domain object SQL is prefixed `0001_`, `0002_`, etc. in FK dependency sequence from schema analysis

Example:
```
0000_account_type_ref
0000_status_code_ref
0001_customers
0002_orders
0003_order_items
```

Without a schema analysis, domain objects are ordered alphabetically with plain `-- table_name` headings.

### Feed intake

Audience: `central_team`.

Route: `/projects/[id]/feeds/new`

The operator uploads one or more files:

- **CSV** — one file = one Feed
- **XLSX** — one file = N Feeds; system auto-creates one Feed per sheet on upload

After upload, each Feed is sliced: a window of rows is extracted and PII fields are replaced with typed tokens (`TAXID_XXXX`, `EMAIL_XXXX`, `DOB_XXXX`, `PHONE_XXXX`). The token type is determined by the masking policy and carries enough semantic meaning for AI to understand the column's purpose. The resulting FeedSlice is stored and used for all subsequent AI analysis.

A progress indicator is shown during PII masking.

### Fiber management

Audience: `central_team`.

Route: `/projects/[id]/feeds/[feed_id]/fibers`

After a FeedSlice is created, the system creates fibers for the Feed by analyzing the FeedSlice against the destination DDL.

**Lookup Fibers** — one per lookup column identified. A lookup fiber is `deferred` by default. To continue it the operator provides:

1. **Source values** — multiline list of unique values for this lookup column (operator may add values beyond what the FeedSlice window showed, knowing the full domain of the real data)
2. **Destination lookup CSV** — reference data from the destination system; flexible multi-column schema: id, description, plus any industry-specific columns (NSIC, SIC, regulatory flags, etc.)

Once both inputs are provided, the fiber calls AI to propose source→destination mappings with confidence scores. Each mapping is a `LookupMapping` row linking a `LookupSourceEntry` to a `LookupDestEntry` — not a JSON blob. Unmapped values are directly queryable, delta values are added as new rows without replacing existing mappings, and the destination reference data retains all its columns (id, description, industry codes, etc.).

Operator can defer any lookup fiber and return to it later. Deferred lookup fibers do not block mapping fibers.

**Mapping Fibers** — one per domain object identified. A mapping fiber runs immediately on creation — it calls AI with the FeedSlice columns and the destination table DDL to propose field-level bindings (source column → destination column).

**Manual fibers** — within the fiber management screen for a feed, the operator can add custom lookup or mapping fibers the AI did not identify. Useful when the AI misses a lookup column or when an enum needs to be defined explicitly from the feed data. A manually added lookup fiber goes to `deferred` and follows the normal inputs → AI mapping → approval flow. A manually added mapping fiber opens the grid for operator-entered field bindings. Both are tied to the same `feed_id` as the AI-spawned fibers. `source` field on the fiber distinguishes `"auto"` from `"manual"`.

**Fiber lifecycles:**

Lookup: `created → deferred → inputs_ready → ai_running → mapped → operator_assigned → business_approved → operator_triggered → codegen_complete`

Mapping: `created → ai_running → mapped → operator_assigned → business_approved → operator_triggered → codegen_complete`

Codegen gates on all fibers for a domain object being `operator_triggered` — both its mapping fiber and every lookup fiber it references must be complete before codegen runs.

### Fiber detail page

Route: `/projects/[id]/feeds/[feedId]/fibers/[fiberId]`

The detail page shows the current fiber status, the lookup proposed-mappings
panel or the domain_object field-bindings panel, and the role/status-gated
actions for the approval chain:

1. **Operator assigns**
2. **Business user approves**
3. **Operator triggers**

### Per-feed workspace

Route: `/feeds/[feedId]` (within project scope, i.e. `/projects/[id]/feeds/[feedId]`)

Audience: role-gated. `central_team` sees the full Feed Detail workspace. `project_stakeholder` (business user) is routed directly to the grid view at `/projects/[id]/feeds/[feedId]/review`.

**Feed list** (project detail → Feeds tab) — one row per feed. Row click routes by role: `central_team` → Feed Detail; `project_stakeholder` → grid view.

**Feed Detail** (`central_team` workspace) — vertical sections:

1. **Slice status panel** — current slice status chip (`pending_approval` / `approved` / `rejected`). Feed slices are immutable post-creation — the upload card is removed once a slice exists (task 001bj). The former slice approval gate overlay is replaced with a slice preview and an 'Analyze with AI' button (task 001bl). Rejection triggers a replacement upload flow with status banners: amber = pending, red = rejected (task 001bu).
2. **Data profile review card** — dedicated card for stakeholders showing a stats strip (row count, column count, null percentages), client-side PII scan results, and an unmasked sample table (task 001cc).
3. **Copybook display-time masking** — copybook values are masked at display time. `admin` and `pm` roles see a 'Show original' toggle to reveal unmasked values (task 001ck).
4. **Field mapping section (multi-table)** — AI-identified destination tables displayed as expandable cards (one per table). Each card shows field bindings with binding type badges:
   - `direct` — source field maps directly to destination column
   - `detail_fk` — FK whose referenced table is also produced by this feed
   - `lookup_fk` — FK into a reference/lookup table (amber badge); reference table name shown
5. **Lookup fibers section** — one card per `lookup_fk` binding. Each card: source field name, reference table chip, in-place editable source value list (`discovery_type="operator"`), "Run AI mapping" button.
6. **Transformation Instructions** — a textarea where the operator enters per-feed transformation instructions injected into the codegen prompt for this feed (task 001cn).
7. **AI Prompt Log Viewer** — unified viewer for AI prompts, raw responses, and reasoning across all call types (schema analysis, bindings, lookups, codegen). Replaces legacy in-line panels.
8. **Reviews section** — the shared ReviewGrid component (see below).

**Review grid** (`/projects/[id]/feeds/[feedId]/review`) — accessible to all roles; default landing for `project_stakeholder`.

Sections:
- **Multi-table display** — review shows multiple destination tables per feed (task 001bo). Read-only expandable accordion per destination table. Columns: Source field | Destination field | Binding type badge.
- **Feed slice sample data** — feed slice sample values displayed alongside binding rows so reviewers can see real data in context (task 001bs).
- **Unmapped source fields warning** — amber warning panel listing source columns that have no binding to any destination field (task 001bv).
- **Operator mapping edit** — `central_team` operators can edit the destination field selector per binding, then 'Save mapping' and 'Submit for review' (task 001bq).
- **Lookup value mapping grids** — one section per lookup field. Columns: Source value | Destination row | Confidence | Status.
- **Per-binding sign-off** — operator and stakeholder each sign off per binding; PM can poke either party via a nudge mechanism (task 001cl).
- **Bulk approve/reject** — single action to approve or reject all draft snapshots for a feed (task 001bp).
- **Approval strip** — Approve and Request revision controls, visible to `project_stakeholder` only. Request revision requires a comment.
- **`FeedCommentThread`** — comment thread component on the review page for operator ↔ stakeholder discussion (task 001cl).

Approval workflows live inside per-feed workspaces. There is no global `/approvals` page.

### Mapping review

Audience: `central_team` (operator) and `project_stakeholder` (business user).

The mapping and lookup review is managed per-feed through the per-feed workspace and review grid. Both operator and business user see the same ReviewGrid component; the approval controls are role-gated.

**Mapping grid columns** (in the review grid):

| Source Column | Destination Column | Binding Type | Reference Table |
|---|---|---|---|
| `CUST_ID` | `customer_id` | direct | — |
| `ACCT_TYPE` | `account_type_id` | lookup_fk | `account_type_ref` |
| `FULL_NAME` | `first_name` | direct | — |
| `DEPT_FK` | `department_id` | detail_fk | `departments` |

The AI detects which destination columns are `lookup_fk` and names the reference table — no manual lookup name entry by the operator.

**Lookup value mapping grids** — one section per `lookup_fk` binding. Rows: source value → destination row, with confidence score and status (confirmed / pending / rejected).

**Comments** — each Feed has a comment thread accessible to both operator and business user throughout the review. Notifications fire when either party adds a comment. AI reads the full comment thread at codegen time as additional context for scripting the migration proc.

### Project initiation

Fields:

- project name
- source type
- data availability
- destination schema DDL
- fixed-width spec document when applicable
- ordered execution environments
- stakeholder email
- central team assignee
- lawful basis for processing

### Project copy

Audience: `pm`, `admin`.

Route: project list page → 'Copy from…' button opens a modal.

Two-step flow:
1. Select source project from a searchable list.
2. Edit the new project name and assign stakeholders.

The copied project inherits feeds, mapping configuration, and coding standards
from the source but starts with a fresh lifecycle (task 001bt).

Submit flow:

1. Validate the form.
2. Create a frozen `ProjectDefinition`.
3. Open the initial CR.
4. Hand off to the conductor.

### Change request initiation

Supported CR types:

- migration CR
- lookup delta CR

Migration CRs cover source or destination schema changes, new columns, and
changed mappings.

Lookup delta CRs cover newly discovered lookup values and are pre-populated when
raised from failed execution.

### Gate 1 review

Audience: `central_team`

Panels:

- domain object map
- PII classification
- coverage gaps

Actions:

- approve
- push back with structured target fields

The UI never routes directly to the analyser. It submits an `ApprovalRecord` to
the Approval Service.

### Gate 2 review

Audience: `project_stakeholder`

Shows `LookupInventoryArtifact` and `LookupMapArtifact` side by side.

Rows have the following states:

- confirmed
- low confidence
- unmapped
- overridden

Controls:

- bulk approve
- individual override
- resolve unmapped
- submit for approval

### Impact review

Audience: `central_team`

Route: `/projects/[id]/runs/[run_id]/impact`

Shown after Gate 1 is rejected. The operator sees the full impact before
correcting the issues and re-submitting.

The screen shows:

- **Pushback panel** — `required_changes` text, `affected_objects` list, rejector and timestamp
- **Replay scope** — other runs in the project that reference the same domain objects and would need to re-execute if the correction is made
- **AI recommendation** — based on `required_changes` + `affected_objects` + field bindings, AI suggests what specifically to fix and what the minimal replay scope is

Actions:

- **Acknowledge and fix** — operator marks they have understood the impact; run is unlocked for correction and re-submission to Gate 1
- **Request clarification** — adds a comment to the gate record; run stays blocked

### Dry-run review

Audience: `central_team`

Route: `/projects/[id]/runs/[run_id]/dry-run`

Shown when `dry_run = true` on the project and the run reaches the dry-run
stage. The engine maps all source rows to destination rows but does not write
to the destination. Instead it produces a `DryRunArtifact` per domain object.

The screen shows one panel per domain object:

**Sample rows table** — columns: source field value | mapped destination value
per field binding. Lookup substitutions are shown inline (source code →
destination description). PII fields appear as their typed tokens (`TAXID_XXXX`,
`EMAIL_XXXX`, etc.) confirming masking is applied correctly.

**Target object summary** — total rows that would succeed; rows that would fail
(unmapped lookup values, null constraint violations); field coverage percentage.

**PII masking status** — list of fields classified as PII and the token type
applied to each.

Actions:

- **Approve** — run promotes from `dry_run_review` to actual execution
- **Push back** — run stays paused; operator provides a structured comment;
  central team investigates before re-triggering

### Lookup delta review

Audience: `project_stakeholder`

Route: `/projects/[id]/change-requests/[cr_id]`

Shown when execution discovers an unmapped lookup value in the real data (beyond the FeedSlice window) and pauses the run.

The screen shows:

- destination object and run context
- lookup name (source column)
- the exact unmapped value found in the data
- a single input: "Map this to:" with a text field
- Submit button

On submit:
1. The new mapping is added to the lookup value map
2. A new LookupSnapshot is generated and auto-approved
3. The paused run resumes from its checkpoint
4. The CR is closed

Entry point: Overview tab active CRs list links here. Notification also deep-links to this page.

### Reconciliation view

Audience: all roles, read-only for auditor.

The screen shows:

- check results
- row count summary
- lineage explorer
- downloadable execution reconciliation artifact

### Run progress view

Audience: project-scoped operators and auditors.

Polling endpoint:

- `GET /projects/{project_id}/runs/{run_id}/progress`

The view should show:

- queue state
- active stage
- pause reason
- checkpoint metadata
- completion / failure status

## Navigation and access

- Portfolio view is global for `admin`, `pm`, `central_team`, and read-only auditors.
- Project-stakeholder views are filtered to member projects.
- Project-level deep links must always include `project_id`.
- Artifact deep links should preserve `artifact_id` and version.

**Admin nav dropdown** — `admin` role sees a dropdown in the top nav with two items:
- **Manage Users** — links to the user management page.
- **Assign PM to Project** — links to `/admin/assign-pm`, a standalone page with dual-autocomplete pickers (one for PM, one for project) (task 001cf).

## Notifications

**`NotificationBell`** — bell icon in the top nav bar. Polls `GET /notifications/count` for unread count. Clicking opens a dropdown listing recent notifications with deep links (task 001at).

Actions:
- **Mark read** — per notification item
- **Mark all read** — bulk action in the dropdown header

UI surfaces receive notification events for:

| Event | Recipients |
|---|---|
| `gate_1_waiting` | `central_team` users |
| `gate_2_waiting` | `project_stakeholder` members |
| `impact_review_waiting` | `central_team` users |
| `dry_run_waiting` | `central_team` users |
| `lookup_delta_discovered` | `project_stakeholder` members |
| `reconciliation_failed` | all project members |
| `knowledge_freeze_published` | all project members |
| `execution_complete` | all project members |
| `feed_comment_added` | the other party (operator comments → stakeholders; stakeholder comments → operator) |

**Delivery:**
- **In-app bell** — `NotificationBell` component with unread count badge polled via `GET /notifications/count`; dropdown list with deep links; mark-as-read per item or bulk mark-all-read
- **Email** — sent at event creation time using SMTP config and `User.email`; plain-text template with event description and deep link

Notifications deep-link to the relevant project or artifact view.
Polling is used for in-app; WebSockets are not required.

## Technical shape

- Server-rendered or simple SPA is acceptable.
- Polling is acceptable for progress.
- WebSockets are not required for the current contract.
- All approval submissions must go through the Approval Service.
- Session state determines role; request bodies do not.

## Failure modes

| Situation | Handling |
|-----------|----------|
| User not authenticated | Redirect to login or reject |
| User lacks project membership | Hide or reject project-scoped pages |
| Approval form missing required structured fields | Validation error |
| Approval Service unavailable | Show failure and preserve parked state |
| Run progress request crosses project boundary | 404 |
| Lookup delta still unmapped | Gate remains blocked |

## Acceptance criteria

- [ ] The UI distinguishes global, project-scoped, and read-only audiences.
- [ ] Project-stakeholder views are limited to member projects.
- [ ] Gate 1 and Gate 2 flows submit structured approvals, not direct conductor calls.
- [ ] Project initiation creates a frozen `ProjectDefinition`.
- [ ] Run progress is available by polling and respects project boundaries.
- [ ] Reconciliation and lineage are viewable without write access.

## Open questions

- Which pages should remain in the UI spec versus the derived domain bundle?
- ~~Should auditors be allowed to download raw staging data or artifact views only?~~ — **Resolved:** Auditors get artifact views only. Display-time masking (task 001ck) ensures raw staging data is not exposed.
- Should project initiation be split into a wizard or a single form?

## Changelog

- 2026-07 — Feeds rename; 5-role capabilities; removed global approvals; admin dropdown nav; feed slice immutability and workflow overhaul; multi-table review with sign-offs; bulk approve/reject; operator edit; sample data; unmapped fields warning; dashboard health view; notifications; project copy UI; AI reasoning panel; codegen instructions panels
- 2026-07-04: Removed global Approvals nav item and inbox; added per-feed workspace and role-gated review grid; updated mapping review to reflect AI-driven binding type detection (direct/detail_fk/lookup_fk) and reference table names; updated role table and SQL bundle delivery to use Feeds terminology.
- 2026-07-03: Clarified notification email delivery as SMTP-backed instead of a logging stub.
- 2026-07-01: Added Feed/FeedSlice/Fiber vocabulary; Feed intake screen; Fiber
  management screen; Mapping review 3-step approval chain; updated delivery
  bundle to 0000/0001+ sequencing; fleshed out Lookup delta review screen.
- 2026-06-29: Added derived UI bundle page to consolidate the operator-facing
  contract from the current specs.
