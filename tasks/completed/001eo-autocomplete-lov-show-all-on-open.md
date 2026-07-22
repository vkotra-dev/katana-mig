---
type: Task Plan
title: Fix AutocompleteInput to Show All Destination Fields When Opened
status: completed
---

# Task: 001eo-autocomplete-lov-show-all-on-open

## Context

On the review page (`web/app/projects/[id]/feeds/[feedId]/review/page.tsx`, rendered via
`ReviewGrid.tsx`), the destination-field picker for a binding is an `AutocompleteInput` (defined
locally inside `ReviewGrid.tsx`, not exported, not used anywhere else — this fix cannot affect the
feed detail page or any other screen).

Confirmed root cause: `AutocompleteInput`'s `query` state is initialized to the current `value`
(the already-mapped destination field). `filteredOptions` immediately substring-filters `options`
by `query` whenever `query` is non-empty. Since `query` starts out equal to the current value, the
dropdown shows only options whose name happens to contain that value as a substring — in practice
just the current value itself — the moment it's opened, before the user types anything. Confirmed
against live data: the backend already sends the full destination field list (e.g. `policy_master`
has 42 total destination fields vs. 38 mapped ones) — this is a frontend filtering bug, not a data
or backend problem.

## Requirements

1. Opening the dropdown (via focus or the toggle arrow) before typing anything must show **all**
   options passed in via the `options` prop — not just the current value.
2. Typing must still narrow the list by substring match, exactly as today, once the user has
   actually typed something.
3. Selecting an option, or blurring without selecting, must behave exactly as today (`onChange`
   fires with the current text on blur; selecting an option calls `onChange` with that option and
   closes the dropdown).
4. No change to any other component. `AutocompleteInput` is local to `ReviewGrid.tsx` — this task
   touches only that file (and its test file).

## Out of Scope

- No change to the feed detail page (`web/app/projects/[id]/feeds/[feedId]/page.tsx`) or any other
  screen — `AutocompleteInput` isn't used there.
- No change to `table.destinationFields`/the backend data feeding this component — confirmed
  already correct.
- No visual/styling changes beyond what's needed for the fix.

## Dependencies
None.
