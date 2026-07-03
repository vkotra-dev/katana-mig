# Task 001ax — Project Resources Field

**Plan:** `plans/2026-07-03-001ax-project-resources-field.md`

## Domain

- [project.md](/Users/vjkotra/projects/katana/docs/domain/project.md)
- [api.md](/Users/vjkotra/projects/katana/docs/domain/api.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)

## Current State

- `project_records.environment` is a `String(64)` column that stores a single
  environment name. It is never consumed by the engine and has no distinct
  purpose from `execution_environments`.
- There is no field for recording infrastructure details such as server
  addresses, credentials, VPN access, and database connection info per
  environment.

## Objective

Replace the unused `environment` string column on `project_records` with a
`project_resources` text column (CLOB) that operators fill with free-form
infrastructure notes — host/IP, port, database name, credentials, VPN details
— organised in sections per environment (DEV → STG → PROD). New projects
receive a pre-filled template so operators know what to document.

`RunRecord.environment` is a different table and must not be touched.

## Scope

- Alembic migration: drop `project_records.environment`, add
  `project_records.project_resources` (Text)
- Update ORM model, Pydantic schemas, and CRUD passthrough in the engine
- Update frontend API types and the project detail read-only display
- Pre-fill new projects with a structured template when the field is empty

## Out of Scope

- `RunRecord.environment` — engine runtime field, leave untouched
- `execution_environments` — kept as-is (powers portfolio filter)
- `domainConfig.environments` — deferred
- Edit form for `project_resources` — handled in 001aw

## Acceptance Criteria

- `project_records.environment` column is removed from the database
- `project_records.project_resources` TEXT column exists and is nullable
- API reads and writes `project_resources` correctly
- Project detail view shows `project_resources` as a read-only textarea
- New project creation pre-fills the field with the environment-section template

## Test Expectations

- CRUD API: creating a project with `project_resources` text persists and
  returns it
- CRUD API: `environment` field no longer appears in project API responses
- Frontend: ProjectDetailView renders `project_resources` in a textarea element

## Pitfalls

- Do not touch `RunRecord.environment` or `RunCheckpoint.current_environment`
- The `project_resources` field may contain passwords and VPN credentials;
  do not log or emit it in error messages

## Commit

- `feat(001ax): replace project environment with project_resources text field`
