# Task: 001ck — Copybook Unmasked Storage + Approval Toggle

## Status
Ready

## Problem

`fixed_intake.py` calls `mask_row()` before writing to `FeedSliceRow.row_csv`, so the original copybook values are destroyed at ingestion. This creates three downstream problems:

1. **AI quality degraded** — `source_analysis.py` and the execution `inner_loop.py` both read `row_csv` directly. For copybook feeds they see `***` instead of real values, producing lower-quality mapping proposals and lookup value extraction.
2. **Approval toggle impossible** — there is no stored original to show.
3. **Inconsistency with CSV feeds** — CSV intake stores raw values; `mask_row` is never called. Copybook feeds have a different (worse) data model for no structural reason.

## Root Cause

`mask_row` is called at line 48 of `fixed_intake.py` before appending to `row_csv_rows`.

`masking_policy` on `FeedSlice` records **field-name** PII only (via `is_pii_field`). Value-pattern PII (via `_matches_pii_pattern`) is not stored there — it is a per-value check. So display-time masking requires two passes:
- Check `masking_policy.masked_fields` (or re-run `is_pii_field`) for field-name matches
- Re-run `_matches_pii_pattern` on the raw cell value for pattern matches

`masking_policy` alone is not a complete display instruction; it is a field-name hint. Both checks must run at read time.

## Solution

### Part A — Store unmasked in `row_csv` (one-line backend change)

**File:** `engine/src/migrations_engine/intake/fixed_intake.py`

Replace:
```python
row_csv_rows.append((row_index, mask_row(header_values, values)))
```
with:
```python
row_csv_rows.append((row_index, _dump_csv_row(values)))
```

`_dump_csv_row` already exists in the same file — same `csv.writer` encoding as `mask_row`, no masking applied.

`masking_policy` continues to be populated via the `masked_fields` argument to `_create_source_slice` — it now serves as the display-layer instruction rather than a post-ingestion record.

No schema change. No migration.

### Part B — Display-time masking endpoint

Add a new endpoint:

```
GET /projects/{project_id}/sources/{source_id}/slices/{slice_id}/rows?masked=true
```

No existing route serves slice rows with masking control, so this is a new route in `routes/feeds.py` (or `routes/slices.py` if that file exists).

Behaviour:
- `masked=true` (default, all roles): reads `FeedSlice.header_csv` to get field names, then for each `FeedSliceRow.row_csv` applies both checks:
  - `is_pii_field(header)` — field-name check
  - `_matches_pii_pattern(value)` — value-pattern check on the raw unmasked value
  Returns the row with matching cells replaced by `***`.
- `masked=false` (admin and pm only — 403 for other roles): returns `row_csv` verbatim.

The endpoint must join `FeedSlice` (for `header_csv`) and `FeedSliceRow` (for `row_csv`) — they are separate rows. Header position drives which check applies to which cell.

### Part C — Approval screen toggle (frontend)

In the feed slice approval card (001cc):

- Default view: masked (applies to all roles including admin)
- "Show original" toggle: visible only when `role === "admin" || role === "pm"`
- On toggle → re-fetches rows with `?masked=false`
- Toggle state resets on slice change

## Downstream Impact

| Consumer | Before (masked at ingestion) | After (unmasked in `row_csv`) |
|---|---|---|
| Source analysis / AI mapping | Sees `***` for PII fields | Sees real values → better mapping quality |
| Lookup value extraction | `***` entries in lookup map | Real distinct values |
| Reconciliation key lookup | Masked key → miss on match | Real key → correct matching |
| Approval screen (default) | Masked (via stored `***`) | Masked (via display-time `mask_row`) |
| Approval screen (admin toggle) | Not possible | Real values visible |
| CSV feeds | Unchanged — already unmasked | Unchanged |

## Files Changed

**Backend:**
- `engine/src/migrations_engine/intake/fixed_intake.py` — remove `mask_row` call at ingestion
- `engine/src/migrations_engine/routes/feeds.py` — new `GET .../slices/{slice_id}/rows` endpoint with `masked` query param and role gate; joins `FeedSlice.header_csv` with `FeedSliceRow.row_csv`

**Frontend:**
- `web/app/projects/[id]/feeds/[feedId]/page.tsx` — "Show original" toggle in approval card, PM/admin only

## Out of Scope

- Backfilling existing `row_csv` rows that already contain `***` (operational concern)
- Quasi-identifier combination scoring (separate task)
- Deterministic string scrambling (separate task)

## Verification

1. Upload a copybook feed → check `FeedSliceRow.row_csv` in DB — values should be unmasked
2. Check `FeedSlice.masking_policy` — still lists PII field names
3. Default approval view shows masked values (same as before for the approver)
4. Admin toggles "Show original" → real values appear
5. PM toggles "Show original" → real values appear
6. `central_team` and `project_stakeholder` have no toggle option
7. Trigger AI analysis on the feed — mapping quality improves for name/dob fields
8. All existing backend tests pass
