---
id: 002ac
title: Sync docs/domain/management.md against actual codebase
status: completed
created: 2026-07-24
priority: medium
domain: docs
depends-on: []
---

# Sync docs/domain/management.md

## Objective

Update `docs/domain/management.md` to accurately reflect the current user/role/membership implementation. Last updated 2026-07-16.

## Scope

- `docs/domain/management.md` only

## What to verify

1. **User model fields** — Compare against ORM: `session_version` field missing from doc
2. **Project membership** — `ProjectMembership` model has only `project_id`, `user_id`, `created_at` — verify doc accuracy
3. **Admin routes** — Verify `POST /users`, `PATCH /users/{user_id}`, `DELETE /users/{user_id}` match actual user routes
4. **Membership routes** — Verify `GET/POST/DELETE /projects/{project_id}/members` match actual routes
5. **PM reassignment** — `PATCH /projects/{id}/manager` — verify exists
6. **Role enforcement** — Verify route guards match actual implementation
7. **Bootstrap admin** — Verify bootstrap path still exists

## Out of scope

- Any other domain doc files
- Backend implementation changes

## Acceptance criteria

- [ ] User model fields match ORM
- [ ] Membership model fields match ORM
- [ ] All API routes match actual routes
- [ ] Route guards match actual guards
- [ ] Changelog updated
- [ ] timestamp updated
