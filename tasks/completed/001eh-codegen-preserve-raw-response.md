---
type: Task Plan
title: Preserve Raw AI Response on Validation Failure — Codegen Call Sites
status: ready
---

# Task: 001eh-codegen-preserve-raw-response

## Context
`001ec` fixed 5 AI call sites (`mapping/propose_mapping`, `source_analysis`, both `fibers.py`
calls, `lookup_mapping`) to catch `AIResponseValidationError` and log the actual raw response
text instead of `None` on a schema-validation failure. Two call sites were deliberately left out
of that task's scope: `codegen/service.py::generate_codegen_artifact` and
`codegen/schema_analysis.py::run_schema_analysis`. Both still have the identical gap — confirmed
by reading the current code, not assumed:

```python
# codegen/service.py:182-194, codegen/schema_analysis.py:57-69 — both identical shape
except Exception as exc:
    log_ai_call(db, ..., raw_response=None, error_detail=str(exc))
    raise
```

No `ValidationError`/`AIResponseValidationError`-specific handling at all — the adapter-layer fix
from `001ec` is universal (all 5 adapters raise `AIResponseValidationError` regardless of which
call site invokes them), so this is purely a two-call-site wiring gap, not new adapter work.

## Requirements

1. **`codegen/service.py::generate_codegen_artifact`** (`service.py:165-194`): add
   `except AIResponseValidationError as exc:` ahead of the existing `except Exception as exc:`,
   logging `raw_response=exc.raw_response` and `error_detail=f"ValidationError: {exc.original}"`
   (matching the convention from the other 5 sites), then bare `raise` — confirmed the current
   `except Exception` branch does a bare `raise` with no `AuthApiError` wrapping (the one
   `AuthApiError` in this function, at line 122, is an unrelated unmapped-required-fields check,
   not part of AI-call error handling) — so match that, exactly like `fibers.py`'s final,
   symmetric fix from 001ec.
2. **`codegen/schema_analysis.py::run_schema_analysis`** (`schema_analysis.py:?-69`): identical
   fix — its `except Exception` branch also does a bare `raise`, same convention to match.
3. **`db.commit()` before re-raising**: confirmed neither file's `except Exception` branch
   commits today (same gap as the 4 branches found missing it in `source_analysis.py`/`fibers.py`
   during 001ec's review) — `log_ai_call()` only does `db.add()` + `db.flush()`, never commits,
   and the FastAPI `get_db()` session rolls back anything uncommitted when an exception
   propagates out. Add `db.commit()` before the `raise` in both the new
   `AIResponseValidationError` branch and the existing generic `except Exception` fallback, in
   both files.
4. **No behavior change beyond this** — don't touch prompt content, adapter selection, or
   anything else in either file.

## Out of Scope
- Any change to the AI adapters themselves — already fixed universally in `001ec`.
- Migrating either file onto the `Prompt`/YAML template mechanism from `001ed` — codegen already
  has its own working Jinja2 template setup, not part of this task.
- Any other codegen behavior.

## Dependencies
None — `AIResponseValidationError` already exists in `ai/adapter.py` from `001ec`.
