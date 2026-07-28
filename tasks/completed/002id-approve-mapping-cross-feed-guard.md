---
id: 002id
title: Block approving a table mapping when another feed already owns it
status: completed
created: 2026-07-28
priority: high
depends-on: []
domain: engine
task: tasks/002id-approve-mapping-cross-feed-guard.md
plan: plans/2026-07-28-002id-approve-mapping-cross-feed-guard.md
---

# Task 002id — `approve_mapping()`: reject cross-feed table-mapping conflicts

## Context

Mappings are project-scoped (`MappingSnapshot.source_definition_id` is nullable) so that a lookup
or table mapping *can* be shared project-wide. That sharing is genuinely wanted for lookups
(`LookupValueMap`/`LookupSnapshot` have no `source_definition_id` at all — they're inherently
project+`lookup_name` scoped, nothing to fix there). It is **not** wanted for table mappings: if
two different feeds each get their own independently-approved `MappingSnapshot` for the same
`destination_object_name`, `generate_codegen_artifact()` (invoked separately per feed, via each
feed's own "Generate SQL" click) will produce **two separate stored procedures**, each
independently upserting into the same destination table — duplicate migration of the same data,
not just a UI nuisance.

This is a real, reachable state today, not hypothetical. Traced the full path:

- `propose_mapping()`'s `already_mapped_tables`/`project_approved` check (`proposal.py:51-77`)
  only blocks *proposing a new* snapshot over a table that already has an *approved* snapshot
  somewhere in the project. It does nothing to stop two feeds from independently drafting the
  same table **before either is approved**.
- `approve_mapping()` (`mapping/review.py:156-276`) has **no cross-feed check at all** — it only
  validates sign-off completeness for the current feed's own drafts (`review.py:202-221`) and
  flips them to `approved` (`review.py:225-238`).
- So: Feed A and Feed B both draft "Customer" (allowed — no approved row exists yet for either to
  conflict with). Feed A gets approved. Feed B's own draft is untouched and still approvable —
  nothing stops its owner from later calling approve on it too, producing a second, independently
  approved "Customer" `MappingSnapshot` scoped to Feed B.
- Codegen's own snapshot-resolution query (`_select_latest_approved_mapping_snapshot`,
  `codegen/service.py:427-457`) prefers the calling feed's own row (priority 0) over a
  project-scoped one (priority 1) — so Feed A's "Generate SQL" click uses Feed A's row, and Feed
  B's separate "Generate SQL" click uses Feed B's row. Two independent, successful codegen runs
  for the same destination table.

An earlier draft of this task proposed detecting this after the fact (a new
`mapping_status: "unusable"` value, hidden from the codegen sources list, a banner on the feed
page). That was rejected in favor of prevention: `propose_mapping()` already has the pattern for
this exact problem (block the action, don't just flag the result) — `approve_mapping()` should
have the same guard, closing the race instead of surfacing it after two people have already done
conflicting work. **This task replaces that draft entirely** — no `mapping_status` enum change, no
frontend filtering, no "unusable" banner.

## Domain Updates Required

- `docs/domain/source-model.md` — the mapping-approval flow description (if any) should note that
  approval is now guarded against cross-feed table-mapping conflicts. Read the current page before
  writing — if the approval flow isn't documented in enough detail for this to be a meaningful
  addition, note explicitly why not, don't force an edit.

## Objective

In `approve_mapping()` (`mapping/review.py`), before flipping each draft's status to `approved`,
reject the approval if any *other* feed (a different `source_definition_id`, or a project-scoped
`NULL`-scoped row) already has an `approved` `MappingSnapshot` for that same
`destination_object_name` in the project. Reuse the exact `outerjoin(Feed, ...)` /
`Feed.status != "discarded"` pattern already established in `proposal.py:63-77` for consistency —
don't invent a second way to compute "approved anywhere in the project." Populate the 409's
`detail` dict with the conflicting feed's `source_definition_id` and `mapping_snapshot_id` — the
frontend's `MappingApiError.detail` (`web/lib/mapping-api.ts:43-54`) already supports this, unused
today.

**Review-page impact (traced, not assumed):** the review page's `handleApprove`
(`review/page.tsx:128-139`) already surfaces `err.message` in a visible banner — this conflict will
not fail silently. But it's a *late* failure: the stakeholder only hits it at the final "Approve"
click, after the operator proposed and both sides completed review and sign-off, since nothing
today warns earlier. 002ic's `per_table_ownership` (surfaced on `propose_mapping`'s 409) covers
earlier warning for conflicts that already exist at propose time; it does not cover the narrower
race this task targets (both feeds draft before either is approved). This task's guard is the
necessary backstop regardless of 002ic's status, but sequencing 002ic first (or alongside) gives
better UX. `handleReject` already exists on the review page as recourse for a blocked stakeholder —
no new frontend work is required for this task to be usable end-to-end.

