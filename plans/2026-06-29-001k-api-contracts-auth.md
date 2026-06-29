# Task
- [001k-api-contracts-auth](/Users/vjkotra/projects/katana/tasks/001k-api-contracts-auth.md)

# Domain
- [api.md](/Users/vjkotra/projects/katana/docs/domain/api.md)
- [auth.md](/Users/vjkotra/projects/katana/docs/domain/auth.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)
- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)

## Current State
- `auth.md` describes auth endpoints behaviorally but without JSON schemas or a
  shared error envelope.
- `engine/src/migrations_engine/app.py` exposes only `/healthz`.
- UI tasks `001g`–`001i` are marked ready but depend on a concrete auth API.
- Admin bootstrap exists via `katana-seed-admin` CLI; no bootstrap HTTP create
  endpoint yet.

## Objective
Add a formal auth API contract page and matching OpenAPI artifact so `001a`
implementation and UI planning can proceed in parallel against stable shapes.

## Out of Scope
- Implementing routes or JWT logic
- Management/user CRUD contracts
- Auto-generated frontend clients

## Blast Radius
- `docs/domain/api.md`
- `docs/domain/README.md`
- `docs/domain/auth.md`
- `engine/openapi/auth.yaml`
- `tasks/TASK_INDEX.md`

## File Changes
- Add `docs/domain/api.md`
- Add `engine/openapi/auth.yaml`
- Link `api.md` from `docs/domain/README.md`
- Add cross-reference from `auth.md` to `api.md`
- Add task `001k-api-contracts-auth` to task index

## Tests
- Validate OpenAPI YAML parses (optional `openapi-spec-validator` in dev only)
- Manual review: every `auth.md` endpoint has a schema in `api.md`

## Verification
- `docs/domain/api.md` documents login, session, logout, password reset, and
  bootstrap status with JSON examples
- `engine/openapi/auth.yaml` lists the same paths and component schemas
- `tasks/TASK_INDEX.md` includes `001k`

## Pitfalls
- Do not implement routes in this task
- Do not add management endpoints yet; keep the slice limited to auth
- Keep bootstrap creation CLI-only; expose only `GET /auth/bootstrap/status`

## Commit
- `docs(api): add auth HTTP contract and OpenAPI slice`
