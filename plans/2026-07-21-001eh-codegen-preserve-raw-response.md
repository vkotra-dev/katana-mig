# Plan: 001eh — Preserve Raw AI Response on Validation Failure (Codegen)

## Task and Domain links

- Task: `tasks/001eh-codegen-preserve-raw-response.md`
- Domain: none — internal error-handling completeness, no API/UI change

## Current State

- `codegen/service.py::generate_codegen_artifact` (`service.py:165-194`): bare
  `except Exception as exc: log_ai_call(..., raw_response=None, error_detail=str(exc)); raise` —
  no `db.commit()`, no `AIResponseValidationError` handling. The function's one `AuthApiError`
  (line 122) is an unrelated unmapped-required-fields check outside the AI-call try/except.
- `codegen/schema_analysis.py::run_schema_analysis` (`schema_analysis.py:44-69`): identical shape.
- `AIResponseValidationError` (`ai/adapter.py`, from `001ec`) is already raised by all 5 adapters
  universally — no adapter-layer change needed here, purely a call-site wiring gap.
- `log_ai_call()` (`ai/logging.py`) only does `db.add()` + `db.flush()`, never commits — confirmed
  during `001ec`'s review that `get_db()`'s session rolls back anything uncommitted when an
  exception propagates through a route handler.

## Objective

1. Add `except AIResponseValidationError as exc:` to both functions, ahead of the existing
   `except Exception`, logging `raw_response=exc.raw_response` and
   `error_detail=f"ValidationError: {exc.original}"`.
2. Add `db.commit()` before `raise` in both the new branch and the existing `except Exception`
   fallback, in both files.
3. No other behavior change.

## Out of Scope

- Adapter changes — already done in 001ec.
- Migrating either file onto the `Prompt`/YAML mechanism from 001ed — codegen's Jinja2 templates
  stay as-is.
- Any other codegen error path.

## Blast Radius

- `engine/src/migrations_engine/codegen/service.py` (edited)
- `engine/src/migrations_engine/codegen/schema_analysis.py` (edited)
- `engine/tests/test_codegen_service.py` (or equivalent — confirm actual test filename) (edited —
  new test)
- `engine/tests/test_schema_analysis.py` (or equivalent) (edited — new test)
- No DB migration, no API/frontend change.

## File Changes

**`engine/src/migrations_engine/codegen/service.py`**
- Import `AIResponseValidationError` from `..ai.adapter` near the existing `log_ai_call`/
  `backfill_artifact_id` import at line 163.
- Replace lines 182-194:
  ```python
  except AIResponseValidationError as exc:
      log_ai_call(
          db,
          project_id=project_id,
          feature="codegen",
          call_type="codegen",
          model_id=adapter.model_id,
          system=system_prompt,
          user=user_prompt,
          raw_response=exc.raw_response,
          error_detail=f"ValidationError: {exc.original}",
      )
      db.commit()
      raise
  except Exception as exc:
      log_ai_call(
          db,
          project_id=project_id,
          feature="codegen",
          call_type="codegen",
          model_id=adapter.model_id,
          system=system_prompt,
          user=user_prompt,
          raw_response=None,
          error_detail=str(exc),
      )
      db.commit()
      raise
  ```

**`engine/src/migrations_engine/codegen/schema_analysis.py`**
- Same pattern: import `AIResponseValidationError`, add the new branch ahead of the existing one,
  `db.commit()` added to both.

## Tests

- One test per file: mock the adapter to raise `AIResponseValidationError`, assert the resulting
  `ai_call_log` row has `raw_response` populated (not `None`) — using the `db.rollback()`
  verification technique from `001ec` (call the service function with a manually-managed session,
  then `db.rollback()` before querying, so the test only passes if `db.commit()` genuinely ran).
- Existing test suites for both files rerun unchanged — no behavior change to the success path or
  to non-validation failures.

## Verification

- `ruff check` / `mypy --strict` clean on both files.
- Manually trigger a schema-validation failure (e.g. a fixture that violates `extra="forbid"` on
  `GeneratedSQL`/`DDLAnalysisResult`) and confirm the resulting `ai_call_log` row's `raw_response`
  contains the actual invalid JSON.

## Pitfalls

- Same ordering risk as `001ec`: `except AIResponseValidationError` must come *before* `except
  Exception` in both files — Python matches clauses top-to-bottom, and `Exception` would
  otherwise shadow the more specific branch.
- Don't wrap either branch in `AuthApiError` — confirmed neither function does that today for AI
  failures; match the existing bare-`raise` convention rather than introducing a third error-
  handling style into the codebase.

## Commit

Own commit. No dependency on any other in-flight task.
