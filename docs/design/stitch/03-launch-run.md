**Style — data-dense enterprise operations console** (web / desktop; reference feel: Linear, Datadog, Retool). Light mode primary. Neutral gray canvas, a single indigo accent used only for primary actions and active nav. Reserve color for **status**: green = healthy / approved / complete, amber = action-required / paused / awaiting approval, red = failed / blocked / rejected, blue = in-progress / running, gray = idle / queued / archived. Compact tables (~38px rows) with sticky sortable headers, status chips, role badges, filter bars. Sans (Inter) for text; **monospace** (JetBrains Mono) for all IDs, version refs, and timestamps — each shown with a copy icon. Tight but legible spacing. This is an internal, audit-first operations tool, not a marketing site.

---

**Screen name:** `Launch Run` — use this exact name as the screen/frame title.

Design the **Launch Run** flow for Katana — a manual, preflight-gated launcher for
starting a migration run. Present it as a **multi-step modal/wizard** over the app
shell. A run targets exactly **one destination object** in **one environment**.

**Step 1 — Target:** select **Project** (dropdown, scoped to what the user may
access) → **Destination object** (single-select) → **Environment** (single-select).
A hint reads: "Multi-environment work creates separate runs in declared order."

**Step 2 — Snapshot set (auto-pinned, read-only):** a key-value panel showing the
**latest approved** versions that will be pinned to the run, each as a copyable
monospace **version pill**: source slice version, mapping snapshot version, lookup
snapshot version, codegen-input version, knowledge-freeze version. Caption:
"These versions are pinned to the run and reused on resume."

**Step 3 — Preflight checks (blocking):** a checklist with green-check / red-X rows;
the **Launch** button stays disabled until all pass:
- Frozen project definition present
- Required source slice approved & present
- Required downstream snapshots approved
- Object not already running for this environment
Each failed row shows a reason + a "Resolve" link.

**Step 4 — Confirm & launch:** read-only summary, primary **Launch run** button.

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
- **Failed-preflight state**: one or more red-X rows, Launch disabled, resolve links.
- **Success state**: "Run queued" confirmation with the new monospace `run_id` and a
  "View run" button.
- **Error state**: lease/queue failed, with retry.
