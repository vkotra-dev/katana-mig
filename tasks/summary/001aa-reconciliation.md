# Summary: Task 001aa — Reconciliation

## What changed

- Added reconciliation persistence models for reports and lineage rows.
- Added the reconciliation API service, routes, and registration in the engine.
- Added Alembic migration `0015_reconciliation_tables`.
- Added backend tests covering trigger, access control, lineage drill-down, orphaned mapped rows, and export.
- Added the reconciliation UI API helper, the `/runs/[id]/reconciliation` page, and page tests.
- Updated [`docs/domain/runs.md`](/Users/vjkotra/projects/katana/docs/domain/runs.md) to describe the reconciliation report and lineage evidence schema.

## Verification

- `cd engine && alembic upgrade head`
- `PYTHONPATH=engine/src KATANA_BOOTSTRAP_ADMIN_EMAIL=admin@example.com KATANA_BOOTSTRAP_ADMIN_PASSWORD=pass12345 pytest engine/tests/test_reconciliation_api.py -q`
- `cd web && npm exec -- tsc --noEmit`
- `cd web && npm exec -- vitest run 'app/runs/[id]/reconciliation/page.test.tsx' 'app/dashboard/page.test.tsx'`

## Notes

- The Alembic chain required shortening two revision IDs and widening `version_num` for fresh installs so MySQL would accept the migration history.
- The pre-existing `.claude/settings.local.json` change was left untouched.
