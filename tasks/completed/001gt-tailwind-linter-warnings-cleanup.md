---
id: 001gt
title: Clean up Tailwind CSS Linter Diagnostics (Narrowed Scope — Safe Fixes Only)
status: completed
created: 2026-07-25
priority: low
domain: frontend / tailwind / cleanup
depends-on: []
---

# Task 001gt — Clean up Tailwind CSS Linter Diagnostics (Narrowed Scope)

## Context

The Tailwind CSS IntelliSense linter reported several diagnostics across `ReviewGrid.tsx`, `review/page.tsx`, and `page.tsx`. This task was originally scoped to apply the linter's suggestions as-is, but a review against the actual source and app behavior found that **3 of the original 5 proposed changes are not safe, lossless lint fixes** — they'd silently change rendered behavior/layout while `npm test` stays green (nothing in this repo's test suite asserts computed color, z-index stacking, or rendered max-width). This revision narrows scope to the changes that are genuinely equivalent, and explicitly documents why the other two are excluded so a future pass doesn't reintroduce them by "helpfully" reapplying the linter's raw suggestions.

## In Scope — Requirements

1. **Fix `cssConflict` on the `lookup_fk` badge** (`web/components/projects/ReviewGrid.tsx`, `getBindingBadge`, `case "lookup_fk"`, currently line 410): the `className` has both `bg-amber-50` and `bg-amber-500/10` — a genuine duplicate/conflicting background utility (last one wins in the compiled CSS; the other is dead weight). Keep `bg-amber-50`, drop `bg-amber-500/10`. **Rationale for which one to keep**: the sibling badges in the same `switch` (`case "direct"`: `bg-slate-100 ... border-slate-200`; `case "detail_fk"`: `bg-blue-100 ... border-blue-200`) both use a solid `bg-{color}-100`-style fill, not opacity syntax — `bg-amber-50` matches that established pattern, `bg-amber-500/10` (translucent) is the outlier and was very likely the accidental duplicate. **This is a judgment call, not a mathematical certainty — confirm visually in a browser (see Verification) before treating it as done**, since neither color has an automated test asserting it.

2. **Fix `max-w-[240px]` → `max-w-60`** (`web/components/projects/ReviewGrid.tsx`, currently line 141, the `Combobox`-style component's outer `<div>`). Verified exact and lossless: Tailwind's `max-w-60` = `15rem` = `240px`. No visual change, safe as a pure rename.

## Explicitly Out of Scope — Do Not Apply These

These were in the original linter output and the original version of this task, but were found on review to be **not safe substitutions** — applying them would be a behavior/layout regression disguised as a lint cleanup:

1. **`z-[100]` → `z-50`** (`ReviewGrid.tsx`, currently line 177, the autocomplete/combobox dropdown `<ul>`). **Do not apply.** Tailwind's default `z-index` scale tops out at `z-50` — there is no built-in canonical value for `100`, so the linter's "suggestCanonicalClasses" hint is misleading here; it's suggesting the closest thing it has, not an equivalent. Elsewhere in this app, `web/app/projects/[id]/feeds/[feedId]/page.tsx:470` already uses `z-50` for a full-screen modal overlay (`fixed inset-0 z-50 ... bg-black/40`). The dropdown's `z-[100]` is deliberately higher than everything else in the app — the standard "always render above absolutely everything, including modals" pattern. Collapsing it to `z-50` would make it tie with (and risk rendering behind) that modal. `z-[100]` is the *correct* tool given no project-level z-index scale extension exists (checked `web/app/globals.css`'s `@theme` block — no custom z-index tokens defined) — leave it as-is.

2. **`max-w-[1400px]` → `max-w-7xl`** (`web/app/projects/[id]/feeds/[feedId]/review/page.tsx`, currently line 585). **Do not apply.** `max-w-7xl` = `80rem` = `1280px`, not `1400px`. This would shrink the section's max content width by 120px (-8.6%) on wide viewports — a real, visible layout change, not a no-op rename.

3. **`max-w-[1600px]` → `max-w-7xl`** (`web/app/projects/[id]/feeds/[feedId]/page.tsx`, currently line 440). **Do not apply.** Same issue, worse magnitude: 1600px → 1280px is a 320px (-20%) reduction in max content width. Checked `web/app/globals.css`'s `@theme` block — no custom `1400`/`1600` max-width tokens are defined in this project, so these arbitrary-value classes are deliberate, intentional custom sizes, not leftover cruft that happens to lack a canonical name. If narrowing/unifying these two pages' widths is ever genuinely wanted, that's a deliberate design decision requiring visual review on a wide monitor — not something to fold into a "lint cleanup" task.

## Files to Change

1. `web/components/projects/ReviewGrid.tsx` — fix the `lookup_fk` badge `cssConflict` (line 410) and the `max-w-[240px]` → `max-w-60` rename (line 141). **Do not touch line 177 (`z-[100]`)** — see Out of Scope above.
2. `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` — **no changes**. See Out of Scope above.
3. `web/app/projects/[id]/feeds/[feedId]/page.tsx` — **no changes**. See Out of Scope above.

## Verification

```bash
cd web && npm test -- --run
```

**This alone is not sufficient** — nothing in the existing test suite asserts computed background color, so it cannot confirm the badge fix is visually correct. After the automated tests pass, start the dev server and visually confirm in a browser:
- The `lookup_fk` badge on the Review page renders with the intended light-amber background (matching the visual weight of the `direct`/`detail_fk` badges next to it, just in amber) — not a jarring color shift.
- No unrelated dropdown/z-index/layout-width changes crept in (there shouldn't be any, since those items are out of scope for this task).

---
Plan: plans/2026-07-25-001gt-tailwind-linter-warnings-cleanup.md
Summary: tasks/summary/001gt-tailwind-linter-warnings-cleanup.md
