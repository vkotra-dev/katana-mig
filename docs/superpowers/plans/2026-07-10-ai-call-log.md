# AI Call Log — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture every AI adapter call (system prompt, user prompt, raw response, model ID) in a single `ai_call_log` table, with no per-caller boilerplate and automatic logging for future adapters.

**Architecture:** Extend `AIAdapter.call()` to return `AICallResult[T]` (parsed + raw). A `log_ai_call()` helper writes to `ai_call_log`. Each of the 5 callers logs immediately after the adapter call and back-fills `artifact_id` after the artifact is persisted. One new `GET` endpoint exposes call logs per project.

**Tech Stack:** Python/FastAPI, SQLAlchemy + Alembic (MySQL), existing `AIAdapter` protocol.

## Global Constraints

- Migration `0032` — `down_revision = "0031"` (after `0031_transformation_instructions`)
- `artifact_id` is untyped (no FK) — points to different tables per `call_type`
- Role guard on API endpoint: `admin` or `central_team` only
- Logging must not swallow adapter exceptions — log then re-raise

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `engine/migrations/versions/0032_ai_call_log.py` | Create | Add `ai_call_log` table |
| `engine/src/migrations_engine/db/models.py` | Modify | Add `AICallLog` ORM model |
| `engine/src/migrations_engine/ai/adapter.py` | Modify | Add `AICallResult` dataclass, update `AIAdapter` protocol |
| `engine/src/migrations_engine/ai/claude_adapter.py` (or equivalent) | Modify | Return `AICallResult` |
| `engine/src/migrations_engine/ai/gemini_adapter.py` | Modify | Return `AICallResult` |
| `engine/src/migrations_engine/ai/mock_adapter.py` | Modify | Return `AICallResult` |
| `engine/src/migrations_engine/ai/logging.py` | Create | `log_ai_call()` helper |
| `engine/src/migrations_engine/api/schemas.py` | Modify | Add `AICallLogResponse` |
| `engine/src/migrations_engine/management/ai_calls.py` | Create | `list_ai_calls()` management function |
| `engine/src/migrations_engine/routes/ai_calls.py` | Create | `GET /projects/{id}/ai-calls` route |
| `engine/src/migrations_engine/app.py` | Modify | Register `ai_calls` router |
| `engine/src/migrations_engine/codegen/service.py` | Modify | Log codegen adapter call |
| `engine/src/migrations_engine/mapping/review.py` | Modify | Log mapping adapter call |
| `engine/src/migrations_engine/management/source_analysis.py` | Modify | Log source analysis adapter call |
| `engine/src/migrations_engine/management/fibers.py` | Modify | Log lookup mapping adapter call |
| `engine/src/migrations_engine/codegen/schema_analysis.py` | Modify | Log schema analysis adapter call |

---

### Task 1: Migration and ORM model

**Files:**
- Create: `engine/migrations/versions/0032_ai_call_log.py`
- Modify: `engine/src/migrations_engine/db/models.py`

**Interfaces:**
- Produces: `AICallLog` ORM model with fields: `call_id`, `project_id`, `call_type`, `artifact_id`, `model_id`, `system_prompt`, `user_prompt`, `raw_response`, `error_detail`, `called_at`

- [ ] **Step 1: Verify migration chain**

```bash
ls engine/migrations/versions/ | sort | tail -3
```

Expected: `0031_transformation_instructions.py` is the latest.

- [ ] **Step 2: Create migration 0032**

Create `engine/migrations/versions/0032_ai_call_log.py`:

```python
"""add ai_call_log table

Revision ID: 0032
Revises: 0031
"""
from alembic import op
import sqlalchemy as sa

revision = "0032"
down_revision = "0031"


def upgrade() -> None:
    op.create_table(
        "ai_call_log",
        sa.Column("call_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("project_registry.project_id"), nullable=False),
        sa.Column("call_type", sa.String(64), nullable=False),
        sa.Column("artifact_id", sa.String(36), nullable=True),
        sa.Column("model_id", sa.String(128), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt", sa.Text(), nullable=False),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("called_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_call_log_project_id", "ai_call_log", ["project_id"])
    op.create_index("ix_ai_call_log_artifact_id", "ai_call_log", ["artifact_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_call_log_artifact_id", table_name="ai_call_log")
    op.drop_index("ix_ai_call_log_project_id", table_name="ai_call_log")
    op.drop_table("ai_call_log")
```

- [ ] **Step 3: Add `AICallLog` ORM model**

