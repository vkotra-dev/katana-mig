# Summary: 001co — AI Call Log

## What was built

Implemented a comprehensive AI call logging system to capture the inputs and outputs of every LLM interaction across the engine.

### Backend Updates

| Component | Details |
|---|---|
| **Database Schema** | Created migration `0033` (after fixing the sequence from the plan) to add `ai_call_log` table with FK `project_id`, `call_type`, `model_id`, `system_prompt`, `user_prompt`, `raw_response`, and `error_detail`. |
| **Adapter Updates** | Updated the `AIAdapter` protocol to return a new `AICallResult[T]` dataclass that carries both the parsed Pydantic model (`.parsed`) and the raw string (`.raw_response`). Updated Anthropic, OpenAI, Gemini, Ollama, and Mock adapters to return this result. |
| **Logging Helpers** | Created `log_ai_call` and `backfill_artifact_id` in `engine/src/migrations_engine/ai/logging.py`. |
| **Call Site Injection** | Wired the logging logic into `codegen/service.py`, `mapping/review.py`, `management/source_analysis.py`, `management/fibers.py`, and `codegen/schema_analysis.py`, wrapping calls in `try/except` to ensure `error_detail` is logged on failures. |
| **API Endpoint** | Created `GET /projects/{project_id}/ai-calls` (restricted to admin/central team) with optional filtering by `call_type` and `artifact_id`. |
| **Tests** | Updated test fake adapters (`test_codegen_service_api.py`, `test_fiber_ai_flow.py`, `test_lookup_fiber_api.py`, `test_mapping_review_api.py`, `test_schema_analysis_api.py`, `test_source_analysis_api.py`, `test_source_analysis_service.py`, `test_impact_review_api.py`) to correctly return `AICallResult` mocks and assign `model_id`. |

## Deviations from plan

- **Migration ID**: Used `0033` instead of `0032` because `0032` was already taken by `codegen_prompts_visibility.py`.
- **Impact Analysis**: Updated the `_call_impact_ai` call site in `management/impact.py` to extract `.parsed` from the `AICallResult`, but did not inject `log_ai_call` because it does not operate with `db` or `project_id` in scope (and wasn't part of the 5 targeted files in the plan).

## Verification

All 130 tests pass.
