Task: tasks/completed/001gt-tailwind-linter-warnings-cleanup.md
Plan: plans/2026-07-25-001gt-tailwind-linter-warnings-cleanup.md
Commits: 1763d06

## Changes Made

### `web/components/projects/ReviewGrid.tsx`
- `lookup_fk` badge (`getBindingBadge`): removed the conflicting `bg-amber-500/10` utility, keeping `bg-amber-50` — matches the solid-fill pattern used by the sibling `direct`/`detail_fk` badges in the same `switch`.
- `AutocompleteInput`'s outer container: `max-w-[240px]` → `max-w-60` (verified exact equivalent: `max-w-60` = 15rem = 240px in Tailwind's default scale).

## Deviations from Plan

- **These two changes landed inside commit `1763d06`**, which is titled/scoped as task 001gu's commit — they were not committed separately as their own atomic change. Functionally correct and matches the plan exactly; only the commit boundary differs from what the plan implied (one commit per task).
- The three items the plan explicitly scoped *out* (`z-[100]`→`z-50`, `max-w-[1400px]`→`max-w-7xl`, `max-w-[1600px]`→`max-w-7xl`) were correctly never applied — confirmed by inspection, no trace of those changes in the committed diff or current source.
- A stray, out-of-scope `z-[100]` addition to `AutocompleteInput`'s outer `<div>` (not part of this task, not a correct fix for the dropdown-clipping issue that task 001gx addresses separately) was found uncommitted in the working tree during later housekeeping and reverted — never shipped.

## Tests

`cd web && npm test -- --run` — 337 passed, 0 failed (verified independently during later session review).