In `engine/src/migrations_engine/db/models.py`, add after `AuditEvent`:

```python
class AICallLog(Base):
    __tablename__ = "ai_call_log"

    call_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_registry.project_id"), nullable=False, index=True
    )
    call_type: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4: Run migration**

```bash
cd engine && alembic upgrade head
```

Expected: `Running upgrade 0031 -> 0032` with no errors.

- [ ] **Step 5: Commit**

```bash
git add engine/migrations/versions/0032_ai_call_log.py \
        engine/src/migrations_engine/db/models.py
git commit -m "feat: add ai_call_log table (migration 0032)"
```

---

### Task 2: Extend `AIAdapter` protocol and concrete adapters

**Files:**
- Modify: `engine/src/migrations_engine/ai/adapter.py`
- Modify: all concrete adapter files (check with `grep -rn "class.*Adapter" engine/src/migrations_engine/ai/`)

**Interfaces:**
- Produces: `AICallResult[T]` dataclass with `parsed: T` and `raw_response: str`; updated `AIAdapter.call()` returning `AICallResult[T]`

- [ ] **Step 1: Add `AICallResult` and update protocol in `adapter.py`**

Replace the current content of `engine/src/migrations_engine/ai/adapter.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class AICallResult(Generic[T]):
    parsed: T
    raw_response: str


class AIAdapter(Protocol):
    def call(self, system: str, user: str, response_model: type[T]) -> AICallResult[T]:
        """Send a prompt and return parsed model + raw response string."""

    @property
    def model_id(self) -> str:
        """The model identifier used for this adapter."""


class AICallError(Exception):
    """Raised when the AI provider returns an error."""


class ConfigurationError(Exception):
    """Raised when a required config value is missing, invalid, or unrecognised."""
```

- [ ] **Step 2: Find all concrete adapters**

```bash
grep -rn "def call" engine/src/migrations_engine/ai/
```

Read each adapter file to understand how it currently calls the provider and returns.

- [ ] **Step 3: Update each concrete adapter to return `AICallResult`**

For each adapter, capture the raw provider response string before parsing and wrap the return:

Pattern for any adapter:

```python
def call(self, system: str, user: str, response_model: type[T]) -> AICallResult[T]:
    # ... existing provider call ...
    raw = <the raw string from the provider>
    parsed = response_model.model_validate_json(raw)   # or however it currently parses
    return AICallResult(parsed=parsed, raw_response=raw)
```

For `MockAdapter`, `raw_response` can be `response_model(...).model_dump_json()`.

- [ ] **Step 4: Fix all existing call sites to unpack `.parsed`**

```bash
grep -rn "adapter\.call\|adapter\.call(" engine/src/migrations_engine/ | grep -v "def call"
```

Each existing call site currently does:
```python
result = adapter.call(system=..., user=..., response_model=...)
```

Update to:
```python
result = adapter.call(system=..., user=..., response_model=...)
# use result.parsed where previously used result directly
```

- [ ] **Step 5: Run existing tests**

```bash
cd engine && python -m pytest tests/ -v -x
```

Expected: all tests pass with no `AttributeError` on adapter return values.

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/ai/
git commit -m "feat: extend AIAdapter to return AICallResult with raw_response"
```

---

### Task 3: Logging helper and `ai_calls` management module

**Files:**
- Create: `engine/src/migrations_engine/ai/logging.py`
- Create: `engine/src/migrations_engine/management/ai_calls.py`

**Interfaces:**
- Produces:
  - `log_ai_call(db, *, project_id, call_type, model_id, system, user, raw_response, error_detail, artifact_id) -> AICallLog`
  - `backfill_artifact_id(db, call_id, artifact_id) -> None`
  - `list_ai_calls(db, project_id, call_type, artifact_id) -> list[AICallLog]`

- [ ] **Step 1: Create `engine/src/migrations_engine/ai/logging.py`**

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import AICallLog
from ..db.utils import new_id


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
    entry = AICallLog(
        call_id=new_id(),
        project_id=project_id,
        call_type=call_type,
        model_id=model_id,
        system_prompt=system,
        user_prompt=user,
        raw_response=raw_response,
        error_detail=error_detail,
        artifact_id=artifact_id,
    )
    db.add(entry)
    db.flush()
    return entry


def backfill_artifact_id(db: Session, call_id: str, artifact_id: str) -> None:
    entry = db.get(AICallLog, call_id)
    if entry is not None:
        entry.artifact_id = artifact_id
        db.flush()
