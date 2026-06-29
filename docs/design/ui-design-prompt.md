# Katana — UI Design Prompt

> Paste this into a visual design tool (Figma Make / Stitch / UX Pilot / similar).
> It is written as a screen-by-screen brief. Generate **high-fidelity mockups**,
> not code. Aesthetic: **data-dense enterprise operations console** (reference
> feel: Linear, Datadog, Retool, AWS-console-but-calmer). Generate every screen
> and every state listed.

---

## 1. Product context

**Katana** is the operator console for a **governed data-migration platform**. Teams
run migrations from declared source systems (databases, fixed-length files, CSV,
XLS, composite) into a client-owned destination schema. Work is organized into
**projects**; each project moves through a **governed lifecycle** with **human
approval gates**; execution happens as **object-level runs** that are auditable,
checkpointed, and reconciled.

The console is used by operators to **monitor projects, approve gates, launch and
watch runs, inspect reconciliation/lineage, and administer users**. It is an
internal tool: information density and fast scanning beat marketing polish.

This is **not** a consumer app. Optimize for: scanning many rows, comparing
versions, reading status at a glance, and never losing audit context.

---

## 2. Roles (drive every screen)

Three roles share one app with **role-determined views**. Role is fixed by the
session; the UI shows/hides accordingly. Design the role differences explicitly —
show how each screen looks per role where it differs.

| Role | Scope | Can do | Cannot do |
|---|---|---|---|
| **central_team** | All projects (admin) | Everything: Gate 1 approval, impact + dry-run review, initiate projects, raise CRs, manage users & membership, launch runs | — |
| **project_stakeholder** | Only projects they are a *member* of | Gate 2 approval, lookup-delta review, initiate projects/CRs on member projects, launch runs on member projects | See non-member projects; any Gate 1 action; manage users |
| **read_only_auditor** | All projects, view-only | View all artifacts, lineage, reconciliation; download evidence | Approve, create, raise CRs, launch runs, manage users |

