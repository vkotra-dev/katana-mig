Task: tasks/002id-approve-mapping-cross-feed-guard.md
Domain: docs/domain/source-model.md

## Current State

- `approve_mapping()` (`engine/src/migrations_engine/mapping/review.py:156-276`) has two paths:
  single-table (`destination_object_name` given, `drafts` is one row) and bulk (all of the feed's
  `status == "draft"` rows, deduped to latest per table at lines 189-196).
- Sign-off validation (lines 202-221) runs once, before the per-draft loop, scoped to the current
  feed's own bindings/lookups only — no cross-feed awareness anywhere in this function today.
- The per-draft loop (lines 225-249) flips `snapshot.status = "approved"` unconditionally once
  sign-off passes (aside from the existing `snapshot.status != "draft"` check at line 226, which
  guards against re-approving a non-draft row, not cross-feed conflicts).
- `proposal.py:51-77` already computes "approved anywhere in the project for this table" via
  `already_mapped_tables | project_approved`, using an `outerjoin(Feed, ...)` plus
  `Feed.status != "discarded"` to exclude discarded feeds and include `NULL`-scoped rows. This
  exact pattern is what the new guard should reuse, not reinvent.
- `docs/domain/source-model.md:423` documents the unique index as feed-scoped
  (`project_id, source_definition_id, destination_object_name, version`) with no mention that
  approval-time cross-feed conflicts are separately guarded — that line is the natural insertion
  point for a clarifying note.
- The review page's approve action (`review/page.tsx:128-139`, `handleApprove`) already catches
  errors and renders `err.message` in a visible banner (line 662) — verified this is not swallowed
  like the `propose_mapping` 409 case found earlier. `MappingApiError`
  (`web/lib/mapping-api.ts:43-54`) already carries an optional `.detail` field, parsed from the
  backend's `{error: {code, message, detail}}` shape (lines 144-158) — unused today, but the
  plumbing already exists, so the new 409 should populate it rather than leaving it out.
