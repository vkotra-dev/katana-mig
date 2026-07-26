---
id: 002ac
title: Sync docs/domain/management.md against actual codebase
status: ready
created: 2026-07-24
domain: docs/domain/management.md
task: 002ac
---

# Plan: Sync docs/domain/management.md

## Task and Domain Links

- **Task:** [002ac](../tasks/002ac-sync-domain-docs-management.md)
- **Domain Doc:** `docs/domain/management.md`

## Current State

`docs/domain/management.md` was last updated 2026-07-16. The User model and ProjectMembership model have evolved since then.

## Objective

Read `docs/domain/management.md` section by section, cross-reference against `db/models.py` (User, ProjectMembership) and `routes/users.py`, `routes/projects.py`. Patch divergences.

## Out of Scope

- Any other domain doc files
- Backend implementation changes

## Blast Radius

One file: `docs/domain/management.md`

## File Changes

- `docs/domain/management.md` — patch in-place

## Verification

1. Verify all User fields match ORM model
2. Verify ProjectMembership fields match ORM model
3. Verify all route guards mentioned exist in route files
4. Verify bootstrap admin flow matches actual implementation

## Pitfalls

- `session_version` field on User is not in the doc but is used for session invalidation
- `status` field default is "declared", not "active"

## Tests

N/A — documentation-only change, no test suite applies.

## Commit

```
docs(domain): sync management.md against codebase

Cross-reference docs/domain/management.md against ORM models (User,
ProjectMembership) and management routes. Fix field descriptions,
route accuracy, and enforcement rules.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```