```

- [ ] **Step 2: Write a unit test**

Create `engine/tests/ai/test_logging.py`:

```python
from migrations_engine.ai.logging import log_ai_call, backfill_artifact_id
from migrations_engine.db.models import AICallLog


def test_log_ai_call_creates_row(db_session, project_id):
    entry = log_ai_call(
        db_session,
        project_id=project_id,
        call_type="codegen",
        model_id="claude-sonnet-4-6",
        system="You are a SQL generator.",
        user="Generate staging DDL.",
        raw_response='{"staging_table_ddl": "CREATE TABLE ..."}',
    )
    db_session.commit()
    row = db_session.get(AICallLog, entry.call_id)
    assert row.call_type == "codegen"
    assert row.artifact_id is None


def test_backfill_artifact_id(db_session, project_id):
    entry = log_ai_call(
        db_session,
        project_id=project_id,
        call_type="codegen",
        model_id="claude-sonnet-4-6",
        system="sys",
        user="usr",
        raw_response="{}",
    )
    db_session.commit()
    backfill_artifact_id(db_session, entry.call_id, "artifact-uuid-123")
    db_session.commit()
    row = db_session.get(AICallLog, entry.call_id)
    assert row.artifact_id == "artifact-uuid-123"
```

- [ ] **Step 3: Create `engine/src/migrations_engine/management/ai_calls.py`**

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import AICallLog


def list_ai_calls(
    db: Session,
    *,
    project_id: str,
    call_type: str | None = None,
    artifact_id: str | None = None,
) -> list[AICallLog]:
    q = select(AICallLog).where(AICallLog.project_id == project_id)
    if call_type is not None:
        q = q.where(AICallLog.call_type == call_type)
    if artifact_id is not None:
        q = q.where(AICallLog.artifact_id == artifact_id)
    return list(db.scalars(q.order_by(AICallLog.called_at.desc())).all())
```

- [ ] **Step 4: Run tests**

```bash
cd engine && python -m pytest tests/ai/test_logging.py -v
```

Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
git add engine/src/migrations_engine/ai/logging.py \
        engine/src/migrations_engine/management/ai_calls.py \
        engine/tests/ai/test_logging.py
git commit -m "feat: add log_ai_call helper and list_ai_calls management function"
```

---

### Task 4: Wire logging into all 5 callers

**Files:**
- Modify: `engine/src/migrations_engine/codegen/service.py`
- Modify: `engine/src/migrations_engine/mapping/review.py`
- Modify: `engine/src/migrations_engine/management/source_analysis.py`
- Modify: `engine/src/migrations_engine/management/fibers.py`
- Modify: `engine/src/migrations_engine/codegen/schema_analysis.py`

**Interfaces:**
- Consumes: `log_ai_call()`, `backfill_artifact_id()` from Task 3; `AICallResult` from Task 2

- [ ] **Step 1: Wire codegen (`codegen/service.py`)**

In `generate_codegen_artifact`, locate the `adapter.call()` call (around line 111). Change from:

```python
generated_sql = adapter.call(
    system=_build_system_prompt(...),
    user=_build_user_prompt(...),
    response_model=GeneratedSQL,
)
```

to:

```python
from ..ai.logging import log_ai_call, backfill_artifact_id

system_prompt = _build_system_prompt(...)
user_prompt = _build_user_prompt(...)
try:
    result = adapter.call(system=system_prompt, user=user_prompt, response_model=GeneratedSQL)
    call_log = log_ai_call(
        db,
        project_id=project_id,
        call_type="codegen",
        model_id=adapter.model_id,
        system=system_prompt,
        user=user_prompt,
        raw_response=result.raw_response,
    )
    generated_sql = result.parsed
except Exception as exc:
    log_ai_call(
        db,
        project_id=project_id,
        call_type="codegen",
        model_id=adapter.model_id,
        system=system_prompt,
        user=user_prompt,
        raw_response=None,
        error_detail=str(exc),
    )
    raise
