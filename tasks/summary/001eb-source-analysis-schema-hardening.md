# Summary: 001eb — Source-Analysis AI Call Hardening

## What was built
`analyze_source_slice`'s AI call now has an explicit, rule-driven system prompt and a strict
response schema, plus a guard that catches column-name corruption (the production incident where
the model returned `claim_claim` for a column that was actually `claim_type`) at its source,
before it's ever persisted.

### Key changes
- **New system prompt**: explicit verbatim-column-name/order rules, type-inference criteria
  (ignore masked values), nullability and max-length rules, and a strict output contract.
- **`analysis_schemas.py`** (new module): `ColumnSchema`/`AnalysisResult` with `extra="forbid"`,
  a `nullable` bool-strict validator, and a `max_length` non-negative-and-not-bool validator
  (`isinstance(v, bool)` explicitly excluded — `bool` is an `int` subclass in Python, so the
  naive check would have silently accepted `max_length: true`).
- **`validate_against_header`**: wired in right after parsing, inside the adapter-call try block;
  strictly compares the AI's returned column names against the real `header_csv` (order and
  content). On mismatch, mutates the already-written `ai_call_log` row's `error_detail` (no
  duplicate row) and raises a distinct `source_analysis_header_mismatch` (422), separate from
  `ai_schema_validation_failed` (502) for a `ValidationError`.
- **Error handling**: `analyze_source_slice` previously had a single bare
  `except Exception: raise` with no `ValidationError`-specific handling at all; now distinguishes
  schema-validation failures, header-mismatch failures, and generic failures, each logged and
  translated into a proper `AuthApiError`.

## Verification
Spot-checked both `header_csv`-consuming test files before wiring in the guard — fixture
`ColumnSchema` names already matched their headers, so no existing test broke. New tests cover
the header-mismatch case (including the exact `claim_type`/`claim_claim` reproduction) and the
boolean-`max_length` rejection.
