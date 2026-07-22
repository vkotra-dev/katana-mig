---
type: Task Plan
title: Expose destination_columns in the Mapping API + Fix Silent Codegen Skip
status: completed
---

# Task: 001em-expose-destination-columns-codegen-guard

## Context

Design spec: `docs/superpowers/specs/2026-07-22-unmapped-required-fields-callout-design.md`
(sections 1 and 2).

`MappingSnapshot.destination_columns` (added in migration `0036_destination_columns.py`) stores
each destination column's `name`/`destination_data_type`/`nullable` as a JSON list, populated by
`propose_mapping` (`mapping/proposal.py`) from the AI's `all_columns` output. Two problems:

1. **It's never returned by the API.** `MappingSnapshotResponse` (`api/schemas.py:578`) only has
   `destination_fields: list[str]` (names only, no `nullable` flag). Neither
   `snapshot_to_response` (`mapping/review_repository.py:103`) nor the two response-builders in
   `routes/mapping_snapshots.py` (`get_latest_mapping_snapshot`, `list_approved_mapping_snapshots`)
   set it. The frontend has no way to know which destination fields are required at all.
2. **`codegen/service.py`'s required-field check silently no-ops when the column is `NULL`.**
   `generate_codegen_artifact` (`codegen/service.py:78`) only runs the NOT-NULL check
   `if mapping_snapshot.destination_columns is not None:` — any `MappingSnapshot` row created
   before migration `0036` (or any row that otherwise never got `destination_columns` populated)
   silently skips validation and lets code generation proceed even if required fields are
   unmapped.

This task is backend-only. It is a prerequisite for `001en` (the frontend banner), which reads
`destination_columns` from the API.

## Requirements

1. Add a `MappingDestinationColumnResponse` Pydantic model (mirrors the JSON shape already stored
   in `MappingSnapshot.destination_columns`: `name`, `destination_data_type`, `nullable`) and a
   `destination_columns: list[MappingDestinationColumnResponse] | None = None` field on
   `MappingSnapshotResponse`.
2. Populate that new field in all three places a `MappingSnapshotResponse`/`MappingReviewResponse`
   is currently constructed:
   - `mapping/review_repository.py::snapshot_to_response`
   - `routes/mapping_snapshots.py::get_latest_mapping_snapshot`
   - `routes/mapping_snapshots.py::list_approved_mapping_snapshots`
3. `codegen/service.py::generate_codegen_artifact` must no longer silently skip the required-field
   check when `destination_columns is None`. It must raise a loud, actionable error instead (new
   error code `destination_metadata_missing`), distinct from the existing
   `unmapped_required_destination_fields` error (which still fires, unchanged, when
   `destination_columns` is present and a required field is genuinely unmapped).
4. Existing tests in `engine/tests/test_codegen_service_api.py` currently seed a `MappingSnapshot`
   with no `destination_columns` set (defaults to `NULL`) via the shared `_seed_project()` helper.
   Once requirement 3 lands, those tests will break (they'll start getting the new loud error
   instead of a successful codegen run) unless `_seed_project()` is updated to also populate
   `destination_columns` for its seeded snapshot. This update is in scope and required — do not
   leave those tests broken.

## Out of Scope

- No frontend changes at all (that's `001en`).
- No backfill migration for pre-existing rows with `destination_columns = NULL` — out of scope per
  the design spec; affected dev-box rows will be handled by discarding their feed directly, not by
  this task.
- No change to `mapping_hints` or the mapping-proposal AI flow.
- No change to the *shape* of `destination_fields` (the existing names-only list stays as-is,
  unchanged, for backward compatibility with any other consumer).

## Dependencies

None. Should land before `001en`, which depends on `destination_columns` being present in the API
response.
