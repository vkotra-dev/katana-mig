# 001ar — Dry-Run Review

Implemented the dry-run review surface for central team operators:

- added `DryRunArtifact` to the ORM and created Alembic migration `0021_dry_run_artifact`
- added backend schemas, service logic, and routes for `GET /projects/{project_id}/runs/{run_id}/dry-run`,
  `POST /projects/{project_id}/runs/{run_id}/dry-run/approve`, and
  `POST /projects/{project_id}/runs/{run_id}/dry-run/push-back`
- registered the new router in `app.py`
- added backend tests covering artifact fetch, 404 handling, approve, push-back, and access control
- added `getDryRunArtifact`, `approveDryRun`, and `pushBackDryRun` helpers to `web/lib/runs-api.ts`
- added the dry-run review page and page tests at `/projects/[id]/runs/[run_id]/dry-run`
- documented the endpoints and response shape in `docs/domain/api.md`

Verification:

- `PYTHONPATH=/Users/vjkotra/projects/katana/.worktrees/001ar-dry-run-review/engine/src python -m pytest tests/test_dry_run_api.py -v`
- `npm test -- runs-api`
- `npm test -- dry-run/page`
- `npm test`
- `python -m alembic upgrade head`

Result:

- dry-run API tests passed
- frontend helper and page tests passed
- full web test suite passed
- Alembic upgrade applied successfully against the configured database