Show, for each role: a **role badge** in the top bar, disabled/hidden actions
(render disabled controls with a tooltip "Requires central_team" rather than
silently hiding, except whole projects a stakeholder can't see — those are hidden).

**Landing screen by role:** central_team → Portfolio dashboard. project_stakeholder
→ their project home (filtered portfolio). read_only_auditor → read-only portfolio.

---

## 3. Visual system

- **Density:** compact. Table row height ~36–40px. Generous use of tabular data,
  status chips, and inline metadata. Section padding tight but breathable.
- **Palette:** neutral gray canvas (light mode primary; include a dark-mode
  variant of the shell + one screen). Single brand accent (deep indigo or teal)
  used sparingly for primary actions and active nav. Reserve color for **status
  semantics**, not decoration.
- **Status colors (consistent everywhere):**
  - Green = healthy / complete / approved / reconciled
  - Amber = action required / awaiting approval / paused
  - Red = failed / blocked / rejected / reconciliation failed
  - Blue = in progress / running
  - Gray = idle / queued / archived / not started
- **Typography:** clean sans (Inter/IBM Plex Sans). **Monospace** (IBM Plex Mono /
  JetBrains Mono) for all IDs, version refs, hashes, snapshot versions, and
  timestamps — these are first-class data here.
- **Components to standardize:** status chip, role badge, "action required" badge,
  version pill (mono, copyable), environment tag, breadcrumb with `project_id`,
  data table with sticky header + column sort + filter bar, side drawer for
  detail/inspect, multi-step wizard, approval panel with structured fields,
  timeline/stepper, key-value metadata grid, empty/loading/error states.
- **IDs & versions are always visible and copyable.** Every project, run, and
  artifact view shows its `project_id` / `run_id` / `artifact_id` + version,
  with a copy affordance. Deep links preserve these.

---

## 4. Global shell (every authenticated screen)

- **Left sidebar nav** (collapsible), sections gated by role:
  - Portfolio (dashboard)
  - Projects (browse / filtered to membership for stakeholders)
  - Runs (cross-project run list — central_team & auditor; stakeholder sees member-project runs)
  - Approvals / Action Required (badge with count)
  - Reconciliation
  - Admin → Users, (Admin → Membership) — **central_team only**
- **Top bar:** breadcrumb (carries project context), global search (projects/runs by
  id or name), **notifications bell** with unread count, **role badge**, user menu
  (profile, change password, sign out).
- **Project switcher:** prominent control in the top bar when inside a project
  context; shows only projects the user may see.
- **"Action Required" is a first-class concept:** a persistent badge in nav + a
  filterable inbox surfacing every gate/review waiting on *this* user's role.

---

## 5. Screens — generate all of these, with all states

For **every** screen also produce: **loading** (skeleton), **empty**,
**error/unavailable**, and **insufficient-permission** variants.

### 5.1 Login

- Centered card on neutral canvas. Product mark "Katana", subtitle "Migration
  operations console".
- Fields: **email**, **password**, "Sign in" primary button. Inline error on
  invalid credentials ("Invalid email or password" — never reveal which).
- States to show: default, validating, error (bad credentials), **disabled
  account** ("This account has been disabled. Contact your administrator."),
  session-expired return ("Your session expired, please sign in again").
- No public sign-up. Small footer: "Accounts are provisioned by your central team."

### 5.2 First-run bootstrap (admin seed)

- Shown only when no users exist yet. "Set up the first administrator" — create the
  bootstrap `central_team` account (email, display name, password, confirm).
- One-time; after creation it routes to login. Show a success confirmation state.

### 5.3 Portfolio dashboard (landing for central_team / auditor)

- **Header:** title "Portfolio", count of projects, filter bar (source type,
  lifecycle stage, blocked, action-required), search.
- **Primary view: dense project table**, one row per project, columns:
  - Project name (link) + `project_id` (mono, secondary)
  - Source type tag
  - Current lifecycle stage (chip)
  - Stage entered date
  - **Days in current stage** (numeric; amber/red if stale)
  - **Blocked** indicator + reason on hover
  - **Action required** badge if a gate is waiting (links to the gate)
- Sortable columns; sticky header; row hover reveals quick actions (open, view runs).
- **Summary strip** above the table: counts of projects by stage, # blocked,
  # awaiting approval.
- Empty state: "No projects yet" + (for central_team) "Initiate a project" CTA.
- Stakeholder variant: same layout, filtered to member projects, titled "My projects".

### 5.4 Project detail

- **Header:** project name, `project_id` (copy), source type, current stage chip,
  blocked banner if blocked, environment ordering tags, primary actions
  (role-gated): "Launch run", "Raise change request", "Initiate" disabled here.
- **Tabs:**
  1. **Overview** — lifecycle **stage timeline / stepper** (ingestion → intake →
     planning → approval gate → implementation → verification → review → delivery),
     current stage highlighted, with stage entered date + days-in-stage. Key-value
     metadata grid: goal, destination schema owner, lawful basis, contacts/escalation,
     definition version (`definition_id`, mono), assumptions, **unresolved questions**
     called out in amber.
  2. **Artifacts** — table of artifacts produced per stage (source schema, domain
     object map, mapping snapshot, lookup snapshot, codegen input, knowledge-freeze)
     each with **version pill** and produced date; click → artifact inspect drawer.
  3. **Change requests** — active CRs and status (migration CR / lookup-delta CR).
  4. **Knowledge-freeze history** — versioned list with published dates.
  5. **Runs** — run history table (see 5.11) scoped to this project, with
     reconciliation status per run.
- Auditor variant: all tabs visible, all action buttons hidden/disabled.

### 5.5 Project initiation (wizard)

central_team and project_stakeholder. Multi-step wizard (data-dense, not playful):

- **Step 1 — Identity:** project name, goal, stakeholder email, central-team
  assignee, **lawful basis for processing** (required).
- **Step 2 — Source:** source type selector (`database`, `fixed_length_file`,
  `csv`, `xls`, `composite`), data availability, and **type-specific fields**:
  - database: connection ref, schema/table/view/query, filters, key hints
  - fixed-length: file path/pattern, record length, offsets/widths, encoding,
    header/trailer rules, **fixed-width spec document upload**
  - csv/xls: sheet name, delimiter, headers, column hints
  - composite: add multiple backing sources (repeatable rows)
- **Step 3 — Destination:** **destination schema DDL** input/upload (client-owned;
  the form makes clear the system will not invent schema).
- **Step 4 — Environments:** ordered list of execution environments (drag to order).
- **Step 5 — Review & submit:** read-only summary of everything; submit creates a
  **frozen ProjectDefinition** + opens the initial change request. Show the
  validation-error state inline per field, and a final "Project frozen — definition
  v… created" success state with link to the new project.

### 5.6 Change request initiation

- Modal or focused page. CR type selector: **Migration CR** (source/destination
  schema change, new columns, changed mappings) or **Lookup-delta CR**.
- Migration CR: structured fields describing the change + affected objects.
- Lookup-delta CR: **pre-populated** when launched from a failed execution's
  unmapped value (show source column + exact value, read-only, plus proposed
  mapping). Submit + success state.

### 5.7 Approvals — shared pattern

All gate/review screens share an **approval panel**: left = the evidence/artifacts
to review; right = the **decision panel** with structured fields. Decisions submit
an `ApprovalRecord` to the Approval Service — the UI **never** calls execution
directly (note this in the UI copy/microcopy where relevant). Show: submitting,
success ("Approval submitted, run will resume"), and **Approval Service
unavailable** error (preserves parked state, offers retry).

#### 5.7.1 Gate 1 review — central_team

- Panels: **domain object map**, **PII classification**, **coverage gaps**.
- Actions: **Approve** / **Push back** (structured target fields required —
  validation error if missing).

#### 5.7.2 Gate 2 review — project_stakeholder

- **Side-by-side**: `LookupInventoryArtifact` vs `LookupMapArtifact`.
- Rows show state chip: **confirmed / low-confidence / unmapped / overridden**.
- Controls: **bulk approve**, **individual override** (inline editor), **resolve
  unmapped**, **submit for approval**. Unmapped rows block submission — show the
  blocked state.

#### 5.7.3 Impact review — central_team

- Shown after a pushback yields an impact report. Show: pushback comment, the
  structured target fields, **affected objects**, **replay scope**, recommendation.
  Approve / push back again.

#### 5.7.4 Dry-run review — central_team

- One **dry-run artifact per domain object**: sample rows + annotations, target
  object summary, **PII masking status** badge per field. Approve / push back.

#### 5.7.5 Lookup-delta review — project_stakeholder

- Triggered when execution discovers a new lookup value. Show: discovering
  **environment**, **source column + exact value**, **AI-proposed mapping**,
  **confidence score** (visual meter). Accept / override / reject → resumes the
  blocked run.

### 5.8 Reconciliation view (all roles; read-only for auditor)

- **Check results** (pass/fail list with reasons), **row-count summary**
  (source vs destination, rejected, duplicated, partially mapped),
  **lineage explorer** (see 5.10), and a **download** for the reconciliation
  artifact. Failed checks rendered red and pinned to top. Make clear that
  infrastructure success ≠ logical success — a run can be infra-green but
  reconciliation-red.

### 5.9 Runs — list / cross-project

- Dense table, columns: `run_id` (mono), project, **destination object**,
  **environment** tag, status chip (queued / running / paused / completed /
  failed / awaiting approval), current stage, started, last checkpoint,
  reconciliation status. Filter bar (project, environment, status, object).
- Row actions: open run detail; paused rows show "resume" affordance (role-gated).
- **Primary action: "Launch run"** (see 5.10).

### 5.10 Launch run (manual launch flow) — KEY SCREEN

A modal/wizard for manually starting a run. central_team (any project) and
project_stakeholder (member projects). Design it as a **preflight-gated launcher**:

- **Step 1 — Target:** select **project** (scoped to permissions) → **destination
  object** (single — one object per run) → **environment** (single; multi-env work
  becomes separate runs, surface this hint).
- **Step 2 — Snapshot set (auto-pinned, read-only):** the launcher selects the
  **latest approved** artifacts and shows the exact set that will be pinned:
  source slice version, mapping snapshot version, lookup snapshot version,
  codegen-input version, knowledge-freeze version — each as a **version pill**.
  Copy: "These versions will be pinned to the run and used on resume."
- **Step 3 — Preflight checks (blocking):** a checklist with pass/fail rows; the
  **Launch** button stays disabled until all pass:
  - Frozen project definition present ✔/✘
  - Required source slice approved & present ✔/✘
  - Required downstream snapshots approved ✔/✘
  - Object not already running for this environment ✔/✘
  Each failed check shows the reason + a link to resolve (e.g., "Source slice not
  approved → go to Gate / approvals"). Show the **blocked** state explicitly.
- **Step 4 — Launch:** confirm → run is leased & queued. Success state routes to
  the new **Run detail** with status "queued". Show error state if lease fails.

### 5.11 Run detail / progress — KEY SCREEN

Single run, polled (progress updates by polling — no live socket needed; show a
"last updated" timestamp + manual refresh + subtle auto-refresh indicator).

- **Header:** `run_id` (copy), project link, **destination object**, **environment**
  tag, big **status** chip, started / last-checkpoint timestamps. If paused, an
  **amber pause banner** with the reason. If failed, **red banner** with the
  recorded failure reason. Resume action (role-gated) when paused.
- **Progress strip:** queue state → active stage → completion, as a stepper with
  the current stage emphasized; show **pause reason** inline at the paused step.
- **Tabs / sections:**
  1. **Overview** — key-value grid: status, current stage, current object,
     environment, start metadata, pause metadata, resume metadata (which checkpoint
     it resumed from), completion metadata.
  2. **Pinned snapshots** — the exact consumed versions (source slice, mapping,
     lookup, codegen input, knowledge-freeze) as copyable version pills. Emphasize:
     this is the audit answer to "which approved set did this run use."
  3. **Checkpoints** — list of checkpoint boundaries: stage, object, environment,
     selected snapshots, last completed boundary, pause reason if any. The
     checkpoint a resume would continue from is highlighted.
  4. **Timeline / history** — ordered event log: stage transitions, pauses (with
     reason: human approval / provider limit / budget exhausted / missing
     prerequisite / policy rejection), resumes, errors. Each event timestamped (mono).
  5. **Reconciliation & lineage** — reconciliation status + link to the full
     reconciliation view; **lineage explorer**: which source row → which destination
     row, mapping rules used, rejected/duplicated/partially-mapped rows. If the run
     completed without lineage evidence, show it as **incomplete** (red), not success.
- **Failure/pause affordances:** for a `LookupDeltaCR` raised mid-run, surface a
  link to the lookup-delta review; for budget exhaustion show it as a graceful
  terminal state (gray/neutral, not red error).

### 5.12 Admin → Users (central_team only)

- **User table:** display name, email (mono), **role** chip, **status**
  (active / disabled / soft-deleted), created, last updated. Filter by role/status,
  search by email/name.
- **Create user** (drawer/modal): email, display name, role selector
  (central_team / project_stakeholder / read_only_auditor), temporary password.
  Validation: duplicate email rejected inline.
- **Edit user** (drawer): update display name + **role change** (role changes
  treated as an explicit, confirmed action — show a confirm step). Cannot escalate
  via any side path.
- **Soft-delete user:** confirm dialog ("This deactivates the account and blocks
  login; history is preserved"). Soft-deleted rows render grayed with a "Deleted"
  chip — never disappear (audit). Show that a soft-deleted user is rejected even
  with a still-valid token (copy in the confirm dialog).
- States: empty, loading, permission-denied (non-admin sees nothing here / nav item
  hidden).

### 5.13 Admin → Project membership (central_team only)

- Within a project (or under Admin): **members table** for a project —
  `project_stakeholder` users assigned to it (name, email, added date, remove).
- **Add member:** picker limited to `project_stakeholder`-role users (reject
  non-stakeholder roles inline). Prevent duplicate membership (show no-op/blocked
  state). Note in UI: central_team and auditor don't need membership rows.

### 5.14 Self-service — change password

- From user menu. Fields: current password, new password, confirm. Verify current
  password (error state on mismatch). Success confirmation. Make clear this path
  **cannot change role**.

### 5.15 Notifications

- **Bell dropdown** + a full **notifications page** (filterable, mark-read).
- Event types, each with an icon + deep link to the relevant project/artifact/run:
  Gate 1 waiting, Gate 2 waiting, impact review waiting, dry-run waiting,
  **lookup delta discovered**, **reconciliation failed**, knowledge-freeze
  published, **execution complete**.
- Unread emphasized; "action required" notifications styled amber and pinned.
- Empty state + grouping by project/date.

---

## 6. Cross-cutting states & rules to depict

- **Permission denied:** project a stakeholder can't access → 404-style "Not found
  or no access" page (don't confirm existence). Disabled actions → tooltip naming
  the required role.
- **Run progress crossing project boundary →** not-found, never leak.
- **Approval Service unavailable →** non-destructive error that preserves the parked
  approval and offers retry.
- **Everything is auditable:** prefer states that preserve/soft-delete over
  destructive removal; never invent a "delete forever" affordance for users or runs.
- **Version coherence:** wherever multiple snapshot versions appear together, make it
  visually obvious they are a *coherent pinned set*, not arbitrary latest values.

---

## 7. Deliverables expected from the design tool

Generate, at minimum:
1. The **global shell** (light + one dark variant) with role badge variations.
2. **Login**, **bootstrap**, **change password**.
3. **Portfolio dashboard** (central_team, stakeholder, auditor variants).
4. **Project detail** (all tabs) + **project initiation wizard** (all steps).
5. All **approval/review** screens (Gate 1, Gate 2, impact, dry-run, lookup delta).
6. **Reconciliation** + **lineage explorer**.
7. **Runs list**, **Launch-run flow** (all steps incl. failed preflight),
   **Run detail** (all tabs incl. paused + failed states).
8. **Admin Users**, **Membership**, **Notifications**.
9. For each: loading, empty, error, and permission-denied variants.

Keep it dense, legible, status-driven, and audit-first.
