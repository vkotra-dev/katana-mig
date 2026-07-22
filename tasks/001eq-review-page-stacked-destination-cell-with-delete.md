---
type: Task Plan
title: Review Page — Stacked Destination-Field Cell with Add/Remove Controls
status: ready
---

# Task: 001eq-review-page-stacked-destination-cell-with-delete

## Context

The review page (`web/app/projects/[id]/feeds/[feedId]/review/page.tsx`, via `ReviewGrid.tsx`)
already supports mapping one source field to more than one destination field: an "Add" flow
(`onAddBinding`, `handleAddBinding`) exists and is tested. Today, each `(source, destination)`
binding renders as its own full table `<tr>`, so a 1-to-N source field shows as multiple separate
rows repeating the same source field name.

This task changes the layout so all bindings sharing one source field render inside a single row,
with their destination fields **stacked inside one cell** — matching the actual product request:
a `+` inside the destination-field cell to add another row within that same cell, and per-entry
delete controls, with two distinct scopes:

1. **Per-destination-entry delete** (`×` next to each stacked destination-field input, hidden on
   the first/original entry) — removes just that one extra mapping, leaves the rest of the group
   intact.
2. **Whole-source-field delete** (`×` next to the source field name itself) — removes *all*
   bindings for that source field in one action, dropping it from migration entirely (it then
   surfaces in the existing "Unmapped source fields" warning box). Available even when the source
   field has only one destination (not just for 1-to-N groups).

This depends on `001ep` (backend) landing first — deleting a signed-off binding must not 409.

## Requirements

1. Group `table.bindings` by `sourceField` for rendering. One `<tr>` per group, not per binding.
2. Destination Field cell: a vertical stack, one entry per binding in the group (same
   `AutocompleteInput`/locked-display pattern as today, unchanged per-entry), each with an inline
   `×` to its right — visible only when `editingEnabled && entryIndex > 0`. Below the stack, the
   existing "Map to another destination" control (today's `onAddBinding` button) becomes the
   trailing element of this same cell.
3. Type and Sign-offs cells: also become vertical stacks, one entry per binding in the group,
   aligned with the destination-field stack (same order).
4. Source Field cell: adds an inline `×` next to the source field name (kept alongside the existing
   "1-to-N" badge), visible whenever `editingEnabled`, regardless of group size. Clicking it removes
   every binding for that source field.
5. Neither delete control is gated on sign-off status — per `001ep`, the backend now allows
   removing a signed-off binding; the frontend must not add its own blocking check here that
   contradicts that.
6. The "Map to another destination" control's visibility is governed only by `editingEnabled` and
   whether any destination fields remain unmapped for that table — not by whether any existing
   entry in the group is signed off (today's code accidentally checks the signed status of
   whichever single binding row it happens to be attached to; group-level rendering removes that
   inconsistency, since adding a new entry doesn't touch any existing signed entry).
7. New `onRemoveBinding`/`onRemoveSourceField` handlers in `review/page.tsx`, following the exact
   same optimistic-update-then-PATCH shape as the existing `handleAddBinding` — including building
   the PATCH payload directly from the pre-update `targetSnapshot` closure (not from a fresh state
   read), matching the pattern already fixed and verified correct in that function.

## Out of Scope

- The feed detail page (`web/app/projects/[id]/feeds/[feedId]/page.tsx`) — untouched, does not use
  `ReviewGrid`.
- `001eo` (the `AutocompleteInput` LOV-filtering fix) — a separate, independent task; this task's
  plan assumes it may or may not have landed yet and doesn't depend on it either way, since it
  touches a different part of the same component.
- No change to the Lookup Value Mapping section of `ReviewGrid.tsx` (the second, separate table)
  — this task only touches the Table Mappings section.
- No confirmation dialog before delete — per the earlier design discussion, both delete controls
  act immediately on click, no "are you sure."

## Dependencies

Depends on `001ep` landing first — deleting a signed-off binding must succeed on the backend before
this task's delete controls can work end-to-end. Independent of `001eo`.
