# 001ap — Lookup Delta CR Review Screen

Implemented lookup-delta change-request review end to end:

- added `ChangeRequestPayload`, `ChangeRequestSummary`, `ChangeRequestDetail`,
  `ChangeRequestResolveRequest`, and `ChangeRequestResolveResponse` backend schemas
- created `management/change_requests.py` with list/get/resolve service logic
- added `routes/change_requests.py` and registered it in `app.py`
- resolve now:
  - requires a `project_stakeholder`
  - patches the `LookupValueMap`
  - mints a new approved `LookupSnapshot`
  - queues the paused `RunRecord`
  - closes the change request in one transaction
- added backend tests covering auth, list/detail, resolve success, `cr_not_open`,
  and `cr_wrong_type`
- added `web/lib/change-requests-api.ts` and tests for list/get/resolve helpers
- created the `/projects/[id]/change-requests/[crId]` review page and page test
- updated `docs/domain/api.md` with the new change-request endpoints

Verification:

- `source /Users/vjkotra/projects/katana/engine/.env && source /Users/vjkotra/projects/katana/.venv/bin/activate && KATANA_BOOTSTRAP_ADMIN_EMAIL=admin@example.com KATANA_BOOTSTRAP_ADMIN_PASSWORD=pass12345 PYTHONPATH=engine/src python -m pytest engine/tests/test_change_requests_api.py -q`
- `source /Users/vjkotra/projects/katana/engine/.env && source /Users/vjkotra/projects/katana/.venv/bin/activate && KATANA_BOOTSTRAP_ADMIN_EMAIL=admin@example.com KATANA_BOOTSTRAP_ADMIN_PASSWORD=pass12345 PYTHONPATH=engine/src python -m pytest engine/tests/test_change_requests_api.py engine/tests/test_runs_api.py -q`
- `cd web && npm test -- --run components/projects/__tests__/KnowledgeFreezePanel.test.tsx components/projects/__tests__/ProjectDetailView.test.tsx lib/runs-api.test.ts lib/change-requests-api.test.ts app/projects/[id]/change-requests/[crId]/page.test.tsx`
- `cd web && npm test -- --run`

Result:

- backend tests: `9 passed` and `11 passed`
- focused web tests: `25 passed`
- full web suite: `196 passed`
