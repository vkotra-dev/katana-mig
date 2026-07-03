# 001ai — Knowledge-Freeze History Panel

Implemented the project overview freeze-history panel end to end:

- added `KnowledgeFreezeRecord` to the backend API schema
- added `list_knowledge_freezes` to the run execution service
- exposed `GET /projects/{project_id}/knowledge-freezes` on a project-level router
- added focused backend tests for filtering, ordering, empty state, and auth
- added `KnowledgeFreezeRecord` and `listKnowledgeFreezes` to the web runs API
- created the `KnowledgeFreezePanel` component with loading, empty, error, and table states
- mounted the panel in the project overview tab alongside `ProjectDetailView`

Verification:

- `source /Users/vjkotra/projects/katana/engine/.env && source /Users/vjkotra/projects/katana/.venv/bin/activate && KATANA_BOOTSTRAP_ADMIN_EMAIL=admin@example.com KATANA_BOOTSTRAP_ADMIN_PASSWORD=pass12345 PYTHONPATH=engine/src python -m pytest engine/tests/test_freeze_history_api.py engine/tests/test_runs_api.py -q`
- `cd web && npm test -- --run components/projects/__tests__/KnowledgeFreezePanel.test.tsx components/projects/__tests__/ProjectDetailView.test.tsx lib/runs-api.test.ts`

Result:

- backend tests: `6 passed`
- web tests: `14 passed`
