# Design: AI Call Log

**Date:** 2026-07-10
**Status:** Approved

---

## Problem

Every AI adapter call (`codegen`, `mapping`, `source_analysis`, `lookup_mapping`) builds system and user prompts as Python strings, passes them to `AIAdapter.call()`, and discards them. The SQL bundle or mapping snapshot lands in the DB but there is no record of what the AI was told or what it returned. Debugging, auditing, and prompt tuning require reading source code.

---

## Goal

Capture every AI adapter call — system prompt, user prompt, raw model response, model ID — in a single queryable table. No individual caller needs to change. New adapters get logging automatically.

---

## Out of Scope

- Prompt template externalization (Jinja2 files) — separate task
- UI for browsing call logs — separate task (`001co` frontend)
- Replay / re-running from a logged prompt

---

## Data Model

### Migration 0032 — `ai_call_log`

```sql
CREATE TABLE ai_call_log (
    call_id           VARCHAR(36)   PRIMARY KEY,
    project_id        VARCHAR(36)   NOT NULL REFERENCES project_registry(project_id),
    call_type         VARCHAR(64)   NOT NULL,   -- 'codegen' | 'mapping' | 'source_analysis' | 'lookup_mapping'
    artifact_id       VARCHAR(36)   NULL,        -- ID of the artifact this call produced
    model_id          VARCHAR(128)  NOT NULL,
    system_prompt     TEXT          NOT NULL,
    user_prompt       TEXT          NOT NULL,
    raw_response      TEXT          NULL,        -- null if the call failed
    error_detail      TEXT          NULL,        -- null if the call succeeded
    called_at         DATETIME      NOT NULL
);

CREATE INDEX ix_ai_call_log_project_id ON ai_call_log (project_id);
CREATE INDEX ix_ai_call_log_artifact_id ON ai_call_log (artifact_id);
```

`artifact_id` is untyped (no FK) because it points to different tables depending on `call_type`. Nullable because logging happens before the artifact is written; callers back-fill it after the artifact is persisted.

---

## Backend

### `AIAdapter.call()` return value

The protocol currently returns only `T`. Extend it to also return the raw response string:

```python
class AICallResult(Generic[T]):
    parsed: T
    raw_response: str

class AIAdapter(Protocol):
    def call(self, system: str, user: str, response_model: type[T]) -> AICallResult[T]: ...
    @property
    def model_id(self) -> str: ...
```

All concrete adapters (`ClaudeAdapter`, `GeminiAdapter`, `MockAdapter`) return `AICallResult`.

### Logging helper

New function in `ai/logging.py`:

```python
def log_ai_call(
    db: Session,
    *,
    project_id: str,
    call_type: str,
    model_id: str,
    system: str,
    user: str,
    raw_response: str | None,
    error_detail: str | None = None,
    artifact_id: str | None = None,
) -> AICallLog:
```

Callers invoke this immediately after `adapter.call()` returns (or on exception). They pass `artifact_id=None` initially and back-fill it after the artifact row is committed.

### Callers that need updating

| File | Call type |
|---|---|
| `codegen/service.py` | `codegen` |
| `mapping/review.py` | `mapping` |
| `management/source_analysis.py` | `source_analysis` |
| `management/fibers.py` | `lookup_mapping` |
| `codegen/schema_analysis.py` | `source_analysis` |

Each caller: call adapter → log → persist artifact → back-fill `artifact_id`.

### ORM model

```python
class AICallLog(Base):
    __tablename__ = "ai_call_log"

    call_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project_registry.project_id"), nullable=False, index=True)
    call_type: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

---

## API

### `GET /projects/{project_id}/ai-calls`

Query params:
- `call_type` (optional filter)
- `artifact_id` (optional filter)

Response: `list[AICallLogResponse]`

```python
class AICallLogResponse(BaseModel):
    call_id: str
    call_type: str
    artifact_id: str | None
    model_id: str
    system_prompt: str
    user_prompt: str
    raw_response: str | None
    error_detail: str | None
    called_at: datetime
```

Role: `admin` or `central_team` only.

---

## Verification

1. Trigger Generate SQL → row appears in `ai_call_log` with `call_type='codegen'`, correct `project_id`, `artifact_id` back-filled
2. Trigger mapping AI → row appears with `call_type='mapping'`
3. Trigger source analysis → row appears with `call_type='source_analysis'`
4. AI call fails → row appears with `raw_response=null`, `error_detail` populated
5. `GET /projects/{id}/ai-calls` returns all rows for project; filters by `call_type` work
6. `project_stakeholder` role → 403 on the endpoint
