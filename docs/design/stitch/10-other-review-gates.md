**Style — data-dense enterprise operations console** (web / desktop; reference feel: Linear, Datadog, Retool). Light mode primary. Neutral gray canvas, a single indigo accent used only for primary actions and active nav. Reserve color for **status**: green = healthy / approved / complete, amber = action-required / paused / awaiting approval, red = failed / blocked / rejected, blue = in-progress / running, gray = idle / queued / archived. Compact tables (~38px rows) with sticky sortable headers, status chips, role badges, filter bars. Sans (Inter) for text; **monospace** (JetBrains Mono) for all IDs, version refs, and timestamps — each shown with a copy icon. Tight but legible spacing. This is an internal, audit-first operations tool, not a marketing site.

---

**Screen names:** `Impact Review` (A), `Dry-run Review` (B), `Lookup-delta Review` (C)
— use these exact names as the screen/frame titles, one per generated screen.

Design **three related review screens** for Katana. All share the same two-pane
pattern: evidence on the left, an approve / push-back decision panel on the right.
Generate each as its own screen.

**A. Impact Review (admin)** — shown after a push-back produces an impact report.
Left panel shows: the pushback comment, the structured target fields, **affected
objects** (table), **replay scope**, and a recommendation. Right: Approve / Push back.

**B. Dry-run Review (admin)** — shown when dry run is enabled. Left panel shows one
**dry-run artifact per domain object**: sample rows with annotations, a target-object
summary, and a **PII masking status** badge per field. Right: Approve / Push back.

**C. Lookup-delta Review (stakeholder)** — shown when execution discovers a new lookup
value. Left panel shows: the discovering **environment**, the **source column + exact
value** (monospace), the **AI-proposed mapping**, and a **confidence score** rendered
as a small meter. Right: Accept / Override / Reject — resolving resumes the blocked run.

---

**Guardrail — apply to these screens:**

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
- For each: the **submitting / success** state.
- For Lookup-delta: the **override editor** open.
