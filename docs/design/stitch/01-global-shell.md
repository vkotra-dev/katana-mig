**Style — data-dense enterprise operations console** (web / desktop; reference feel: Linear, Datadog, Retool). Light mode primary. Neutral gray canvas, a single indigo accent used only for primary actions and active nav. Reserve color for **status**: green = healthy / approved / complete, amber = action-required / paused / awaiting approval, red = failed / blocked / rejected, blue = in-progress / running, gray = idle / queued / archived. Compact tables (~38px rows) with sticky sortable headers, status chips, role badges, filter bars. Sans (Inter) for text; **monospace** (JetBrains Mono) for all IDs, version refs, and timestamps — each shown with a copy icon. Tight but legible spacing. This is an internal, audit-first operations tool, not a marketing site.

---

**Screen name:** `App Shell` — use this exact name as the screen/frame title.

Design the **global app shell** for Katana, an internal data-migration operations
console. This shell wraps every screen — design it first so all other screens sit
inside it. Use a **horizontal top navigation — there is no left sidebar.**

**Primary top bar** (sticky, full width): the "Katana" wordmark at the far left,
then a row of horizontal nav links (icon + label): Portfolio, Projects, Runs,
Approvals (with an amber count badge labelled "Action required"), Reconciliation,
and an **Admin dropdown** that opens to Users and Membership. The active link uses
the indigo accent (colored text + a 2px underline). Right-aligned: a global search
field (search projects/runs by id or name), a **notifications bell** with an unread
count, a **role-badge chip** (e.g. `central_team`), and a user-menu avatar
(Profile, Change password, Sign out).

**Context bar** (a thin row directly beneath the primary top bar): on the left, a
breadcrumb that carries project context (e.g. `Portfolio / Acme Core Migration`)
plus a **project-switcher** dropdown; the right side is reserved for page-level
actions on inner screens.

**Main content area:** an empty placeholder with a page-title slot. No dashboard
content, charts, tables, or alert panels.

---

**Guardrail — apply to this screen:**

*Vocabulary (use exact terms; invent nothing else):* This is a data-migration
governance console. Brand is "Katana". Roles: `central_team`,
`project_stakeholder`, `read_only_auditor`. Do not invent generic widgets, charts,
metrics, or alert panels.

*This screen defines the canonical shell* (top nav + context bar) that every other
screen reuses. Horizontal top nav only — no left sidebar. The role chip shows the
role string (e.g. `central_team`), never the project name. There is **no "New
Migration" or create button** in the nav.

---

Then generate as follow-ups:
- The **role badge** in three variants: `central_team`, `project_stakeholder`,
  `read_only_auditor` (show how the Admin dropdown is hidden for the latter two).
- A **dark-mode** variant of the shell.
- The **Admin dropdown open**, showing Users and Membership.
