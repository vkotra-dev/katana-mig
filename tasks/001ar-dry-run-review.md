# Task 001ar — Dry-Run Review

**Plan:** `plans/2026-07-01-001ar-dry-run-review.md`

## Domain

- `docs/domain/api.md` — DryRunArtifact; dry_run_review run status; approve resumes run; push-back adds comment

## Scope

Add the dry-run review surface that central team operators use after the engine produces a dry-run pass:

- `DryRunArtifact` DB model (FK → `run_records`), Alembic migration (number TBD — check actual latest in `engine/migrations/versions/` at execution time)
- `GET /projects/{project_id}/runs/{run_id}/dry-run` — returns artifact or 404 `dry_run_artifact_not_found`
- `POST /projects/{project_id}/runs/{run_id}/dry-run/approve` — sets `artifact.status = "approved"`, `run.status = "queued"` (resumes engine pickup)
- `POST /projects/{project_id}/runs/{run_id}/dry-run/push-back` — sets `artifact.status = "pushed_back"`, `run.status` stays `"dry_run_review"`
- Frontend: review page at `/projects/[id]/runs/[run_id]/dry-run` with artifact display + approve/push-back buttons (central team only)

## Tasks (3)

1. **Backend** — `DryRunArtifact` model + migration; `management/dry_run.py` service; `routes/dry_run.py`; register in `app.py`; schemas in `api/schemas.py`.
2. **Frontend API helpers** — `getDryRunArtifact`, `approveDryRun`, `pushBackDryRun` in `web/lib/runs-api.ts`.
3. **Frontend review page** — `web/app/projects/[id]/runs/[run_id]/dry-run/page.tsx`.

## Success criteria

- GET returns artifact; 404 when none exists
- Approve sets run to `"queued"` so engine picks it up
- Push-back leaves run in `"dry_run_review"`; GET/approve/push-back are role-restricted (approve/push-back central team only)
- All tests pass

## Execution order

Execute after 001ak (run/artifact models). Migration number determined at
execution time. This is part of the feed/fiber/comment/AI priority stream and
should land before the later-phase delivery tickets.
