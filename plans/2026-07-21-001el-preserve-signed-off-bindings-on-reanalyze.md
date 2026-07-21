# Plan: 001el — Patch Field Mapping In Place on Re-Analyze, Preserving Signed-Off Bindings

## Task and Domain links

- Task: `tasks/001el-preserve-signed-off-bindings-on-reanalyze.md`
- Domain: `docs/domain/ui.md` (Field mapping section) — this changes review-workflow behavior,
  governance I22 applies

## Current State

- `propose_mapping` (`mapping/proposal.py`) skips a table only when it's `status == "approved"`
  (`already_mapped_tables`, `proposal.py:60-86,215`). A `draft` snapshot doesn't match, so
  re-analysis always creates a **new `MappingSnapshot` row** (`proposal.py:250-262`,
  new `mapping_snapshot_id`, incremented `mapping_snapshot_version`), built entirely from the
  fresh AI response — no read of the prior draft's `field_bindings`, no
  `MappingBindingSignOff` lookup.
- `MappingBindingSignOff` (`db/models.py`) is keyed by `mapping_snapshot_id` +
  `(source_field, destination_field)` pair (re-keyed in `001dy`). A new snapshot ID means prior
  sign-offs are orphaned — `get_sign_off_status` (`management/sign_offs.py`) only reads sign-offs
  for the latest snapshot per table.
- **Prior attempt (`001df`) never actually built this.** Its task doc
  (`tasks/completed/001df-ai-reanalysis-preservation.md`) described real per-field upsert logic
  ("If a destination column has an active sign-off, skip creating a snapshot row for it..."), but
  the shipped commit (`d4a0400`) only changed 3 lines in what was then `review.py`, per its own
  commit message: "skip already-approved destination tables instead of throwing 409" — i.e., it
  just silently skips fully-`approved` tables, the same `already_mapped_tables` check that
  already existed. The `draft`-snapshot merge case — the actual point of the task — was never
  implemented.
- Confirmed live in the dev DB: `policy_master`/`policy_claims` each have disconnected `v1`/`v2`
  `draft` rows from separate "AI Analyze" runs, no shared sign-off state between them.

## Objective

1. `propose_mapping`: when a table already has a `draft` snapshot, patch its `field_bindings` in
   place instead of creating a new snapshot row/version.
2. Merge logic keyed by `(source_field, destination_field)`: any pair with an existing sign-off
   (either role) keeps its current value; everything else takes the fresh AI value.
3. No version bump for a patched draft — versioning stays for genuinely new proposals only.
4. One-time cleanup script/migration that runs the same merge logic retroactively across every
   `(project, feed, table)` group that currently has more than one simultaneous `draft` row —
   confirmed 2 such groups exist in the dev DB today (`policy_master`, `policy_claims`, both zero
   sign-offs) — and marks the superseded older row(s) with a new `status="superseded"` value.
   Confirmed safe: `MappingSnapshot.status` is a plain `String(32)` column with no enum
   constraint, and every existing check in the codebase is `== "draft"`/`!= "draft"` (not an
   exhaustive allow-list), so introducing this value requires no other code changes — existing
   `status == "draft"` filters exclude it automatically.

## Out of Scope

- `patch_mapping` (operator edits) — unaffected.
- `fibers.py`'s `feed_analysis`/`lookup_mapping` re-analysis paths — `001df`'s "Part 3" scope;
  not touched here (flag as a separate follow-up if the same gap is confirmed there).
- Multi-table proposal orchestration beyond the single-table merge itself.

## Decision: what happens to an old, unsigned binding the new AI proposal drops entirely

Recommended: **drop it** — if the AI no longer proposes a mapping for that destination field and
no one signed off on the old value, there's nothing worth preserving; keeping it would silently
resurrect a mapping the latest analysis explicitly chose not to make. State this explicitly in
the PR since it's a real behavior choice, not a default to assume silently (matches this
session's pattern of surfacing exactly this kind of decision rather than picking it implicitly).

## Blast Radius

