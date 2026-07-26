---
id: 002ab
title: Sync docs/domain/security.md against actual codebase
status: ready
created: 2026-07-24
domain: docs/domain/security.md
task: 002ab
---

# Plan: Sync docs/domain/security.md

## Task and Domain Links

- **Task:** [002ab](../tasks/002ab-sync-domain-docs-security.md)
- **Domain Doc:** `docs/domain/security.md`

## Current State

`docs/domain/security.md` was last updated 2026-07-16. The security boundaries, threat model, and control requirements need verification against the actual auth/session/persistence/audit code.

## Objective

Read `docs/domain/security.md` section by section, cross-reference against `db/models.py` (User, AuthSession), `routes/auth.py`, `routes/users.py`, `harness/audit_bus.py`, `harness/policy_gate.py`, and `migrations_engine/pii_classifier.py`. Patch any divergences.

## Out of Scope

- Any other domain doc files
- Backend implementation changes
- Adding new security controls

## Blast Radius

One file: `docs/domain/security.md`

## File Changes

- `docs/domain/security.md` — patch in-place

## Verification

1. For each security boundary (identity, project, workspace, PII, audit), verify there is corresponding enforcement code
2. For each threat model risk, verify it's still a valid concern
3. For each control requirement, verify it maps to actual code
4. For session invalidation triggers, verify all 6 are handled
5. Run `grep -r "session_version\|soft_deleted_at\|password_hash" engine/src/migrations_engine/db/models.py` to confirm field accuracy

## Pitfalls

- The doc mentions "fail-closed" but doesn't specify HOW each component fails closed. Need to verify against actual error handling in auth routes.
- The PII boundary references `pii_classifier` — verify the classifier exists and what it actually does.
- The 365-day audit retention may be aspirational if no retention job exists.

## Tests

N/A — documentation-only change, no test suite applies.

## Commit

```
docs(domain): sync security.md against codebase

Cross-reference docs/domain/security.md against ORM models, auth routes,
audit bus, policy gate, and PII classifier. Fix boundary descriptions,
threat model, and control requirements.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```
