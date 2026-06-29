**Style — data-dense enterprise operations console** (web / desktop; reference feel: Linear, Datadog, Retool). Light mode primary. Neutral gray canvas, a single indigo accent used only for primary actions and active nav. Reserve color for **status**: green = healthy / approved / complete, amber = action-required / paused / awaiting approval, red = failed / blocked / rejected, blue = in-progress / running, gray = idle / queued / archived. Compact tables (~38px rows) with sticky sortable headers, status chips, role badges, filter bars. Sans (Inter) for text; **monospace** (JetBrains Mono) for all IDs, version refs, and timestamps — each shown with a copy icon. Tight but legible spacing. This is an internal, audit-first operations tool, not a marketing site.

---

**Screen name:** `Run Detail` — use this exact name as the screen/frame title.

Design the **Run Detail** screen for Katana — a single migration run, inside the app
shell. Progress updates by polling, so include a "last updated" timestamp, a manual
refresh button, and a subtle auto-refresh indicator.

**Header:** monospace `run_id` (copy icon), project link, **destination object**,
**environment** tag, a large **status chip** (queued / running / paused / completed /
failed / awaiting approval), and started / last-checkpoint timestamps. A
role-gated **Resume** button appears when paused.

**Progress strip:** a horizontal stepper — queue state → active stage → completion —
with the current stage emphasized.

**Tabbed sections below:**
1. **Overview** — key-value grid: status, current stage, current object, environment,
   start metadata, pause metadata, resume metadata (which checkpoint it resumed from),
   completion metadata.
2. **Pinned snapshots** — the exact consumed versions as copyable monospace version
   pills: source slice, mapping, lookup, codegen input, knowledge-freeze.
3. **Checkpoints** — table of checkpoint boundaries (stage, object, environment,
   selected snapshots, last completed boundary, pause reason); highlight the one a
   resume would continue from.
4. **Timeline** — ordered event log with monospace timestamps: stage transitions,
   pauses (with reason), resumes, errors.
5. **Reconciliation & lineage** — reconciliation status + a link to the full
   reconciliation view.

---

**Guardrail — apply to this screen:**

*Vocabulary (use exact terms; invent nothing else):* This is a data-migration
governance console — no generic dashboard widgets (no threads, latency,
CPU/system-health, uptime, charts, or alert panels) and no data beyond what this
prompt names. Primary create action is **"Initiate project"**, never "New
Migration". Lifecycle stages (only these): ingestion, intake, planning, approval
gate, implementation, verification, review, delivery. Run statuses (only these):
queued, running, paused, completed, failed, awaiting approval. Roles:
`central_team`, `project_stakeholder`, `read_only_auditor`. Gates: Gate 1, Gate 2,
impact review, dry-run review, lookup-delta review. IDs render as realistic
monospace values like `prj_8f2a…`, `run_3c91…` (not `#MIG-####`); version refs as
pills like `v3`, `mapping@v7`. Source types: `database`, `fixed_length_file`,
`csv`, `xls`, `composite`.

*Shell lock (reuse the App Shell exactly; do not redesign it):* Use a **horizontal
top navigation — no left sidebar**. Primary top bar: the "Katana" wordmark at the
left, then horizontal nav links — Portfolio, Projects, Runs, Approvals (with an
amber "Action required" count badge), Reconciliation, and an **Admin dropdown
containing Users and Membership** — then, right-aligned, a global search field, a
notifications bell, a **role-badge chip** (e.g. `central_team`), and a profile
avatar. Directly below it, a thin **context bar**: a breadcrumb that carries project
context plus a project-switcher dropdown on the left. There is **no "New Migration"
or create button** in the nav; the role chip shows the role string, not the project
name; don't rename the brand or add unrelated tabs.

*Layout lock:* render ONLY the sections named in this prompt — nothing extra.

---

Then generate as follow-ups:
- **Paused state**: amber banner at top with a pause reason (e.g. "Awaiting human
  approval" / "Provider limit"), Resume button enabled.
- **Failed state**: red banner with the recorded failure reason.
- **Budget-exhausted state**: neutral/gray terminal banner (graceful stop, not an
  error).
