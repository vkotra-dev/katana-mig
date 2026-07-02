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

Three roles use the same application with role-determined views.

Role is session-scoped, and `project_stakeholder` access is membership-scoped.

| Role | Can do | Cannot do |
|------|--------|-----------|
| `central_team` | All projects, Gate 1 approval, impact review, dry-run review, initiate projects, raise CRs, manage users and membership | — |
| `project_stakeholder` | Member projects only, Gate 2 approval, lookup-delta review, initiate projects and CRs on member projects | See other projects, Gate 1 actions |
| `read_only_auditor` | View all artifacts, lineage, reconciliation, download evidence | Approve, create, raise CRs, manage users or membership |

## Entry points

- `central_team` lands on the portfolio dashboard.
- `project_stakeholder` lands on their project home or filtered project view.
- `read_only_auditor` lands on a read-only selector or portfolio view.

## Vocabulary

| Term | Meaning |
|---|---|
| **Feed** | A single CSV file or one XLSX sheet — the raw data unit provided for migration |
| **FeedSlice** | A windowed, PII-masked sample of a Feed; the working unit AI analyzes |
| **Lookup Fiber** | A unit of work mapping unique source values for one lookup column to destination reference rows |
| **Mapping Fiber** | A unit of work mapping source columns to destination table columns for one domain object |

`SourceDefinition` and `SourceSlice` in the codebase correspond to Feed and FeedSlice respectively. The rename is tracked in task 001aj.

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

One row per project:

- project name
- source type
- current lifecycle stage
- stage entered date
- days in current stage
- blocked indicator with reason if blocked
- action required badge if a gate is waiting

This is the high-level operational surface for cross-project monitoring.

### Project detail

Full lifecycle view for one project. Four tabs:

- **Overview** — stage timeline, key–value metadata (goal, environments, target DB engine, staging schema, dry-run flag, destination schema DDL, sample policy, constraints, unresolved questions, assumptions, lexicon scope)
- **Feeds** — list of feeds with add-feed action; DDL analysis prompt banner (see below)
- **Artifacts** — source slice versions and approval status
- **SQL Bundle** — navigates to the SQL bundle delivery page (see SQL bundle delivery)

The **DDL analysis prompt banner** appears in the Feeds tab when at least one feed exists but no schema analysis has been run yet. It shows a prompt with an "Analyze DDL" button. The button is disabled if the project has no `destination_schema_ddl` set. Clicking it triggers AI analysis and hides the banner on success.

The Overview tab also shows:
- active CRs and their status
- **knowledge-freeze history** — read-only panel listing runs where a knowledge freeze was recorded, newest first. Columns: date, run ID, destination object, environment, frozen artifact ID, run status. Empty state if no freezes yet.
- execution run history with reconciliation status

This is the project-local drilldown view.

### SQL bundle delivery

Audience: all authenticated roles with project access.

Route: `/projects/{id}/codegen`

Panels:

- **Sources** — list of source contracts with "Generate SQL" action per row (`central_team` only)
- **Latest active artifact** — destination name, artifact ID, created date, source slice version; "Copy SQL" and "Download delivery bundle" buttons; full SQL preview in a scrollable code block
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

### Mapping review

Audience: `central_team` (operator) and `project_stakeholder` (business user).

Three-step approval chain per Feed:

1. **Operator assigns** — reviews AI-proposed field bindings and lookup mappings in the mapping grid; sets default values for destination columns with no source equivalent; adds comments for the business user; submits
2. **Business user approves** — reviews the same grid (without the Default Value column); adjusts lookup value selections; responds to operator comments; approves
3. **Operator triggers** — final cursory review; explicitly triggers fiber lineup for codegen

**Mapping grid:**

| Source Column | Destination Column | Lookup | Default Value | Status |
|---|---|---|---|---|
| `CUST_ID` | `customer_id` | — | — | mapped |
| `ACCT_TYPE` | `account_type` | `account_type_map` | — | mapped |
| `FULL_NAME` | `first_name` | — | — | mapped |
| `FULL_NAME` | `last_name` | — | — | mapped |
| — | `created_by` | — | `"MIGRATION"` | default |
| `LEGACY_CODE` | — | — | — | unmapped (data loss) |

Rules:
- One source field may appear on multiple rows mapping to different destination columns
- Unmapped source columns are shown with no destination — documented as potential data loss
- Destination columns with no source are shown with no source — operator assigns a static default value
- Default Value column is visible to operator only; business user sees the grid without it
- Business user may change lookup value selections (pick a different destination row for any source value)

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

- Portfolio view is global for `central_team` and read-only auditors.
- Project-stakeholder views are filtered to member projects.
- Project-level deep links must always include `project_id`.
- Artifact deep links should preserve `artifact_id` and version.

## Notifications

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
- **In-app bell** — unread count badge polled via `GET /notifications/count`; list view with deep links; mark-as-read per item or bulk
- **Email** — notification delivery hook exists at event creation time; the base slice logs instead of sending, and real SMTP delivery is tracked separately

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
- Should auditors be allowed to download raw staging data or artifact views only?
- Should project initiation be split into a wizard or a single form?

## Changelog

- 2026-07-03: Clarified notification delivery as in-app plus a stubbed email hook.
- 2026-07-01: Added Feed/FeedSlice/Fiber vocabulary; Feed intake screen; Fiber
  management screen; Mapping review 3-step approval chain; updated delivery
  bundle to 0000/0001+ sequencing; fleshed out Lookup delta review screen.
- 2026-06-29: Added derived UI bundle page to consolidate the operator-facing
  contract from the current specs.
