# 001b-password-reset

## Domain

- [auth.md](/Users/vjkotra/projects/katana/docs/domain/auth.md)
- [management.md](/Users/vjkotra/projects/katana/docs/domain/management.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)
- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)

## Objective

Implement self-service password reset so a user can recover access without
changing role or project scope, and so old credentials stop working after reset.

## Scope

- Password reset request and reset confirmation flow
- Proof-of-control challenge for the account
- Password replacement and old-credential invalidation
- No role escalation through the reset path

## Out of Scope

- Administrative user creation
- Role assignment or membership changes
- Login UI redesign beyond the minimal reset entry points
- Migration-domain mapping or run behavior

## Acceptance Criteria

- A reset challenge can be issued and consumed once
- Resetting a password stores only a new hash
- The old password stops working after reset
- The reset flow cannot change role or project membership

## Test Expectations

- Reset token or equivalent challenge works once and cannot be reused
- Password reset invalidates the old password
- Password reset does not change role
- Password reset does not change project access

