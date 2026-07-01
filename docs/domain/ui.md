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
- **Sources** — list of source contracts with add-source action; DDL analysis prompt banner (see below)
- **Artifacts** — source slice versions and approval status
- **SQL Bundle** — navigates to the SQL bundle delivery page (see SQL bundle delivery)

The **DDL analysis prompt banner** appears in the Sources tab when at least one source exists but no schema analysis has been run yet. It shows a prompt with an "Analyze DDL" button. The button is disabled if the project has no `destination_schema_ddl` set. Clicking it triggers AI analysis and hides the banner on success.

Also shows:
- active CRs and their status
- knowledge-freeze history
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

When a schema analysis exists, the downloaded bundle orders SQL blocks by FK dependency sequence and prefixes each with `-- [01] table_name`, `-- [02] table_name`, etc. Without an analysis, blocks are ordered alphabetically with plain `-- table_name` headings.

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

Shown when a pushback yields an impact report.

The screen shows:

- the pushback comment
- the structured target fields
- affected objects
- replay scope
- recommendation

### Dry-run review

Audience: `central_team`

Shown when dry run is enabled.

The screen shows:

- one dry-run artifact per domain object
- sample rows and annotations
- target object summary
- PII masking status

### Lookup delta review

Audience: `project_stakeholder`

Shown when a new lookup value is discovered during execution.

The screen shows:

- environment that discovered the value
- source column and exact value
- AI-proposed mapping
- confidence score

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

- gate 1 waiting
- gate 2 waiting
- impact review waiting
- dry-run waiting
- lookup delta discovered
- reconciliation failed
- knowledge freeze published
- execution complete

Notifications should deep-link to the relevant project or artifact view.

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
- Should notifications land in-app only, email only, or both?

## Changelog

- 2026-06-29: Added derived UI bundle page to consolidate the operator-facing
  contract from the current specs.
