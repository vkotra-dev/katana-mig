**Style — data-dense enterprise operations console** (web / desktop; reference feel: Linear, Datadog, Retool). Light mode primary. Neutral gray canvas, a single indigo accent used only for primary actions and active nav. Reserve color for **status**: green = healthy / approved / complete, amber = action-required / paused / awaiting approval, red = failed / blocked / rejected, blue = in-progress / running, gray = idle / queued / archived. Compact tables (~38px rows) with sticky sortable headers, status chips, role badges, filter bars. Sans (Inter) for text; **monospace** (JetBrains Mono) for all IDs, version refs, and timestamps — each shown with a copy icon. Tight but legible spacing. This is an internal, audit-first operations tool, not a marketing site.

---

**Screen names:** `Notifications` (full page) and `Notifications Bell` (dropdown) —
use these exact names as the screen/frame titles.

Design the **Notifications** surface for Katana. Generate two views.

**A. Bell dropdown** (from the top bar): a compact list of recent notifications, each
with an icon, a short label, a project/run reference, and a timestamp; unread items
emphasized; a "Mark all read" action and a "View all" link.

**B. Notifications page** (full screen inside the shell): a filterable, grouped list
(by project / by date) with mark-read controls.

Notification types, each with an icon and a deep link to the relevant
project / artifact / run: Gate 1 waiting, Gate 2 waiting, impact review waiting,
dry-run waiting, **lookup delta discovered**, **reconciliation failed**, knowledge-
freeze published, **execution complete**. Style "action required" types in amber and
pin them; style "reconciliation failed" in red.

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
- **Empty state**: "You're all caught up."
- **Unread-only** filtered view.