```

After the `CodeGenerationArtifact` is committed, back-fill:
```python
backfill_artifact_id(db, call_log.call_id, artifact.codegen_artifact_id)
```

- [ ] **Step 2: Wire mapping (`mapping/review.py`)**

Find the `adapter.call()` invocation. Apply the same pattern with `call_type="mapping"`. Back-fill with the `mapping_snapshot_id` after the snapshot is committed.

- [ ] **Step 3: Wire source analysis (`management/source_analysis.py`)**

Apply same pattern with `call_type="source_analysis"`. Back-fill with `schema_artifact_id`.

- [ ] **Step 4: Wire fibers (`management/fibers.py`)**

Apply same pattern with `call_type="lookup_mapping"`. Back-fill with `fiber_id` (no dedicated artifact table — use the `ProjectFiber.fiber_id`).

- [ ] **Step 5: Wire schema analysis (`codegen/schema_analysis.py`)**

Apply same pattern with `call_type="source_analysis"`. Back-fill with the analysis output ID if one exists; otherwise leave `artifact_id=None`.

- [ ] **Step 6: Run all tests**

```bash
cd engine && python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add engine/src/migrations_engine/codegen/service.py \
        engine/src/migrations_engine/mapping/review.py \
        engine/src/migrations_engine/management/source_analysis.py \
        engine/src/migrations_engine/management/fibers.py \
        engine/src/migrations_engine/codegen/schema_analysis.py
git commit -m "feat: wire ai_call_log into all 5 adapter call sites"
```

---

### Task 5: API endpoint

**Files:**
- Modify: `engine/src/migrations_engine/api/schemas.py`
- Create: `engine/src/migrations_engine/routes/ai_calls.py`
- Modify: `engine/src/migrations_engine/app.py`

**Interfaces:**
- Consumes: `list_ai_calls()` from Task 3
- Produces: `GET /projects/{project_id}/ai-calls` → `list[AICallLogResponse]`

- [ ] **Step 1: Add `AICallLogResponse` to schemas**

In `engine/src/migrations_engine/api/schemas.py`:

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

- [ ] **Step 2: Create `routes/ai_calls.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError, get_current_user, get_db
from ..api.schemas import AICallLogResponse
from ..db.models import User
from ..management.access import require_project_access
from ..management.ai_calls import list_ai_calls

router = APIRouter(prefix="/projects/{project_id}/ai-calls", tags=["ai-calls"])


@router.get("", response_model=list[AICallLogResponse])
def get_ai_calls(
    project_id: str,
    call_type: str | None = None,
    artifact_id: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AICallLogResponse]:
    from ..roles import ADMIN_ROLE, CENTRAL_TEAM_ROLE
    if actor.role not in {ADMIN_ROLE, CENTRAL_TEAM_ROLE}:
        raise AuthApiError("forbidden", "Admin or central team access is required.", 403)
    require_project_access(db, user=actor, project_id=project_id)
    rows = list_ai_calls(db, project_id=project_id, call_type=call_type, artifact_id=artifact_id)
    return [
        AICallLogResponse(
            call_id=r.call_id,
            call_type=r.call_type,
            artifact_id=r.artifact_id,
            model_id=r.model_id,
            system_prompt=r.system_prompt,
            user_prompt=r.user_prompt,
            raw_response=r.raw_response,
            error_detail=r.error_detail,
            called_at=r.called_at,
        )
        for r in rows
    ]
```

- [ ] **Step 3: Register router in `app.py`**

```bash
grep -n "include_router" engine/src/migrations_engine/app.py | head -10
```

Add alongside existing routers:
```python
from .routes.ai_calls import router as ai_calls_router
app.include_router(ai_calls_router)
```

- [ ] **Step 4: Smoke-test**

```bash
cd engine && python -m uvicorn src.migrations_engine.app:app --port 8001 &
sleep 3
curl -s http://localhost:8001/openapi.json | python -m json.tool | grep "ai-calls"
kill %1
```

Expected: route appears in OpenAPI spec.

- [ ] **Step 5: Commit**

```bash
git add engine/src/migrations_engine/api/schemas.py \
        engine/src/migrations_engine/routes/ai_calls.py \
        engine/src/migrations_engine/app.py
git commit -m "feat: add GET /projects/{id}/ai-calls endpoint"
```

---

## Verification

1. Trigger Generate SQL → `SELECT * FROM ai_call_log WHERE call_type='codegen'` → row present with prompts and `artifact_id` populated
2. Trigger mapping AI → row with `call_type='mapping'`
3. Trigger source analysis → row with `call_type='source_analysis'`
4. Force an adapter failure → row present with `raw_response=NULL`, `error_detail` explains the error
5. `GET /projects/{id}/ai-calls` → returns all rows; `?call_type=codegen` filters correctly
6. `project_stakeholder` → 403 on the endpoint
7. `GET /projects/{id}/ai-calls?artifact_id={codegen_artifact_id}` → returns exactly the log entry for that artifact
