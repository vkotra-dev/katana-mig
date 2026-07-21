---
type: Task Plan
title: Patch Field Mapping In Place on Re-Analyze — Preserve Signed-Off Bindings
status: ready
---

# Task: 001el-preserve-signed-off-bindings-on-reanalyze

## Context
Re-supersedes a prior attempt at this requirement (`001df-ai-reanalysis-preservation`) that did
not actually implement it. Confirmed by reading `mapping/proposal.py::propose_mapping` directly:
its only skip condition (`proposal.py:60-86,215`) is `MappingSnapshot.status == "approved"` — a
table with an existing `draft` snapshot (mid-review, possibly with partial sign-offs) doesn't
match, so re-running "AI Analyze" creates a **brand new `MappingSnapshot` row** with a **new
`mapping_snapshot_id`** (`proposal.py:243-262`), built entirely from the fresh AI response. No
code anywhere reads the previous draft's `field_bindings` or checks
`MappingBindingSignOff` before doing this.

The consequence is worse than "doesn't preserve individual field edits": since
`MappingBindingSignOff` rows are keyed by `mapping_snapshot_id` (`db/models.py`), and the new
snapshot gets a new ID, **every sign-off recorded against the previous version becomes orphaned**
— `get_sign_off_status` (`management/sign_offs.py`) only ever looks at the latest snapshot per
table, so the new version starts review from zero regardless of what was already approved.
Confirmed live in the dev DB: `policy_master`/`policy_claims` each have a `v1` and `v2` `draft`
row, completely disconnected, no shared sign-off state.

## Requirements

1. **When `propose_mapping` re-analyzes a table that already has a `draft` snapshot**, it must
   **patch that existing snapshot's `field_bindings` in place** — not create a new
   `MappingSnapshot` row/version. (A table with an `approved` snapshot keeps its current
   skip-entirely behavior, unchanged.)
2. **Merge logic, per `(source_field, destination_field)` pair** (matching `001dy`'s pair-keyed
   convention, not the old source-field-only keying):
   - Look up existing `MappingBindingSignOff` rows for the current draft snapshot.
   - For any binding pair that has **at least one** sign-off recorded (central_team **or**
     project_stakeholder — "even if we have sign-off from one, don't update that field"), keep
     the existing binding's value — but see the key-level overlay rule below; "keep" means keep
     the *known* fields, not necessarily reject 100% of the fresh data.
   - For any binding pair with **no** sign-off at all, replace it with the fresh AI-proposed
     value.
   - A pair present in the new AI proposal but not in the old bindings (a genuinely new mapping)
     gets added.
   - Decide explicitly (don't assume silently) what happens to an old, unsigned binding that the
     new AI proposal no longer mentions at all — drop it, or keep it until an operator manually
     removes it. State the choice in the plan.
   - **Forward-compatible key-level overlay, not whole-dict freeze**: for a signed-off pair,
     don't just keep the old dict untouched — merge as
     `merged = {**fresh_binding.model_dump(), **old_binding}` (old wins on any key both dicts
     have, fresh wins on any key *only* it has). This means if the `Binding` schema grows a new
     field later (e.g. an auto-generated-ID detector), an already-signed-off pair still gets that
     new field populated from the AI's current output — the old stored dict simply doesn't have
     that key, so there's nothing for it to "protect," and the core reviewed fields
     (`source_field`, `destination_field`, `binding_type`, etc.) still can't be silently changed
     since `old_binding` overwrites them. Deliberately simple: no `MappingBindingSignOff` schema
     change, no tracking of "which fields were part of the original review" — a missing key in
     the old dict is itself sufficient signal that it wasn't reviewed yet.
3. **No new `mapping_snapshot_version` on re-analyze of a draft** — since the same row is
   patched, not superseded. `mapping_snapshot_version` continues to increment only when a fresh
   snapshot is created for a table with no existing draft (the current behavior for a genuinely
   new proposal is unaffected).
4. **Sign-off state itself is untouched** — this task only changes which *values* survive
   re-analysis; it doesn't invalidate or re-trigger sign-offs for fields that were already signed
   off (they stay signed off, since their value didn't change). Existing `patch_mapping` logic
   already invalidates sign-offs when an *operator* changes a field manually — confirm this new
   AI-driven patch path doesn't need the same invalidation, since by construction it never
   changes an already-signed-off field.
5. **This must supersede/replace whatever `001df` shipped**, not sit alongside it — investigate
   what `001df`'s commit actually touched (`git log --oneline | grep -i 001df`) before writing
   the implementation, to understand exactly what to remove/replace versus what (if anything) was
   salvageable.
6. **One-time cleanup of existing damage from the bug**: confirmed live — 2 `(project, feed,
   table)` groups currently have simultaneous duplicate `draft` `MappingSnapshot` rows
   (`policy_master`, `policy_claims`, both same feed), both with zero sign-offs on any of the 4
   affected rows in this environment. The fix must include a one-time reconciliation (script or
   migration, run once) that, for every such group: picks the latest draft as authoritative,
   re-associates any `MappingBindingSignOff` rows from older drafts onto it for pairs whose value
   still matches (reusing the same merge logic from requirement 2 — don't write a second, separate
   version of it), and marks the older, now-redundant draft(s) with a new status
   (`"superseded"`, not deletion — matches this codebase's don't-mutate-history convention) so
   they stop appearing in `status == "draft"` queries. Zero sign-offs in the current dev DB means
   this specific data's cleanup is simple, but the logic must handle the general case (sign-offs
   present) since other environments may differ.
7. **Bulk dedup risk**: `unapprove_mapping`'s bulk path (`review.py`) selects all `status ==
   "draft"` rows for a feed and dedups by `destination_object_name` in iteration order, with no
   explicit "pick the latest" ordering guarantee once duplicates exist — a second, independent
   reason (beyond orphaned sign-offs) the duplicates need cleaning up, not just left alone as
   harmless clutter.

## Out of Scope
- Any change to `patch_mapping` (the operator-edit path) — unaffected, already correctly
  invalidates sign-offs on a real value change.
- Bulk/multi-table re-analysis semantics beyond what's already there — this only changes how a
  single already-drafted table's bindings get merged, not the overall multi-table proposal flow.
- The `feed_analysis`/`lookup_mapping` re-analysis paths in `fibers.py` — task title/scope is
  specifically the `mapping.yaml`/`propose_mapping` flow the user described ("every time AI does
  mapping analyze"); if the same gap exists in `fibers.py`'s per-fiber field-mapping re-run, treat
  that as a separate, follow-up task, not silently bundled in here.

## Dependencies
None, but should land after confirming exactly what `001df` did (requirement 5) so this doesn't
duplicate or conflict with dead code from that attempt.
