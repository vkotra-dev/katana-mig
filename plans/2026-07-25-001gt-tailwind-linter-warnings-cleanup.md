# Plan: Task 001gt — Clean up Tailwind CSS Linter Diagnostics (Narrowed Scope)

- **Task**: [001gt-tailwind-linter-warnings-cleanup.md](file:///Users/vjkotra/projects/katana/tasks/001gt-tailwind-linter-warnings-cleanup.md)

---

## Goal Description

Fix the two Tailwind diagnostics in `ReviewGrid.tsx` that are genuinely safe, lossless fixes: a real `cssConflict` (duplicate background utility) and an exact-equivalent arbitrary-value-to-scale rename.

**This plan deliberately does NOT apply 3 of the original 5 linter suggestions.** They were checked against the actual rendered app and found to be lossy or behavior-changing, not equivalent renames — applying them would pass `npm test` while shipping a real regression (see the task file's "Explicitly Out of Scope" section for the full reasoning on each). If you are an agent executing this plan and are tempted to "also fix" `z-[100]` in `ReviewGrid.tsx` or either `max-w-[1400px]`/`max-w-[1600px]` in the two `page.tsx` files because your own linter flags them too: **do not**. Re-read the task file's Out of Scope section first — those are intentional exclusions, not oversights.

---

## Step-by-Step Build Instructions (Agent Executable)

### Step 1: Fix the `cssConflict` on the `lookup_fk` badge

**File**: [web/components/projects/ReviewGrid.tsx](file:///Users/vjkotra/projects/katana/web/components/projects/ReviewGrid.tsx)

Find `getBindingBadge`, `case "lookup_fk":` (search for `lookup_fk` — do not rely on a line number, search the string `bg-amber-50` to anchor exactly, since it's unique in the file):

```diff
       case "lookup_fk":
         return (
-          <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 border border-amber-200/55 bg-amber-500/10">
+          <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 border border-amber-200/55">
             lookup_fk
           </span>
         );
```

Only `bg-amber-500/10` is removed. `bg-amber-50` stays — it matches the solid-fill pattern the sibling `direct`/`detail_fk` badges already use two cases above this one in the same `switch` statement.

---

### Step 2: Rename `max-w-[240px]` to `max-w-60`

**File**: [web/components/projects/ReviewGrid.tsx](file:///Users/vjkotra/projects/katana/web/components/projects/ReviewGrid.tsx)

Search for `max-w-[240px]` (unique string in the file, in the combobox component's outer `<div>`):

```diff
-    <div ref={containerRef} className="relative w-full max-w-[240px]">
+    <div ref={containerRef} className="relative w-full max-w-60">
```

Verified lossless: `max-w-60` = `15rem` = `240px` exactly, in Tailwind's default (unmodified in this project) spacing scale.

---

### Step 3 — explicitly skipped, do not do this

The original version of this plan had a step here changing `z-[100]` → `z-50` on `ReviewGrid.tsx`'s dropdown `<ul>`. **Do not make this change.** `z-50` is already used elsewhere in this app (`web/app/projects/[id]/feeds/[feedId]/page.tsx:470`) for a full-screen modal overlay; the dropdown's `z-[100]` is intentionally set higher so it always renders above everything, including that modal. There is no built-in Tailwind scale value above `z-50` and this project defines no custom one (checked `web/app/globals.css`'s `@theme` block). Leave line 177 of `ReviewGrid.tsx` untouched.

---

### Step 4 — explicitly skipped, do not do this

The original version of this plan had steps here changing `max-w-[1400px]` → `max-w-7xl` (`review/page.tsx`) and `max-w-[1600px]` → `max-w-7xl` (`page.tsx`). **Do not make either change.** `max-w-7xl` is `1280px`, not `1400px` or `1600px` — these are not equivalent renames, they're a real reduction in max content width (-120px and -320px respectively). Neither file has any custom `maxWidth` theme token defined for `1400`/`1600` (checked `web/app/globals.css`). Leave both files untouched — do not modify `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` or `web/app/projects/[id]/feeds/[feedId]/page.tsx` at all for this task.

---

### Step 5: Automated verification

```bash
cd web && npm test -- --run
```

Must pass with no new failures. This is a necessary but not sufficient check — see Step 6.

---

### Step 6: Manual visual verification (required — do not skip)

Nothing in the automated test suite asserts computed background color. Start the dev server (`npm run dev` in `web/`), navigate to a Review page with at least one `lookup_fk`-type field binding, and visually confirm:

- The `lookup_fk` badge renders with a light amber background consistent with the `direct` (slate) and `detail_fk` (blue) badges' visual weight next to it — not a stark or jarring color.
- Nothing else on the page looks different (no dropdown positioning issues, no width changes) — there shouldn't be, since Steps 3 and 4 were skipped, but confirm this is actually true rather than assuming it.

---

## Verification Plan

```bash
cd web && npm test -- --run
```

Plus the manual visual check in Step 6 — required for this task specifically because the only in-scope change (Step 1) is a pure-CSS color fix that no automated test in this repo can verify. Do not report this task complete based on `npm test` passing alone.
