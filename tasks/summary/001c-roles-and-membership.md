# 001c-roles-and-membership Summary

- Implemented user CRUD at `/users` with soft delete (`soft_deleted_at`, session
  bump, excluded from list).
- Implemented project membership at `/projects/{id}/members` with role-aware access
  checks via `user_has_project_access()`.
- Added platform audit events for user and membership mutations.
- Added `engine/tests/test_management_api.py` (4 tests, all passing).
