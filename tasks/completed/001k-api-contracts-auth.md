# 001k-api-contracts-auth

## Domain

- [api.md](/Users/vjkotra/projects/katana/docs/domain/api.md)
- [auth.md](/Users/vjkotra/projects/katana/docs/domain/auth.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)
- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)

## Objective

Formalize the first HTTP API contract slice so backend implementation and UI
planning can proceed against shared request/response schemas instead of prose
in `auth.md` alone.

## Scope

- Auth endpoints: bootstrap status, login, session, logout, password-reset
  request/confirm
- Shared error envelope, status codes, and role enums
- OpenAPI artifact for the auth slice
- UI-to-endpoint mapping for login and session restore

## Out of Scope

- FastAPI route implementation (task `001a`)
- Management/user CRUD API contracts
- Project, run, and migration endpoints
- Generated TypeScript client code

## Acceptance Criteria

- `docs/domain/api.md` defines JSON shapes for all auth-slice endpoints
- `engine/openapi/auth.yaml` matches `api.md`
- UI tasks can reference stable endpoint paths, payloads, and error codes
- Bootstrap creation remains documented as CLI-first; API exposes status only

## Test Expectations

- OpenAPI file parses as valid OpenAPI 3.1
- Every endpoint listed in `auth.md` API contract section appears in `api.md`
  with request/response schemas
