# Task
- [001j-engine-fastapi-foundation](/Users/vjkotra/projects/katana/tasks/001j-engine-fastapi-foundation.md)

# Domain
- [governance.md](/Users/vjkotra/projects/katana/docs/domain/governance.md)
- [auth.md](/Users/vjkotra/projects/katana/docs/domain/auth.md)
- [management.md](/Users/vjkotra/projects/katana/docs/domain/management.md)
- [project.md](/Users/vjkotra/projects/katana/docs/domain/project.md)
- [runs.md](/Users/vjkotra/projects/katana/docs/domain/runs.md)
- [source-model.md](/Users/vjkotra/projects/katana/docs/domain/source-model.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)

## Current State
The repository now has a FastAPI scaffold in `engine/` and a first-pass set of
SQLAlchemy models and Alembic migrations, but the work is not yet formally
tracked by a task/plan pair.

## Objective
Bring the backend scaffold under the task workflow and make the first migration
set explicit and recoverable from task, plan, and summary artifacts.

## Out of Scope
- Implementing routes or business logic
- Adding new tables beyond the current first-pass backend set
- UI work

## Blast Radius
- `tasks/TASK_INDEX.md`
- `tasks/001j-engine-fastapi-foundation.md`
- `plans/2026-06-29-001j-engine-fastapi-foundation.md`

## File Changes
- Add task file
- Add plan file
- Update task index

## Tests
- No runtime tests are expected from the docs-only task tracking update.

## Verification
- Confirm the task index includes the new backend task
- Confirm the plan references the correct domain pages

## Pitfalls
- Do not expand this task to include route implementation
- Do not mix in UI or auth endpoint behavior

## Commit
- `docs(task): add backend foundation task and plan`
