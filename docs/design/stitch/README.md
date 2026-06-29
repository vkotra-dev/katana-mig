# Katana — Stitch prompt pack

Per-screen prompts for generating the Katana migration-console UI in **Google
Stitch**. Each screen file is **self-contained** (the style block is already
prepended), so you can copy-paste one file straight into Stitch.

Master reference (full rationale, all states, domain detail):
[`../ui-design-prompt.md`](../ui-design-prompt.md).

## How to use with Stitch

1. Set the project to **Web / desktop** (this is a dense console, not mobile).
2. Generate **`01-global-shell.md` first.** Get the nav + top bar + role badge
   looking right, then design every other screen to live inside that shell.
3. **Stay in the same Stitch project** for all screens — Stitch keeps a per-project
   theme, so they inherit the shell's colors/fonts automatically. See
   `design-tokens.md` (the design system the shell produced); only re-paste it if a
   screen comes back off-theme.
4. **The guardrail is already baked into every screen file** (vocabulary + shell-lock
   + layout-lock) — just paste the whole file. `vocabulary.md` is kept as the
   standalone source if you ever need to re-send it on its own. The guardrail is what
   stops Stitch inventing generic-SaaS content/terms ("New Migration", "Active
   Threads", `#MIG-####`, "PENDING") and redrawing the shell each screen.
5. Then work down the list in order. Each file is one screen/flow.
6. Stitch generates the **main screen** per prompt. The "Then generate as
   follow-ups" list at the bottom of each file tells you what to ask for next
   (empty / error / paused / permission states, dark mode) in the same session.
7. If output drifts visually, re-paste `design-tokens.md` and say "match this theme."

## Generation order & screen-name mapping

Each prompt declares a **`Screen name:`** line near the top — paste it into Stitch
and use that as the screen/frame title so each file maps 1:1 to a named screen.
Stitch may auto-name on generation; if so, rename the canvas frame to match.

| # | File | Screen name(s) | Tier |
|---|------|----------------|------|
| 1 | `01-global-shell.md` | `App Shell` | foundation — do first |
| 2 | `02-portfolio-dashboard.md` | `Portfolio Dashboard` | full |
| 3 | `03-launch-run.md` | `Launch Run` | full — key screen |
| 4 | `04-run-detail.md` | `Run Detail` | full — key screen |
| 5 | `05-runs-list.md` | `Runs` | medium |
| 6 | `06-project-detail.md` | `Project Detail` | medium |
| 7 | `07-project-initiation.md` | `Project Initiation` | full — wizard |
| 8 | `08-gate1-review.md` | `Gate 1 Review` | medium |
| 9 | `09-gate2-review.md` | `Gate 2 Review` | full |
| 10 | `10-other-review-gates.md` | `Impact Review`, `Dry-run Review`, `Lookup-delta Review` | three screens |
| 11 | `11-reconciliation-lineage.md` | `Reconciliation & Lineage` | full |
| 12 | `12-auth-screens.md` | `Login`, `First-run Bootstrap`, `Change Password` | three screens |
| 13 | `13-admin-users.md` | `Admin · Users` | medium |
| 14 | `14-membership.md` | `Project Membership` | short |
| 15 | `15-notifications.md` | `Notifications`, `Notifications Bell` | short |

`00-style-header.md` is the shared style block, already embedded at the top of
every file above — keep it as a standalone copy for re-grounding mid-session.
