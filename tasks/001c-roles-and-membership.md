# 001c-roles-and-membership

## Domain

- [auth.md](/Users/vjkotra/projects/katana/docs/domain/auth.md)
- [management.md](/Users/vjkotra/projects/katana/docs/domain/management.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)
- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)

## Objective

Implement the smallest role-and-membership slice: explicit role changes for
administrators and project membership as the gate for project-stakeholder
access.

## Scope

- `central_team`, `project_stakeholder`, and `read_only_auditor` role handling
- Admin-only user role changes
- Project membership add/remove flows
- Project-stakeholder access depending on membership, not role alone

## Out of Scope

- Password reset and login mechanics
- Migration mapping or source analysis
- Approval workflow semantics
- Broad UI redesign beyond the role/membership surfaces needed for testing

## Acceptance Criteria

- Non-admin role changes are rejected
- Project-stakeholder access requires membership
- Read-only auditors can inspect but not mutate
- Role changes and membership changes are auditable

## Test Expectations

- Non-admin role changes are rejected
- A stakeholder without membership cannot perform project-scoped actions
- An admin can add and remove project membership
- A read-only auditor cannot mutate management state

