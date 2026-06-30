# 001o-project-crud Summary

- Added project CRUD schemas to `engine/src/migrations_engine/api/schemas.py`,
  including the nested `MigrationProjectConfig`, `ProjectResponse`, and create/
  update request models.
- Added `require_non_auditor`, `require_project_access`, and
  `get_project_initiation_user` so role checks stay at the API boundary.
- Implemented pure project business logic in
  `engine/src/migrations_engine/management/projects.py` for create, list, get,
  update, and archive.
- Wired `/projects` create/list/get/update/archive routes in
  `engine/src/migrations_engine/routes/projects.py`, while preserving the
  existing membership routes.
- Added integration coverage in `engine/tests/test_project_crud_api.py` for
  create/list/get/update/archive behavior, stakeholder scoping, auditor
  rejection, and definition cloning.
- Aligned `docs/domain/api.md` with the project config contract already defined
  in `docs/domain/project.md`.
- Verified with `py_compile`, the new project CRUD test file, and the full
  `engine/tests` suite using a local SQLite-backed test harness.
