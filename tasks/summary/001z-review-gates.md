# Summary 001z — Review Gates

Implemented the two review gates called for by the task and aligned them to the
authoritative UI contract.

- Added backend gate schemas, service logic, and FastAPI routes.
- Stored gate decisions in `RunRecord.approvals` and updated run status/stage on
  approve/reject.
- Added a duplicate-approval guard so an already approved gate returns a structured
  422 instead of overwriting the record.
- Added gate evidence endpoints for Gate 1 domain coverage and Gate 2 lookup
  review.
- Added the new Gate 1 and Gate 2 UI screens plus a shared gates API client.
- Added backend and web tests for the new flow.

Verification:

- `KATANA_BOOTSTRAP_ADMIN_EMAIL=admin@example.com KATANA_BOOTSTRAP_ADMIN_PASSWORD=admin-password PYTHONPATH=engine/src pytest engine/tests/test_gates_api.py -q`
- `KATANA_BOOTSTRAP_ADMIN_EMAIL=admin@example.com KATANA_BOOTSTRAP_ADMIN_PASSWORD=admin-password PYTHONPATH=engine/src pytest engine/tests/test_runs_api.py -q`
- `KATANA_BOOTSTRAP_ADMIN_EMAIL=admin@example.com KATANA_BOOTSTRAP_ADMIN_PASSWORD=admin-password PYTHONPATH=engine/src pytest engine/tests/test_source_slice_approval_api.py -q`
- `cd web && npm test`