- `engine/src/migrations_engine/mapping/proposal.py` (edited — core logic)
- `engine/src/migrations_engine/management/sign_offs.py` (read-only reference — confirm
  `get_sign_off_status`'s query shape to reuse for the pre-merge lookup, don't duplicate a third
  copy of "how to query sign-offs for a snapshot")
- `engine/tests/test_mapping_review_api.py` (edited/new tests)
- `engine/scripts/consolidate_duplicate_draft_snapshots.py` (new, one-time cleanup script) — or a
  hand-written Alembic data migration if this repo's convention prefers migrations over standalone
  scripts for one-time data fixes; check existing precedent (`engine/migrations/versions/`) before
  choosing the mechanism.
- No schema migration required for the `status="superseded"` value itself (plain string column,
  confirmed above) — only needed if the cleanup mechanism is itself a migration file.
- No frontend change — the API contract (`propose_mapping`'s response) is unchanged in shape; a
  `superseded` snapshot is never the "latest" for its table, so nothing currently reads it.

## File Changes

**`mapping/proposal.py`**
- Before the per-table loop (`proposal.py:210`), fetch existing `draft` snapshots for tables in
  this proposal (`select(MappingSnapshot).where(..., status == "draft", destination_object_name
  in mapped_table_names)`), keyed by `destination_object_name`.
- For a table with an existing draft:
  - Fetch its `MappingBindingSignOff` rows, build a set of signed-off `(source_field,
    destination_field)` pairs (matching either role — "at least one" per requirement 2).
  - Build the merged `field_bindings`, per pair:
    - **Not signed off, fresh binding exists for the pair**: use the fresh AI binding wholesale
      (`binding.model_dump()`).
    - **Not signed off, no fresh binding for the pair**: drop it (per the Decision above).
    - **Signed off, fresh binding exists for the pair**: key-level overlay —
      `merged = {**fresh_binding.model_dump(), **old_binding}`. Old wins on any key present in
      both; fresh wins only on a key the old dict doesn't have at all (forward-compatible with
      future `Binding` schema fields, without touching `MappingBindingSignOff`'s schema — a
      missing key in the old dict is itself the signal that it predates the field and wasn't
      part of the original review).
    - **Signed off, no fresh binding for the pair** (AI stopped proposing this mapping entirely):
      keep the old binding as-is — a sign-off should not be silently invalidated by the AI simply
      omitting the pair this time.
    - Any pair present in the fresh proposal but absent from the old bindings: add it wholesale
      (`binding.model_dump()`).
  - Mutate the existing `MappingSnapshot` row's `field_bindings` in place (`snapshot.field_bindings
    = merged`) — no `new_id()`, no `next_snapshot_version` call, no new row.
  - Still record a `record_management_audit` event for the patch (distinct `event_type`, e.g.
    `mapping_reanalyzed`, from `mapping_proposed`, so the audit trail distinguishes "fresh
    proposal" from "patched existing draft").
- For a table with no existing draft (and not `approved`, per current behavior): unchanged, new
  snapshot as today.
- For a table already `approved`: unchanged, skipped as today.

**`engine/scripts/consolidate_duplicate_draft_snapshots.py` (new)**
- Query for every `(project_id, source_definition_id, destination_object_name)` group with more
  than one `status == "draft"` `MappingSnapshot` — confirmed 2 groups exist today.
- For each group: pick the row with the latest `created_at` as authoritative. For every other
  (older) row in the group: fetch its `MappingBindingSignOff` rows; for each, check whether the
  same `(source_field, destination_field)` pair exists in the authoritative row with the *same*
  binding value — if so, re-point that sign-off row's `mapping_snapshot_id` to the authoritative
  row's id (reusing requirement 2's comparison logic, not a separate implementation); if the pair
  doesn't exist or the value differs, leave the sign-off orphaned on the old row (it no longer
  applies) but log it for manual review rather than silently dropping it.
- Set the older row(s)' `status = "superseded"`.
- Idempotent — safe to run more than once (a group with only one draft row, or already-superseded
  older rows, is a no-op).

## Tests

- New: re-analyze a table with a draft snapshot that has ONE signed-off binding (central_team
  only) and confirm: that specific binding's value is unchanged after re-analysis, even though
  the mocked AI response proposes a different value for it; all other bindings update to the
  fresh AI values; `mapping_snapshot_id`/`mapping_snapshot_version` are unchanged (same row, not
  a new one).
- New: same test with a project_stakeholder-only sign-off (not central_team) — confirm "at least
  one" role is sufficient to preserve, not requiring both.
- New: a binding with no sign-off at all — confirm it updates to the fresh AI value.
- New: an old binding with no sign-off that the new AI response doesn't mention — confirm it's
  dropped (per the Decision), not silently kept.
- New: a signed-off binding where the new AI response doesn't mention that pair at all — confirm
  it's kept as-is (sign-off isn't invalidated by the AI simply omitting it this time).
- New: key-level overlay — mock a fresh `Binding` response containing a field not present in the
  old stored dict (simulate schema growth, e.g. add a throwaway extra key to the old dict's
  absence), confirm a signed-off pair ends up with that new field populated from the fresh
  response while its core fields (`destination_field`, `binding_type`) remain the old,
  signed-off values.
- New: a genuinely new table (no existing draft, not approved) — confirm unchanged behavior
  (new snapshot, new version).
- New: an already-`approved` table — confirm unchanged behavior (skipped, no new snapshot).
- Rerun full `test_mapping_review_api.py` — expect some existing re-analysis assertions to change
  behavior (any test currently asserting "re-analyze always creates a new version" needs
  updating to match the new patch-in-place behavior for drafts).

## Verification

- `mypy --strict` / `ruff` clean.
- Manually: sign off one binding on a draft mapping (as either role), re-run "AI Analyze," confirm
  in the UI that the signed-off field's value and its sign-off chip both survive, while other
  fields refresh to the latest AI proposal.
- Manually: confirm `mapping_snapshot_version` does NOT increment on a patched re-analysis (check
  via the API response or DB directly).
- Run the cleanup script against the dev DB, confirm the 2 known duplicate-draft groups collapse
  to 1 current draft each with the other marked `superseded`, and confirm `bulk approve`/`reject`/
  `unapprove` for those feeds now behaves deterministically (no more ambiguous dedup across
  simultaneous drafts).

## Pitfalls

- Run the cleanup script *after* the code fix lands, not before — cleaning up existing duplicates
  while `propose_mapping` can still create new ones on the next re-analysis just recreates the
  mess it fixed.
- Don't reuse `next_snapshot_version`/`new_id()` accidentally for the patched-draft path — that's
  exactly the bug being fixed; a patched table must keep its existing `mapping_snapshot_id` and
  `mapping_snapshot_version`.
- `get_sign_off_status`'s existing query logic for "is this pair signed off by this role" should
  be the reference for how to check sign-off state here — don't write a third, subtly different
  version of that query (matching the DRY lesson from `001ek`'s DDL-parser findings this same
  session).
- The `IntegrityError` → `mapping_already_proposed` handling (`proposal.py:266-270`) currently
  assumes every table in the loop results in either a skip or a new `db.add()`'d row; with the
  patch-in-place path added, make sure `db.flush()`'s behavior and that error handling still make
  sense (a patched row isn't newly added, so it shouldn't be able to trigger the same
  duplicate-key `IntegrityError` this catch was written for — confirm, don't assume).
- Confirm `snapshot_to_response(snapshots[0], db=db)` (the function's return value,
  `proposal.py:295`) still returns something sensible when the "snapshots" list is empty (e.g.
  every table in the proposal was either approved-skip or patch-in-place, none freshly created) —
  today `if not snapshots: raise AuthApiError("mapping_already_proposed", ...)` at line 285-286
  would incorrectly fire for a fully-successful patch-only re-analysis; this needs its own branch
  distinguishing "nothing happened at all" from "everything was patched successfully."

## Commit

Own commit. Investigate `001df`'s exact diff (already done above) before starting — this task
supersedes that attempt's field-mapping scope; its source-analysis and lookup-fiber scopes are
untouched and out of scope here.
