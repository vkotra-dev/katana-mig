# 001j-engine-fastapi-foundation

## Domain
- [governance.md](/Users/vjkotra/projects/katana/docs/domain/governance.md)
- [auth.md](/Users/vjkotra/projects/katana/docs/domain/auth.md)
- [management.md](/Users/vjkotra/projects/katana/docs/domain/management.md)
- [project.md](/Users/vjkotra/projects/katana/docs/domain/project.md)
- [runs.md](/Users/vjkotra/projects/katana/docs/domain/runs.md)
- [source-model.md](/Users/vjkotra/projects/katana/docs/domain/source-model.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)

## Goal
Initialize the Python backend as a FastAPI application and create the first
migration-backed models that support auth, project routing, runs, source slices,
and auditability.

## Scope
- `engine/` FastAPI scaffold
- SQLAlchemy model layer
- Alembic migrations
- local env wiring for MySQL

## Out of Scope
- API route implementation
- business logic for login, membership, or approvals
- source analysis or reconciliation algorithms
- UI work

## Deliverables
- FastAPI app entrypoint
- MySQL-backed settings
- Alembic migration environment
- tables for users, project definitions, project registry, memberships,
  sessions, password reset, change requests, approvals, run records,
  checkpoints, source definitions, source slices, and audit events

## Verification
- `python -m compileall engine/src engine/migrations`

## Notes
- This task formalizes the backend scaffold already present in `engine/`.