- Traced the UX impact: this is a **late** failure by design — the `project_stakeholder` only
  discovers a conflict at the final "Approve" click, after the operator proposed and both sides
  completed binding review and sign-off. There is no earlier warning on the review page today.
  002ic (duplicate feed mapping detection, `per_table_ownership` on `propose_mapping`'s 409) covers
  the *earlier* warning — for feeds where the conflict already existed at propose time. It does not
  cover the narrower race this task targets (both feeds draft before either is approved, so neither
  hits 002ic's propose-time check) — this task's approve-time guard is the necessary backstop for
  that case regardless of whether 002ic ships. Recommend sequencing 002ic before or alongside this
  task for the best UX, but this task is correct and safe to ship independently either way.
- `review/page.tsx:169` (`handleReject`) already gives the blocked stakeholder recourse — reject the
  now-unapprovable draft. No new UI action is needed for this task to be usable end-to-end.

## Objective

Add a cross-feed conflict check inside `approve_mapping()`'s per-draft loop: reject approval (409)
if any other feed's `MappingSnapshot` — different `source_definition_id`, or `NULL`-scoped,
excluding discarded feeds — is already `approved` for the same `destination_object_name` in the
project. Populate the 409's `detail` dict with the conflicting `source_definition_id` and
`mapping_snapshot_id` (the frontend's `MappingApiError.detail` already supports this — see Current
State), so a future UI enhancement can link directly to the owning feed instead of just showing
text.

## Out of Scope

- `LookupValueMap`/`LookupSnapshot` — no `source_definition_id`, no analogous conflict possible.
- No `mapping_status` schema/enum change, no frontend work — retires the earlier "unusable"
  detection-and-hide design entirely; this is prevention-only.
- No change to `propose_mapping()`'s existing guard.
- No data migration/audit for tables that may already be in a conflicting state today.

## Blast Radius

| File | Action | What changes |
|------|--------|---------------|
| `engine/src/migrations_engine/mapping/review.py` | modify | Add cross-feed conflict check in `approve_mapping()`'s per-draft loop |
| `docs/domain/source-model.md` | modify | Clarify the feed-scoped unique index note at line 423 with the approval-time cross-project invariant |
| `engine/tests/test_mapping_review_api.py` (or a new file) | modify/new | Cross-feed conflict tests |

## File Changes

### `engine/src/migrations_engine/mapping/review.py`

Add right before the per-draft loop (after sign-off validation, before line 223's `now = ...`):

```python
    # Cross-feed conflict guard: at most one feed may hold an approved MappingSnapshot
    # for a given destination_object_name project-wide, otherwise codegen generates
    # duplicate stored procedures that independently migrate the same destination data.
    for snapshot in drafts:
        if snapshot.status != "draft":
            continue
        conflict = db.scalar(
            select(MappingSnapshot)
            .outerjoin(Feed, Feed.source_definition_id == MappingSnapshot.source_definition_id)
            .where(
                MappingSnapshot.project_id == project_id,
                MappingSnapshot.destination_object_name == snapshot.destination_object_name,
                MappingSnapshot.status == "approved",
                or_(
                    MappingSnapshot.source_definition_id.is_(None),
                    and_(
                        MappingSnapshot.source_definition_id != source_definition_id,
                        Feed.status != "discarded",
                    ),
                ),
            )
        )
        if conflict is not None:
            raise AuthApiError(
                "mapping_table_conflict",
                f"'{snapshot.destination_object_name}' already has an approved mapping on "
                "another feed. Approving here would generate a duplicate migration procedure "
                "for the same destination table.",
                409,
                {
                    "destination_object_name": snapshot.destination_object_name,
                    "conflicting_source_definition_id": conflict.source_definition_id,
                    "conflicting_mapping_snapshot_id": conflict.mapping_snapshot_id,
                },
            )
```

Placed as a **separate pass before** the existing mutation loop (line 225's `for snapshot in
drafts:`) — not merged into it — so a rejection never leaves a bulk-approve call half-applied
(some drafts flipped to `approved`, others not).

Import additions required — checked `review.py`'s current imports (lines 1-20): it has
`from sqlalchemy import select` only (no `or_`/`and_`), and `from ..db.models import
MappingSnapshot, LookupValueMap` (no `Feed`). Update both:

```diff
-from sqlalchemy import select
+from sqlalchemy import and_, or_, select
 from sqlalchemy.orm import Session

 from ..api.deps import AuthApiError
 from ..api.schemas import MappingFieldBindingResponse, MappingReviewResponse
-from ..db.models import MappingSnapshot, LookupValueMap
+from ..db.models import Feed, MappingSnapshot, LookupValueMap
```

### `docs/domain/source-model.md`

```diff
 The unique index on `MappingSnapshot` is feed-scoped: `(project_id, source_definition_id, destination_object_name, version)`.
+
+That index only prevents duplicate *rows* within one feed. A separate runtime check in
+`approve_mapping()` prevents a different failure mode: two different feeds each independently
+approving their own `MappingSnapshot` for the same `destination_object_name`. Since codegen is
+triggered per feed and would otherwise generate one stored procedure per approved snapshot, two
+approved snapshots for the same destination table would migrate that table's data twice. At most
+one feed (or a project-scoped, `NULL`-`source_definition_id` snapshot) may hold an `approved`
+`MappingSnapshot` for a given destination table at a time; approving a second one is rejected with
+a 409 (`mapping_table_conflict`).
```

Bump `timestamp` frontmatter to the actual date this lands.

## Tests

- Two feeds each draft `"Customer"`; approve feed A's draft (succeeds, `status == "approved"`);
  attempt to approve feed B's draft for `"Customer"` → 409 `mapping_table_conflict`; verify feed
  B's snapshot is still `"draft"` afterward (no partial mutation). Also assert the error's `detail`
  dict contains `conflicting_source_definition_id == feed A's id` and the correct
  `destination_object_name` — the frontend's `MappingApiError.detail` depends on this shape.
- A `NULL`-scoped approved `MappingSnapshot` for `"Customer"` exists (simulate directly via the
  test DB, no `source_definition_id`); a feed's own draft for `"Customer"` attempts approval →
  409.
- Feed A approves `"Customer"`; a separate, **discarded** feed also has an approved `"Customer"`
  row → feed A's approval is **not** blocked (discarded feeds excluded from the conflict check).
- A feed bulk-approving two of its own distinct tables (`"Customer"`, `"Orders"`), neither
  conflicting elsewhere → both succeed, existing happy path unaffected.
- A feed bulk-approving two tables where one conflicts and one doesn't → verify the whole call
  rejects before any status mutation (the guard runs as a full pre-pass over all drafts before the
  mutation loop, so a mid-batch conflict can't leave the batch half-approved).

## Verification

```bash
.venv/bin/python -m pytest engine/tests -q
.venv/bin/python scripts/validate_okf.py
```

Expected: new tests pass, full suite has no new failures, OKF reports zero warnings for
`docs/domain/source-model.md`.

## Pitfalls

- Exclude the current feed's own rows from the conflict query (`source_definition_id !=
  source_definition_id` for the non-`NULL` branch) — a feed is never "in conflict" with itself.
- Run the guard as a full pre-pass over `drafts` before any mutation, not interleaved with the
  existing mutation loop — a bulk-approve call must not partially apply if one of several tables
  conflicts.
- Reuse `proposal.py`'s exact `outerjoin`/`Feed.status != "discarded"` pattern rather than writing
  a second, subtly-different version of "approved anywhere in the project."
- This is a `MappingSnapshot`-only change — do not touch `LookupValueMap`/`LookupSnapshot` approval
  logic (the `associated_maps`/lookup-approval block at `review.py:251-268`), which has no
  analogous conflict and must keep working exactly as before.

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
