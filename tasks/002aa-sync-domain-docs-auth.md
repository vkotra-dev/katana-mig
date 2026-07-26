---
id: 002aa
title: Sync docs/domain/auth.md against actual codebase
status: completed
created: 2026-07-24
priority: medium
domain: docs
depends-on: []
---

# Sync docs/domain/auth.md

## Objective

Update `docs/domain/auth.md` to accurately reflect the current auth implementation in the codebase. The doc was last updated 2026-07-16 and may have drifted.

## Scope

- `docs/domain/auth.md` only

## What to verify

1. **User model fields** — Compare against `engine/src/migrations_engine/db/models.py` User class:
   - `session_version` (int) — doc does NOT mention this field
   - `status` default is "declared" not "active"
   - `email` max length is 320, not just "email"
   - `password_hash` max length 255

2. **AuthSession model** — `engine/src/migrations_engine/db/models.py` line ~101:
   - Has `session_id`, `user_id`, `issued_at`, `expires_at`, `revoked`, `created_at`, `updated_at`
   - Doc describes "stateless JWT" but the code stores sessions in `auth_sessions` table
   - This is a divergence: doc says "stateless JWT" but the code uses session records

3. **Role model** — Verify all 5 roles are correctly described:
   - `admin`, `pm`, `central_team`, `project_stakeholder`, `read_only_auditor`
   - `service_account` as non-human principal (correctly excluded from role model)

4. **API endpoints** — Check all listed endpoints against actual auth routes:
   - `POST /auth/login`
   - `POST /auth/logout`
   - `POST /auth/password-reset/request`
   - `POST /auth/password-reset/confirm`
   - `GET /auth/session`

5. **Bootstrap identity** — Verify the bootstrap path described still exists

6. **Session authority rule** — Verify the JWT claim shapes match actual implementation

7. **Lifecycle/invalidation** — Verify soft-delete, disabled, expiry behavior matches code

## Out of scope

- Any other domain doc files
- Backend implementation changes
- Test changes

## Acceptance criteria

- [ ] All User model fields in doc match ORM model exactly
- [ ] AuthSession doc accurately describes persistence model (JWT + session table)
- [ ] All 5 roles correctly described with correct scope
- [ ] All API endpoints listed exist in code and no undocumented ones are documented
- [ ] Bootstrap identity section matches actual implementation
- [ ] Session authority rules are accurate
- [ ] Changelog updated with sync date
- [ ] timestamp field in frontmatter updated to current date
