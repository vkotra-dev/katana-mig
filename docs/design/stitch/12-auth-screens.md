**Style — data-dense enterprise operations console** (web / desktop; reference feel: Linear, Datadog, Retool). Light mode primary. Neutral gray canvas, a single indigo accent used only for primary actions and active nav. Reserve color for **status**: green = healthy / approved / complete, amber = action-required / paused / awaiting approval, red = failed / blocked / rejected, blue = in-progress / running, gray = idle / queued / archived. Compact tables (~38px rows) with sticky sortable headers, status chips, role badges, filter bars. Sans (Inter) for text; **monospace** (JetBrains Mono) for all IDs, version refs, and timestamps — each shown with a copy icon. Tight but legible spacing. This is an internal, audit-first operations tool, not a marketing site.

---

**Screen names:** `Login` (A), `First-run Bootstrap` (B), `Change Password` (C) —
use these exact names as the screen/frame titles, one per generated screen.

Design **three auth screens** for Katana. Generate each as its own screen. These are
the only screens without the app shell — centered card on a neutral canvas.

**A. Login** — centered card, product mark "Katana" with subtitle "Migration
operations console". Fields: email, password, and a "Sign in" primary button. Small
footer: "Accounts are provisioned by your central team." No public sign-up.

**B. First-run bootstrap** — "Set up the first administrator" card: email, display
name, password, confirm password, and a "Create administrator" button. One-time setup.

**C. Change password** — a focused card/drawer: current password, new password,
confirm. Note: "This cannot change your role." Submit button.

---

**Guardrail — apply to these screens:**

*Vocabulary (use exact terms; invent nothing else):* This is a data-migration
governance console. Brand is "Katana", subtitle "Migration operations console".
Roles: `central_team`, `project_stakeholder`, `read_only_auditor`. No public
sign-up, no social-login buttons, no marketing copy or imagery.

*Layout lock:* these are the only screens **without** the app shell — a centered
card on a neutral canvas, nothing else. Render ONLY the fields named in this
prompt; do not add extra panels, charts, or illustrations.

---

Then generate as follow-ups:
- Login **error state** ("Invalid email or password").
- Login **disabled-account state** ("This account has been disabled. Contact your
  administrator.").
- Login **session-expired** return banner.
- Change-password **wrong-current-password** error and **success** states.
