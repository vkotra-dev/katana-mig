# 001a-login-and-session

## Domain

- [auth.md](/Users/vjkotra/projects/katana/docs/domain/auth.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)
- [management.md](/Users/vjkotra/projects/katana/docs/domain/management.md)

## Objective

Implement the smallest login slice: password login for human callers, stateless
JWT session issuance, and authoritative session-based identity/role handling.

## Scope

- Password login for human users
- JWT issuance and validation shape
- Authenticated identity and role as the only authority source
- Soft-delete and disabled-user rejection at request time

## Out of Scope

- Password reset or recovery flows
- Role assignment and project membership changes
- Migration mapping, source analysis, and code generation
- UI polish beyond the minimal login path needed to verify the flow

## Acceptance Criteria

- Password login succeeds for valid credentials
- Invalid credentials are rejected
- JWT sessions are stateless
- Request bodies cannot override authenticated identity or role
- Soft-deleted and disabled users cannot continue to act

## Test Expectations

- A valid login returns a usable JWT
- An invalid login is rejected
- A soft-deleted user is rejected even if a token exists
- A caller-supplied role is ignored when it conflicts with authenticated state

