---
id: 002b7
title: Fix 3 MappingBindingSignOff/LookupSignOff/source-model.md contradictions found by 002b6
status: completed
created: 2026-07-24
priority: medium
domain: docs/domain/
depends-on: [002aa, 002ab, 002ac, 002ad, 002ae, 002af, 002b0, 002b1, 002b2, 002b3, 002b4, 002b5, 002b6]
---

# Fix MappingBindingSignOff, LookupSignOff, and stale fiber entities in source-model.md

## Objective

Apply 3 corrections to `docs/domain/source-model.md` discovered by 002b6 verification.
These are schema mismatches between what the docs claim and what the ORM actually stores.

## Changes required

### 1. Fix MappingBindingSignOff (line ~495-504 of source-model.md)

The docs describe `sign_off_id`, `binding_index`, `signer_role`, `signer_id`, `status` (pending/approved/rejected enum).

The actual ORM (`models.py:616-639`) has `id`, `mapping_snapshot_id`, `destination_object_name`, `source_field`, `destination_field`, `user_id`, `role`, `signed_at`. No status enum — sign-off is represented by row existence (unique constraint on `snapshot+object+source_field+destination_field+user`).

**Replace with:**

```
MappingBindingSignOff
- `id` — primary key
- `mapping_snapshot_id` — FK → mapping_snapshots
- `destination_object_name` — the destination object this sign-off covers
- `source_field` — the source field being signed off
- `destination_field` — the destination field being signed off
- `user_id` — FK → users, who performed the sign-off
- `role` — signer's role
- `signed_at` — timestamp of sign-off
```

### 2. Fix LookupSignOff (line ~506-515 of source-model.md)

The docs describe `sign_off_id`, `fiber_id`, `lookup_name`, `signer_role`, `signer_id`, `status`.

The actual ORM (`models.py:644-661`) has `id`, `lookup_value_map_id`, `user_id`, `role`, `signed_at`. No `fiber_id`, no `lookup_name`, no `status`. This is a project-scoped model keyed on `lookup_value_map_id`.

**Replace with:**

```
LookupSignOff
- `id` — primary key
- `lookup_value_map_id` — FK → lookup_value_maps
- `user_id` — FK → users, who performed the sign-off
- `role` — signer's role
- `signed_at` — timestamp of sign-off
```

### 3. Delete stale fiber entity descriptions (lines 314-338 of source-model.md)

Lines 314-338 describe `LookupSourceEntry`, `LookupDestFeed`, `LookupDestEntry`, `LookupMapping` as current tables.

Line 452 correctly states they "were removed by tasks 001fg/001fh."

**Action:** Delete lines 314-338 outright.

## Verification

1. Confirm MappingBindingSignOff fields match `models.py:616-639` exactly
2. Confirm LookupSignOff fields match `models.py:644-661` exactly
3. Confirm no remaining references to `LookupSourceEntry`/`LookupDestFeed`/`LookupDestEntry`/`LookupMapping` in source-model.md

## Tests

N/A — documentation-only change.

## Commit

```
fix(docs): correct MappingBindingSignOff, LookupSignOff, and remove stale fiber entities in source-model.md

MappingBindingSignOff: replace binding_index+status enum with source_field+
destination_field (existence-based sign-off via unique constraint).
LookupSignOff: replace fiber_id+lookup_name+status with lookup_value_map_id+
user_id+signed_at (project-scoped, no fiber).
Delete stale fiber entity descriptions (lines 314-338) that contradict
line 452 saying they were removed by tasks 001fg/001fh.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```
