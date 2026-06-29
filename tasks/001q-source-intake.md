# 001q-source-intake

## Domain

- [source-model.md](../docs/domain/source-model.md)
- [api.md](../docs/domain/api.md)
- [governance.md](../docs/domain/governance.md)

## Objective

Add source contract declaration and data file upload for CSV and fixed-length
record sources. All source data normalizes to masked CSV rows at intake time and
is stored in a new `source_slice_rows` table. Source management lives on the
project detail page as a Sources tab — it is never part of project creation.

## Scope

- Alembic migration `0008` — add `copybook_text`, `header_csv`, `source_slice_rows` table;
  add `status`, `approval_rejection_reason`, `parse_warnings`, `file_storage_path` to `source_slices`
- `SourceSliceRow` ORM model
- `SourceContractCreateRequest`, `SourceContractResponse`, `SourceSliceResponse` schemas
- `intake/masking.py` — PII field detection and CSV row masking
- `intake/cobol_parser.py` — COBOL copybook parser → `FieldDef` list
- `intake/csv_intake.py` — parse CSV, apply masking, store `SourceSliceRow` records
- `intake/fixed_intake.py` — use layout to slice fixed-width records → CSV rows
- `routes/sources.py` — 7 endpoints (declare, list, get, copybook upload, slice upload, list slices, get slice)
- `web/lib/sources-api.ts` and tests
- `web/components/projects/SourceList.tsx` and `AddSourceDialog.tsx` and tests
- Sources tab wired into `web/app/projects/[id]/page.tsx`

## Out of Scope

- Source analysis, domain object mapping, AI-derived layouts
- PII masking policy configuration (default heuristic only)
- Approval workflow for slices (stored as `pending_approval`; gate is separate)
- Database source download
- Source intake during project creation

## Acceptance Criteria

- CSV upload: headers parsed, PII fields masked, rows stored as `SourceSliceRow` records;
  slice `status` set to `"pending_approval"`, `file_storage_path` written, `parse_warnings` populated
- Fixed-length upload: requires copybook uploaded first; returns `409 layout_not_ready` otherwise
- COBOL parser extracts field name, offset, width, picture, type hint; skips `FILLER`
- Masking replaces PII field values with `***` before any row is stored
- `SourceList` shows Add Source button for `central_team` only
- `AddSourceDialog` is a two-step flow: declare → upload; fixed-length adds a copybook step
- Migration `0008` applies cleanly on top of `0007`

## Test Expectations

- `test_masking.py` — `is_pii_field` detects normalized PII names; `mask_row` replaces PII values
- `test_cobol_parser.py` — correct offsets, FILLER excluded but counted in offset, picture → type mapping
- `test_intake_services.py` — CSV and fixed-length ingest produce correct rows in real SQLite DB
- `test_source_intake_api.py` — contract CRUD, copybook upload, CSV and fixed-length slice upload, `409` on missing layout, `404` on missing contract
- Web: `SourceList` renders rows and gates Add Source by role; `AddSourceDialog` advances through steps and calls API

Plan: plans/2026-06-29-001q-source-intake.md
