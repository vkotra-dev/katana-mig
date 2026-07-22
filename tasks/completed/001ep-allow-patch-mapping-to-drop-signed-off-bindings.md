---
type: Task Plan
title: Allow patch_mapping to Remove a Signed-Off Binding Instead of Rejecting the Request
status: ready
---

# Task: 001ep-allow-patch-mapping-to-drop-signed-off-bindings

## Context

`patch_mapping` (`engine/src/migrations_engine/mapping/review.py:59`) currently raises a 409
(`mapping_already_approved`) whenever the new `field_bindings` array submitted by the frontend is
missing a `(source_field, destination_field)` pair that has an existing `MappingBindingSignOff`
row. This was written to stop a *rename* of a signed-off pair (old `(src, X)` -> new `(src, Y)`
shows up as pair `X` dropped + pair `Y` added — both counted as "changed"). But it also blocks a
genuine deletion — removing a binding entirely, with no replacement for that source field — which
is a real, wanted operation (this is the prerequisite for `001eq`, which adds delete controls to
the review page UI).

The frontend already independently prevents the rename case: `ReviewGrid.tsx`'s destination-field
`AutocompleteInput` is disabled (shows a lock icon instead) whenever the binding is signed off by
either role (`isSignedByEither`), so the UI can never construct a rename request for a signed pair
in the first place. This backend check is therefore pure defense-in-depth against a direct API
call, not something the UI's rename flow relies on.

## Requirements

1. Remove the 409 block entirely for a pair that disappears between the old and new
   `field_bindings` array — whether or not it was signed off, patching it away must now succeed
   (200), not fail.
2. The existing behavior of deleting the associated `MappingBindingSignOff` row(s) for a dropped
   pair must be kept — a removed binding must not leave an orphaned sign-off row behind.
3. No other `patch_mapping` behavior changes: the `mapping_not_found` (404), `mapping_not_editable`
   (422, non-draft snapshot), and `mapping_invalid_destination_field` (422) checks are all
   unaffected.
4. This does not add any new deletion capability to `field_bindings` beyond what already exists —
   `patch_mapping` already accepts a full replacement array; a caller (the frontend, in `001eq`)
   dropping an entry from that array is already how deletion works mechanically. This task only
   removes the guard that currently rejects doing so when the dropped entry was signed off.

## Out of Scope

- No frontend changes — this task is `engine/` only. `001eq` (frontend delete UI) depends on this
  landing first, but is a separate task/commit.
- No change to the rename case's behavior when the *replacement* destination field itself is
  already signed off under a different pair (e.g. re-pointing `(src, X)` to `(src, Y)` where `Y` is
  already signed off by a *different* source field) — not affected by or related to this change.
- No change to `propose_mapping`'s own signed-off-preservation logic (`001el`) — unrelated code
  path.

## Dependencies
None. Should land before `001eq`.
