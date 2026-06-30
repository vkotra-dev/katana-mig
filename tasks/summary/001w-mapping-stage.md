# Summary: Task 001w — Mapping Stage

## What changed

- Added a new mapping review service in `engine/src/migrations_engine/mapping/review.py`.
- Added `/projects/{project_id}/sources/{source_definition_id}/mapping` routes for propose, view, patch, approve, and reject.
- Extended the mapping API client with review-specific requests and error handling.
- Added a new mapping review page at `/projects/[id]/sources/[sourceId]/mapping`.
- Added backend and frontend Vitest coverage for the new review flow.
- Kept the approved mapping snapshot path used by runs unchanged.

## Verification

- `cd engine && KATANA_BOOTSTRAP_ADMIN_EMAIL=admin@example.com KATANA_BOOTSTRAP_ADMIN_PASSWORD=adminpass PYTHONPATH=src python -m pytest tests/test_mapping_review_api.py -q`
- `cd web && npm test -- lib/mapping-api.test.ts 'app/projects/[id]/sources/[sourceId]/mapping/page.test.tsx'`
- `cd web && npm run build`
- `git diff --check`

## Notes

- The review flow stays source-scoped in the UI but uses the project-scoped mapping snapshot model.
- Rejection now requires a comment and writes that reason into the audit trail.
