# Katana — domain vocabulary guardrail

Append this block to **every** screen prompt. It stops Stitch from inventing
generic-SaaS content/terms (e.g. "New Migration", "Active Threads", "Queue
Latency", `#MIG-9042`, "PENDING"). Use the exact terms below.

---

**Domain vocabulary — use these exact terms; do not invent metrics, IDs, or labels:**

- This is a **data-migration governance console**. Do **not** add generic dashboard
  widgets (no "threads", "latency", "CPU/system health", "uptime", marketing stats).
  Only show data described in the prompt.
- **Primary create action** is **"Initiate project"** — never "New Migration".
- **Project lifecycle stages** (the only stage names): ingestion, intake, planning,
  approval gate, implementation, verification, review, delivery.
- **Run statuses** (the only run-status chips): queued, running, paused, completed,
  failed, awaiting approval.
- **Roles** (exact strings): `central_team`, `project_stakeholder`,
  `read_only_auditor`.
- **Approval gates** (exact names): Gate 1, Gate 2, impact review, dry-run review,
  lookup-delta review.
- **IDs** are `project_id`, `run_id`, `artifact_id` — render realistic values like
  `prj_8f2a…`, `run_3c91…` in JetBrains Mono, not `#MIG-####`.
- **Version refs** (source slice, mapping, lookup, codegen input, knowledge-freeze)
  render as monospace version pills like `v3`, `mapping@v7`.
- Source types: `database`, `fixed_length_file`, `csv`, `xls`, `composite`.
- Reconciliation produces lineage (source row ↔ destination row), not "logs".

**Shell lock — reuse the App Shell exactly; do not redesign it:**
- **Sidebar** items, in order: Portfolio, Projects, Runs, Approvals (with an amber
  "Action required" badge), Reconciliation, then an **Admin group with TWO items:
  Users and Membership**. Brand mark is "Katana". There is **NO "New Migration"
  button** and no create button anywhere in the sidebar.
- **Top bar**: breadcrumb (carries project context) + project-switcher dropdown +
  global search + notifications bell + a **role-badge chip** showing the role string
  (e.g. `central_team`) + profile avatar. Do **NOT** add a secondary tab row
  (no "Environment"/"Security" tabs). Do not rename the brand or add a version tag.

**Layout lock — render ONLY the sections named in the prompt:**
- Do not add charts, velocity/distribution graphs, "system alerts", health meters,
  or any extra panels beyond what the screen prompt lists. If the prompt says
  header + filter bar + summary strip + table, the page is exactly those, nothing more.

---
