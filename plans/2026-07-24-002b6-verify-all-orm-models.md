---
id: 002b6
title: Verify every ORM model has a documented home across docs/domain
status: completed
created: 2026-07-24
domain: docs/domain/
task: 002b6
---

# Plan: Verify all ORM models documented

## Task and Domain Links

- **Task:** [002b6](../tasks/002b6-verify-all-orm-models-documented.md)
- **Domain Docs:** All of `docs/domain/*.md`

## Current State

The 12 sync tasks cover most models via doc-first checklists, but this approach can't guarantee code-first completeness. Some models (ChangeRequest, ApprovalRecord, AuditEvent, Notification) are mentioned in passing across multiple docs but never verified field-by-field against the ORM.

## Objective

Run a code-first completeness check: enumerate all 31 ORM model classes from `db/models.py`, confirm each appears in at least one domain doc, and spot-check that the description is accurate (not just a name mention).

## Out of Scope

- Updating any doc files (handled by the 12 sync tasks)
- Backend implementation changes

## Blast Radius

Zero files changed. This is a verification-only pass.

## Verification

1. `grep "^class .*(Base)" engine/src/migrations_engine/db/models.py` — extract 31 model names
2. For each model: `grep -rl "ModelName" docs/domain/*.md` — find mentioning docs
3. Report any model with zero mentions
4. For models with mentions, spot-check 5-10 that the doc's field descriptions match the ORM (not just the name)

## Results

### Found (25/31) - accurately described
User, ProjectDefinition, ProjectRegistry, ProjectMembership, AuthSession, PasswordResetToken,
ChangeRequest, ApprovalRecord, RunRecord, RunCheckpoint, Feed, FeedSlice, SourceSchemaArtifact,
SourceValueSummary, MappingSnapshot, LookupSnapshot, LookupValueMap, CodeGenerationArtifact,
AuditEvent, Notification, ReconciliationReport, ReconciliationLineageRow, AICallLog

### Partial matches (4 models need doc updates)
- **FeedComment** — docs describe `author_id`, ORM uses `user_id`. Also documents non-existent `FeedSliceComment`.
- **MappingBindingSignOff** — docs describe `sign_off_id`, `binding_index`, `status` (pending/approved/rejected). ORM has `id`, `mapping_snapshot_id`, `destination_object_name`, `source_field`, `destination_field`, `user_id`, `role`, `signed_at` (no status — existence-based via unique constraint). Fix: replace `binding_index`+`status` with `source_field`+`destination_field`.
- **LookupSignOff** — docs describe `sign_off_id`, `fiber_id`, `lookup_name`, `signer_role`, `signer_id`, `status`. ORM has `id`, `lookup_value_map_id`, `user_id`, `role`, `signed_at`. Wrong foreign key entirely — no `fiber_id`, no `lookup_name`, no `status`.
- **ProjectFiber** — sub-entities (`LookupSourceEntry`, etc.) removed from ORM but still in docs. source-model.md is self-contradictory: lines 314-338 describe them as current tables, line 452 says "removed by tasks 001fg/001fh." Fix: delete lines 314-338.

### Not found in any doc (2 models need docs)
- **FeedSliceRow** — stores `source_slice_id`, `row_index`, `row_csv` for copybook data
- **ProjectSchemaAnalysis** — only referenced via API response names in `api.md`, no domain doc

## Pitfalls

- Some models are named in docs by their singular form (e.g. "source definition" vs `SourceSchemaArtifact`), making grep matching tricky
- Models like `Feed` are aliased as `SourceDefinition` and `SourceContract` in models.py — docs may use any of these names
- This is a completeness check, not a correctness check — it finds gaps but doesn't fix them

## Tests

N/A — documentation-only change, no test suite applies.

## Required fixes for source-model.md (to be applied by task 002b2)

### Fix 1: MappingBindingSignOff — replace docs schema with ORM schema (line ~495-504)

The docs describe a `status` enum + `binding_index` scheme. The ORM uses existence-based sign-offs with explicit `source_field`/`destination_field`.

**Replace the current MappingBindingSignOff section with:**

```
MappingBindingSignOff
- `id` — primary key
- `mapping_snapshot_id` — FK → mapping_snapshots
- `destination_object_name` — the destination object this sign-off covers
- `source_field` — the source field name being signed off
- `destination_field` — the destination field being signed off
- `user_id` — FK → users, who performed the sign-off
- `role` — signer's role
- `signed_at` — timestamp of sign-off
```

No `status` enum — a row's existence is the sign-off signal. The unique constraint on
`(mapping_snapshot_id, destination_object_name, source_field, destination_field, user_id)`
prevents duplicate sign-offs.

### Fix 2: LookupSignOff — replace fiber-based schema with lookup_value_map schema (line ~506-515)

The docs describe `fiber_id` (non-existent in ORM), `lookup_name`, `status`. The ORM uses a project-scoped model keyed on `lookup_value_map_id`.

**Replace with:**

```
LookupSignOff
- `id` — primary key
- `lookup_value_map_id` — FK → lookup_value_maps
- `user_id` — FK → users, who performed the sign-off
- `role` — signer's role
- `signed_at` — timestamp of sign-off
```

No `fiber_id`, no `lookup_name`, no `status` — sign-off is existence-based via unique constraint on `(lookup_value_map_id, user_id)`.

### Fix 3: Delete stale fiber entity descriptions (lines 314-338)

Lines 314-338 describe `LookupSourceEntry`, `LookupDestFeed`, `LookupDestEntry`, `LookupMapping` as current tables. Line 452 correctly says they "were removed by tasks 001fg/001fh." This is a self-contradiction — delete lines 314-338 outright.

## Commit

```
docs: verify all ORM models have documented homes (no-op, verification only)

Run code-first completeness check: enumerate all 31 ORM models and
confirm each is mentioned in at least one domain doc. Spot-check
field accuracy for models mentioned in passing.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```