## Out of Scope

- No change to `LookupValueMap`/`LookupSnapshot` — they have no `source_definition_id` and no
  analogous conflict is possible.
- No `mapping_status` schema/enum change, no frontend changes — this is a backend-only prevention
  fix. The earlier "unusable" detection-and-hide design is retired, not extended.
- No change to `propose_mapping()`'s existing `already_mapped_tables` check — it's already correct
  for its own purpose (blocking new proposals over an approved table); this task only closes the
  separate gap at approval time.
- No retroactive cleanup of any table that may already be in the conflicting state today (two
  feeds both approved for the same table) — if that's a real concern, it's a separate task
  (a data-audit query, not a code change).

## Blast Radius

| File | Change |
|------|--------|
| `engine/src/migrations_engine/mapping/review.py` | Add the cross-feed conflict check inside `approve_mapping()`'s per-draft loop, before mutating `snapshot.status`. |
| `engine/tests/` | New test(s) covering: two feeds drafting the same table, first approves successfully, second's approval attempt is rejected; a project-scoped (`NULL` `source_definition_id`) approved row also blocks; approving a feed's own second table (no conflict) still works; re-running approval for a feed that already owns the table isn't blocked by its own row. |

## Pitfalls

1. The guard must exclude the **current** feed's own existing approved rows — a feed re-approving
   or holding an already-approved table for itself is not the conflict case; only a *different*
   `source_definition_id` (or a `NULL`-scoped row) counts.
2. `approve_mapping()` has two call shapes: single-table (`destination_object_name` given, one
   draft) and bulk (all of a feed's drafts). The guard must run inside the per-draft loop so it
   applies uniformly to both — don't special-case one path.
3. Exclude discarded feeds from the conflict check, matching `proposal.py`'s existing
   `Feed.status != "discarded"` exclusion — an approved mapping on a feed that's since been
   discarded should not block a legitimate approval elsewhere.
4. Error should be a 409 (conflict), not 422 — this mirrors `mapping_already_proposed`'s existing
   409 usage for the analogous propose-time conflict.
5. Don't touch the sign-off validation block (`review.py:202-221`) — this is a new, independent
   check, not a replacement for it. Run it after sign-off validation passes (fail fast on the
   cheaper check first) and before any `snapshot.status` mutation, so a rejection never leaves
   partial state (some drafts in a bulk-approve call flipped, others not).

## Tests

- Two feeds each draft "Customer"; approve Feed A's draft (succeeds); attempt to approve Feed B's
  draft for "Customer" → 409, no mutation (Feed B's snapshot stays `draft`).
- A `NULL`-scoped (`source_definition_id IS NULL`) approved `MappingSnapshot` for "Customer" exists;
  a feed's own draft for "Customer" attempts approval → 409.
- Feed A approves "Customer"; a *discarded* Feed C also has an approved "Customer" row → Feed A's
  approval is **not** blocked by the discarded feed's row.
- A feed approving its own two different tables ("Customer", "Orders") in one bulk-approve call,
  neither conflicting elsewhere → both succeed, no regression to the existing happy path.
- Bulk-approve where one of several drafts conflicts and others don't → verify no partial mutation
  (either the whole call rejects before any status flips, or — if partial success is intentionally
  allowed — that this is a deliberate, tested, documented choice, not an accident).

## Verification

```bash
.venv/bin/python -m pytest engine/tests -q
.venv/bin/python scripts/validate_okf.py
```

## Commit

```
fix(mapping): block approve_mapping when another feed owns the table

Two feeds could each independently draft and approve a MappingSnapshot
for the same destination_object_name, since approve_mapping() had no
cross-feed check (propose_mapping()'s already_mapped_tables guard only
protects against *proposing* over an already-approved table, not two
feeds racing to approve their own pre-existing drafts). Two approved
rows for the same table means codegen produces two independent stored
procedures, each migrating the same destination data.

Add the same project-wide "approved anywhere" check propose_mapping()
already uses to approve_mapping(), scoped to MappingSnapshot only —
LookupValueMap/LookupSnapshot have no source_definition_id and no
analogous conflict is possible.

Retires an earlier draft of this task that proposed a mapping_status:
"unusable" value with frontend filtering instead of preventing the
conflict at the source.
```
