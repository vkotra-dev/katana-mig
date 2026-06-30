# Summary 001v — Source Analysis

Implemented source analysis for approved source slices:

- Added `SourceSchemaArtifact` and `SourceValueSummary` ORM models plus the `0011_source_analysis_artifacts` Alembic migration.
- Added source-analysis response schemas for the API layer.
- Added `docs/domain/source-model.md` coverage for the 200-row analysis sample cap and the 500-distinct-value summary cap.
- Added `management/source_analysis.py` with:
  - latest-approved-slice selection
  - masked sample prompt assembly
  - `pii_review` adapter invocation
  - schema artifact persistence
  - value-summary persistence
  - source-analysis audit logging
- Added `/projects/{project_id}/sources/{source_definition_id}/analyze`
- Added `/projects/{project_id}/sources/{source_definition_id}/schema`
- Added `/projects/{project_id}/sources/{source_definition_id}/value-summary`
- Registered the new analysis router in the app.
- Added unit and integration coverage for the model, service, and API layers.

Verification:

- `source ../.venv/bin/activate && ruff check src/migrations_engine/management/source_analysis.py src/migrations_engine/routes/analysis.py src/migrations_engine/app.py tests/sqlite_test_support.py tests/test_source_analysis_models.py tests/test_source_analysis_service.py tests/test_source_analysis_api.py`
- `source ../.venv/bin/activate && PYTHONPATH=src pytest tests/test_source_analysis_models.py tests/test_source_analysis_service.py tests/test_source_analysis_api.py -q`
- `source ../.venv/bin/activate && PYTHONPATH=src python -m alembic upgrade head --sql >/tmp/katana_001v_migration.sql`

Result:

- 7 test cases passed across the source-analysis coverage
- Alembic rendered the full migration chain through `0011_source_analysis_artifacts`
