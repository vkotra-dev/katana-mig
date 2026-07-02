# Mapping Fiber AI Flow Implementation Plan (001am)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the AI field-binding proposal flow for mapping fibers. When an operator calls `POST /projects/{project_id}/feeds/{feed_id}/analyze`, the system reads the feed's approved FeedSlice header, queries AI to identify lookup columns and domain objects, creates `ProjectFiber` rows for each, and for every `domain_object` fiber immediately calls a second AI slot to propose field bindings — persisting the result as `field_bindings` on the fiber.

**Architecture:** No new DB migration is required — `ProjectFiber.field_bindings` (JSON) already exists from 001ak. The change touches four layers: (1) the AI config stack (`engine.yaml`, `config.py`, `factory.py`) gains a new `feed_analysis` slot; (2) `management/fibers.py` gets the `analyze_feed` service function with internal Pydantic response models and two AI calls; (3) `routes/fibers.py` gets a second `APIRouter` (parent prefix `/projects/{project_id}/feeds/{feed_id}`) with a single `POST /analyze` endpoint; (4) `app.py` registers the new router.

**Tech Stack:** FastAPI, SQLAlchemy 2 (sync), Pydantic v2, pytest with `monkeypatch`, PyYAML; no new frontend in this task.

## Global Constraints

- Depends on **001aj** (Feed rename) completing first — use `FeedSlice` / `Feed` class names, not `SourceSlice` / `SourceDefinition`.
- Depends on **001ak** (Fiber models) completing first — `ProjectFiber`, `FiberResponse`, `_to_response`, `_require_feed`, `create_fiber` already exist in `management/fibers.py` and `routes/fibers.py`.
- `feed_analysis` AI slot → creates lookup fibers (`status="deferred"`, `source="auto"`) + domain_object fibers (`status="ai_running"`, `source="auto"`).
- `field_mapping` AI slot → updates domain_object fiber: `field_bindings = [...]`, `status = "mapped"`.
- Route auth: `central_team` only (`get_central_team_user` dep).
- `FeedSlice.source_definition_id` column holds the FK to the `feeds` table — this is the `feed_id`.
- Project DDL lives at `ProjectDefinition.domain_config["destination_schema_ddl"]` (may be absent; use empty string as fallback).
- Monkeypatch target for service tests: `"migrations_engine.management.fibers.get_adapter"`.
- The `get_adapter` import in `management/fibers.py` MUST use the same try/except guard pattern as `management/source_analysis.py`.
- All existing engine tests must remain green after each commit.
- No new DB migration file needed.

## Objective

Add the `feed_analysis` AI slot, the analyze-feed endpoint, and the field-binding proposal flow for mapping fibers.

## Out of Scope

- No lookup-fiber proposal changes
- No approval-chain work
- No codegen bundle sequencing changes

## File Changes

- See the blast radius table above for the exact backend and web files.

## Verification

- Run the new mapping AI flow tests
- Run the mapping page tests
- Run the touched backend and web suites

## Pitfalls

- Keep the slot wiring and endpoint names aligned
- Preserve the source-column-to-destination-column semantics in the proposal payload
- Avoid mixing lookup-fiber behavior into the mapping flow

## Commit

- `feat(001am): add mapping fiber AI flow`


---

## Blast Radius

| File | Change |
|---|---|
| `engine/config/engine.yaml` | Add `feed_analysis: ${MODEL_FEED_ANALYSIS}` under `migration.models` |
| `engine/tests/fixtures/engine.yaml` | Add `feed_analysis: claude-sonnet-4-6` under `migration.models` |
| `engine/src/migrations_engine/ai/config.py` | Add `feed_analysis: str` field to `MigrationModelConfig`; add parse call in `_parse_config` |
| `engine/src/migrations_engine/ai/factory.py` | Add `"feed_analysis"` entry to `_SLOT_MAP` |
| `engine/tests/test_ai_config.py` | Add assertion for `feed_analysis`; update inline YAML string in env-substitution test |
| `engine/src/migrations_engine/management/fibers.py` | Add internal Pydantic models; add `analyze_feed` service function; add imports |
| `engine/src/migrations_engine/routes/fibers.py` | Add `feeds_router` (`/projects/{project_id}/feeds/{feed_id}`) with `POST /analyze` endpoint |
| `engine/src/migrations_engine/app.py` | Import and include `feeds_router` from `routes.fibers` |
| `engine/tests/test_fiber_ai_flow.py` | Create — service-level and API-level tests |

---

## Task 1: New AI slot `feed_analysis`

**Files:**
- Modify: `engine/config/engine.yaml`
- Modify: `engine/tests/fixtures/engine.yaml`
- Modify: `engine/src/migrations_engine/ai/config.py`
- Modify: `engine/src/migrations_engine/ai/factory.py`
- Modify: `engine/tests/test_ai_config.py`

**Interfaces:**
- Produces: `MigrationModelConfig.feed_analysis: str`; `get_adapter("feed_analysis")` returns a working adapter.
- Consumes: `MODEL_FEED_ANALYSIS` env var (production); concrete model string in test fixture.

- [ ] **Step 1.1: Write failing tests**

Add to `engine/tests/test_ai_config.py`:

```python
def test_feed_analysis_model_loaded_from_fixture() -> None:
    config = get_ai_config(FIXTURE_YAML)
    assert config.migration_models.feed_analysis == "claude-sonnet-4-6"


def test_get_adapter_feed_analysis_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    from migrations_engine.ai.factory import get_adapter, _SLOT_MAP
    assert "feed_analysis" in _SLOT_MAP
```

- [ ] **Step 1.2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/engine && python -m pytest tests/test_ai_config.py -v 2>&1 | tail -20
```

Expected: `FAILED` — `AttributeError: 'MigrationModelConfig' object has no attribute 'feed_analysis'`

- [ ] **Step 1.3: Update `engine/config/engine.yaml`**

Add `feed_analysis: ${MODEL_FEED_ANALYSIS}` under `migration.models`:

```yaml
models:
  planning: ${MODEL_PLANNING}
  review: ${MODEL_REVIEW}
  implementation: ${MODEL_IMPLEMENTATION}
migration:
  models:
    pii_review: ${MODEL_PII_REVIEW}
    field_mapping: ${MODEL_FIELD_MAPPING}
    script_generation: ${MODEL_SCRIPT_GENERATION}
    script_correction: ${MODEL_SCRIPT_CORRECTION}
    feed_analysis: ${MODEL_FEED_ANALYSIS}
providers:
  anthropic_api_key_env: ANTHROPIC_API_KEY
  openai_api_key_env: OPENAI_API_KEY
```

- [ ] **Step 1.4: Update `engine/tests/fixtures/engine.yaml`**

Add `feed_analysis: claude-sonnet-4-6` under `migration.models`:

```yaml
models:
  planning: claude-opus-4-8
  review: claude-sonnet-4-6
  implementation: claude-sonnet-4-6
migration:
  models:
    pii_review: claude-haiku-4-5-20251001
    field_mapping: claude-opus-4-8
    script_generation: gpt-4o-mini
    script_correction: claude-sonnet-4-6
    feed_analysis: claude-sonnet-4-6
providers:
  anthropic_api_key_env: ANTHROPIC_API_KEY
  openai_api_key_env: OPENAI_API_KEY
```

- [ ] **Step 1.5: Update `engine/src/migrations_engine/ai/config.py`**

Add `feed_analysis: str` to `MigrationModelConfig`, and add its parsing in `_parse_config`:

```python
@dataclass(frozen=True)
class MigrationModelConfig:
    pii_review: str
    field_mapping: str
    script_generation: str
    script_correction: str
    feed_analysis: str
```

In `_parse_config`, update the `MigrationModelConfig(...)` construction call:

```python
        migration_models=MigrationModelConfig(
            pii_review=_require_str(migration_models, "pii_review", "migration.models.pii_review"),
            field_mapping=_require_str(migration_models, "field_mapping", "migration.models.field_mapping"),
            script_generation=_require_str(
                migration_models,
                "script_generation",
                "migration.models.script_generation",
            ),
            script_correction=_require_str(
                migration_models,
                "script_correction",
                "migration.models.script_correction",
            ),
            feed_analysis=_require_str(
                migration_models,
                "feed_analysis",
                "migration.models.feed_analysis",
            ),
        ),
```

- [ ] **Step 1.6: Update `engine/src/migrations_engine/ai/factory.py`**

Add `"feed_analysis"` to `_SLOT_MAP`:

```python
_SLOT_MAP = {
    "planning": lambda config: config.models.planning,
    "review": lambda config: config.models.review,
    "implementation": lambda config: config.models.implementation,
    "pii_review": lambda config: config.migration_models.pii_review,
    "field_mapping": lambda config: config.migration_models.field_mapping,
    "script_generation": lambda config: config.migration_models.script_generation,
    "script_correction": lambda config: config.migration_models.script_correction,
    "feed_analysis": lambda config: config.migration_models.feed_analysis,
}
```

- [ ] **Step 1.7: Update the env-substitution test in `engine/tests/test_ai_config.py`**

The inline YAML string in `test_substitutes_env_values_and_raises_for_missing_env` must include `feed_analysis`:

```python
    config_path.write_text(
        "models:\n"
        "  planning: ${MODEL_PLANNING}\n"
        "  review: ${MODEL_REVIEW}\n"
        "  implementation: ${MODEL_IMPLEMENTATION}\n"
        "migration:\n"
        "  models:\n"
        "    pii_review: ${MODEL_PII_REVIEW}\n"
        "    field_mapping: ${MODEL_FIELD_MAPPING}\n"
        "    script_generation: ${MODEL_SCRIPT_GENERATION}\n"
        "    script_correction: ${MODEL_SCRIPT_CORRECTION}\n"
        "    feed_analysis: ${MODEL_FEED_ANALYSIS}\n"
        "providers:\n"
        "  anthropic_api_key_env: ANTHROPIC_API_KEY\n"
        "  openai_api_key_env: OPENAI_API_KEY\n",
        encoding="utf-8",
    )
```

Also add the env-var setup line:

```python
    monkeypatch.setenv("MODEL_FEED_ANALYSIS", "claude-sonnet-4-6")
```

(Add it alongside the other `monkeypatch.setenv` calls in that test.)

- [ ] **Step 1.8: Run AI config tests**

```bash
cd /Users/vjkotra/projects/katana/engine && python -m pytest tests/test_ai_config.py tests/test_ai_adapter.py -v 2>&1 | tail -30
```

Expected: all tests PASS.

- [ ] **Step 1.9: Run full engine suite to check no regressions**

```bash
cd /Users/vjkotra/projects/katana/engine && python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests PASS.

- [ ] **Step 1.10: Commit**

```bash
git add engine/config/engine.yaml \
        engine/tests/fixtures/engine.yaml \
        engine/src/migrations_engine/ai/config.py \
        engine/src/migrations_engine/ai/factory.py \
        engine/tests/test_ai_config.py
git commit -m "$(cat <<'EOF'
feat(001am): add feed_analysis AI slot to engine config and factory

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Service `analyze_feed` + route `POST .../analyze`

**Files:**
- Modify: `engine/src/migrations_engine/management/fibers.py`
- Modify: `engine/src/migrations_engine/routes/fibers.py`
- Modify: `engine/src/migrations_engine/app.py`

**Interfaces:**
- Consumes: `FeedSlice` (post-001aj), `Feed`, `ProjectDefinition`, `ProjectRegistry`, `ProjectFiber`, `FiberResponse` from existing models/schemas; `get_adapter` from `ai.factory`; `_require_feed`, `_to_response` from same file.
- Produces:
  - `analyze_feed(db, *, feed_id, project_id, actor) -> list[FiberResponse]`
  - `POST /projects/{project_id}/feeds/{feed_id}/analyze` → `list[FiberResponse]` 200, requires `central_team`

- [ ] **Step 2.1: Write the failing service test**

Create `engine/tests/test_fiber_ai_flow.py` with the service-level test (no HTTP client):

```python
from __future__ import annotations

import csv
import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.db.models import (
    Feed,
    FeedSlice,
    ProjectDefinition,
    ProjectFiber,
    ProjectRegistry,
    User,
)
from migrations_engine.roles import CENTRAL_TEAM_ROLE


# ---------------------------------------------------------------------------
# Fake adapters
# ---------------------------------------------------------------------------

class FakeFeedAnalysisAdapter:
    model_id = "claude-sonnet-4-6"

    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[SimpleNamespace] = []

    def call(self, system: str, user: str, response_model: type) -> Any:
        self.calls.append(SimpleNamespace(system=system, user=user, response_model=response_model))
        return self.result


class FakeFieldMappingAdapter:
    model_id = "claude-opus-4-8"

    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[SimpleNamespace] = []

    def call(self, system: str, user: str, response_model: type) -> Any:
        self.calls.append(SimpleNamespace(system=system, user=user, response_model=response_model))
        return self.result


# ---------------------------------------------------------------------------
# DB seed helper
# ---------------------------------------------------------------------------

def _seed_project_and_feed(
    db,
    *,
    header_csv: str = "CUST_ID,ACCT_TYPE,SURNAME",
    destination_schema_ddl: str = "CREATE TABLE customers (id INT, name TEXT);",
) -> tuple[User, str, str]:
    """Seed a project + feed + approved FeedSlice. Returns (actor, project_id, feed_id)."""
    actor = User(
        user_id=str(uuid.uuid4()),
        email=f"central-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Central Team",
        password_hash="hash",
        role=CENTRAL_TEAM_ROLE,
        status="active",
    )
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    feed_id = str(uuid.uuid4())
    db.add(actor)
    db.add(
        ProjectDefinition(
            definition_id=definition_id,
            project_id=project_id,
            name="Fiber AI Flow Project",
            domain_config={"destination_schema_ddl": destination_schema_ddl},
            status="active",
        )
    )
    db.add(
        ProjectRegistry(
            project_id=project_id,
            name="Fiber AI Flow Project",
            definition_id=definition_id,
            status="active",
        )
    )
    db.add(
        Feed(
            source_definition_id=feed_id,
            project_id=project_id,
            source_type="csv",
            source_contract_version="v1",
            status="active",
        )
    )
    db.add(
        FeedSlice(
            source_slice_id=str(uuid.uuid4()),
            source_definition_id=feed_id,
            source_contract_version="v1",
            source_slice_version="v1",
            header_csv=header_csv,
            status="approved",
            approved_at=datetime.now(UTC),
            approved_by_user_id=actor.user_id,
        )
    )
    db.commit()
    return actor, project_id, feed_id


# ---------------------------------------------------------------------------
# Module-level DB setup
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _setup_db() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------

def test_analyze_feed_creates_lookup_and_domain_object_fibers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from migrations_engine.management.fibers import (
        _FeedAnalysisResult,
        _FieldMappingResult,
        _LookupIdentified,
        _DomainObject,
        _FieldBinding,
        analyze_feed,
    )

    feed_analysis_result = _FeedAnalysisResult(
        lookups=[
            _LookupIdentified(column_name="ACCT_TYPE", lookup_name="account_type"),
        ],
        domain_objects=[
            _DomainObject(destination_table="customers"),
        ],
    )
    field_mapping_result = _FieldMappingResult(
        field_bindings=[
            _FieldBinding(source_field="CUST_ID", destination_field="id", lookup_name=None),
            _FieldBinding(source_field="SURNAME", destination_field="name", lookup_name=None),
            _FieldBinding(source_field=None, destination_field="created_at", lookup_name=None),
        ]
    )

    feed_analysis_adapter = FakeFeedAnalysisAdapter(feed_analysis_result)
    field_mapping_adapter = FakeFieldMappingAdapter(field_mapping_result)

    def fake_get_adapter(task: str) -> Any:
        if task == "feed_analysis":
            return feed_analysis_adapter
        if task == "field_mapping":
            return field_mapping_adapter
        raise ValueError(f"Unexpected task: {task}")

    monkeypatch.setattr("migrations_engine.management.fibers.get_adapter", fake_get_adapter)

    with SessionLocal() as db:
        actor, project_id, feed_id = _seed_project_and_feed(db)
        responses = analyze_feed(db, feed_id=feed_id, project_id=project_id, actor=actor)

    assert len(responses) == 2

    lookup_fibers = [r for r in responses if r.fiber_type == "lookup"]
    domain_fibers = [r for r in responses if r.fiber_type == "domain_object"]

    assert len(lookup_fibers) == 1
    assert lookup_fibers[0].fiber_key == "account_type"
    assert lookup_fibers[0].status == "deferred"
    assert lookup_fibers[0].source == "auto"
    assert lookup_fibers[0].field_bindings is None

    assert len(domain_fibers) == 1
    assert domain_fibers[0].fiber_key == "customers"
    assert domain_fibers[0].status == "mapped"
    assert domain_fibers[0].source == "auto"
    assert domain_fibers[0].field_bindings is not None
    assert len(domain_fibers[0].field_bindings) == 3
    assert domain_fibers[0].field_bindings[0]["destination_field"] == "id"
    assert domain_fibers[0].field_bindings[2]["source_field"] is None


def test_analyze_feed_passes_correct_context_to_ai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from migrations_engine.management.fibers import (
        _FeedAnalysisResult,
        _FieldMappingResult,
        _LookupIdentified,
        _DomainObject,
        _FieldBinding,
        analyze_feed,
    )

    ddl = "CREATE TABLE orders (order_id INT, customer_id INT);"
    header = "ORDER_ID,CUSTOMER_ID,STATUS_CODE"

    feed_analysis_result = _FeedAnalysisResult(
        lookups=[_LookupIdentified(column_name="STATUS_CODE", lookup_name="order_status")],
        domain_objects=[_DomainObject(destination_table="orders")],
    )
    field_mapping_result = _FieldMappingResult(
        field_bindings=[
            _FieldBinding(source_field="ORDER_ID", destination_field="order_id", lookup_name=None),
            _FieldBinding(source_field="CUSTOMER_ID", destination_field="customer_id", lookup_name=None),
        ]
    )

    feed_analysis_adapter = FakeFeedAnalysisAdapter(feed_analysis_result)
    field_mapping_adapter = FakeFieldMappingAdapter(field_mapping_result)

    def fake_get_adapter(task: str) -> Any:
        if task == "feed_analysis":
            return feed_analysis_adapter
        return field_mapping_adapter

    monkeypatch.setattr("migrations_engine.management.fibers.get_adapter", fake_get_adapter)

    with SessionLocal() as db:
        actor, project_id, feed_id = _seed_project_and_feed(
            db,
            header_csv=header,
            destination_schema_ddl=ddl,
        )
        analyze_feed(db, feed_id=feed_id, project_id=project_id, actor=actor)

    # feed_analysis call context
    assert len(feed_analysis_adapter.calls) == 1
    fa_call = feed_analysis_adapter.calls[0]
    fa_user = json.loads(fa_call.user)
    assert fa_user["source_headers"] == ["ORDER_ID", "CUSTOMER_ID", "STATUS_CODE"]
    assert fa_user["destination_schema_ddl"] == ddl
    assert "data migration analyst" in fa_call.system.lower()

    # field_mapping call context
    assert len(field_mapping_adapter.calls) == 1
    fm_call = field_mapping_adapter.calls[0]
    fm_user = json.loads(fm_call.user)
    assert fm_user["source_columns"] == ["ORDER_ID", "CUSTOMER_ID", "STATUS_CODE"]
    assert fm_user["destination_table"] == "orders"
    assert fm_user["destination_schema_ddl"] == ddl
    assert "field mapper" in fm_call.system.lower()


def test_analyze_feed_uses_correct_ai_slots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from migrations_engine.management.fibers import (
        _FeedAnalysisResult,
        _FieldMappingResult,
        _DomainObject,
        _LookupIdentified,
        _FieldBinding,
        analyze_feed,
    )

    requested_tasks: list[str] = []
    feed_analysis_result = _FeedAnalysisResult(
        lookups=[],
        domain_objects=[_DomainObject(destination_table="customers")],
    )
    field_mapping_result = _FieldMappingResult(
        field_bindings=[_FieldBinding(source_field="ID", destination_field="id", lookup_name=None)]
    )

    def fake_get_adapter(task: str) -> Any:
        requested_tasks.append(task)
        if task == "feed_analysis":
            return FakeFeedAnalysisAdapter(feed_analysis_result)
        return FakeFieldMappingAdapter(field_mapping_result)

    monkeypatch.setattr("migrations_engine.management.fibers.get_adapter", fake_get_adapter)

    with SessionLocal() as db:
        actor, project_id, feed_id = _seed_project_and_feed(db)
        analyze_feed(db, feed_id=feed_id, project_id=project_id, actor=actor)

    assert "feed_analysis" in requested_tasks
    assert "field_mapping" in requested_tasks


def test_analyze_feed_with_multiple_domain_objects_calls_field_mapping_per_fiber(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from migrations_engine.management.fibers import (
        _FeedAnalysisResult,
        _FieldMappingResult,
        _DomainObject,
        _FieldBinding,
        analyze_feed,
    )

    feed_analysis_result = _FeedAnalysisResult(
        lookups=[],
        domain_objects=[
            _DomainObject(destination_table="customers"),
            _DomainObject(destination_table="accounts"),
        ],
    )
    field_mapping_result = _FieldMappingResult(
        field_bindings=[_FieldBinding(source_field="ID", destination_field="id", lookup_name=None)]
    )

    feed_analysis_adapter = FakeFeedAnalysisAdapter(feed_analysis_result)
    field_mapping_adapter = FakeFieldMappingAdapter(field_mapping_result)

    def fake_get_adapter(task: str) -> Any:
        if task == "feed_analysis":
            return feed_analysis_adapter
        return field_mapping_adapter

    monkeypatch.setattr("migrations_engine.management.fibers.get_adapter", fake_get_adapter)

    with SessionLocal() as db:
        actor, project_id, feed_id = _seed_project_and_feed(db)
        responses = analyze_feed(db, feed_id=feed_id, project_id=project_id, actor=actor)

    domain_fibers = [r for r in responses if r.fiber_type == "domain_object"]
    assert len(domain_fibers) == 2
    # field_mapping must be called once per domain_object fiber
    assert len(field_mapping_adapter.calls) == 2
    destination_tables_in_calls = [
        json.loads(c.user)["destination_table"] for c in field_mapping_adapter.calls
    ]
    assert set(destination_tables_in_calls) == {"customers", "accounts"}


def test_analyze_feed_raises_409_when_no_approved_feed_slice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from migrations_engine.management.fibers import analyze_feed
    from migrations_engine.api.deps import AuthApiError

    monkeypatch.setattr(
        "migrations_engine.management.fibers.get_adapter",
        lambda task: None,  # should never be reached
    )

    actor = User(
        user_id=str(uuid.uuid4()),
        email=f"central-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Central Team",
        password_hash="hash",
        role=CENTRAL_TEAM_ROLE,
        status="active",
    )
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    feed_id = str(uuid.uuid4())

    with SessionLocal() as db:
        db.add(actor)
        db.add(ProjectDefinition(definition_id=definition_id, project_id=project_id, name="P", domain_config={}))
        db.add(ProjectRegistry(project_id=project_id, name="P", definition_id=definition_id, status="active"))
        db.add(Feed(source_definition_id=feed_id, project_id=project_id, source_type="csv", source_contract_version="v1"))
        db.commit()

        with pytest.raises(AuthApiError) as exc_info:
            analyze_feed(db, feed_id=feed_id, project_id=project_id, actor=actor)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "feed_slice_not_ready"
```

- [ ] **Step 2.2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/engine && python -m pytest tests/test_fiber_ai_flow.py -v 2>&1 | tail -20
```

Expected: `FAILED` — `ImportError: cannot import name 'analyze_feed'` (or similar)

- [ ] **Step 2.3: Add service code to `engine/src/migrations_engine/management/fibers.py`**

Add all imports needed and the internal Pydantic models and `analyze_feed` function. Append after the existing `get_fiber` function:

```python
# ---------------------------------------------------------------------------
# Internal AI response models (used only within this module)
# ---------------------------------------------------------------------------

import csv as _csv
import json as _json

from pydantic import BaseModel as _BaseModel

try:
    from ..ai.factory import get_adapter
except ModuleNotFoundError:  # pragma: no cover
    get_adapter = None  # type: ignore[assignment]


_FEED_ANALYSIS_SYSTEM = (
    "You are a data migration analyst. "
    "Given CSV column headers and a destination schema DDL, "
    "identify all lookup columns and domain objects. Return JSON."
)

_FIELD_MAPPING_SYSTEM = (
    "You are a field mapper. "
    "Given source columns and destination DDL, propose field bindings. Return JSON."
)


class _LookupIdentified(_BaseModel):
    column_name: str
    lookup_name: str


class _DomainObject(_BaseModel):
    destination_table: str


class _FeedAnalysisResult(_BaseModel):
    lookups: list[_LookupIdentified]
    domain_objects: list[_DomainObject]


class _FieldBinding(_BaseModel):
    source_field: str | None
    destination_field: str
    lookup_name: str | None


class _FieldMappingResult(_BaseModel):
    field_bindings: list[_FieldBinding]


# ---------------------------------------------------------------------------
# analyze_feed service function
# ---------------------------------------------------------------------------

def analyze_feed(
    db: Session,
    *,
    feed_id: str,
    project_id: str,
    actor: User,
) -> list[FiberResponse]:
    """
    Trigger AI analysis for a feed:
    1. Read the latest approved FeedSlice header.
    2. Call AI slot "feed_analysis" to identify lookups and domain objects.
    3. Create ProjectFiber rows for each.
    4. For each domain_object fiber, call AI slot "field_mapping" and persist bindings.
    Returns all created fibers.
    """
    from ..db.models import FeedSlice, ProjectDefinition, ProjectRegistry

    _require_feed(db, feed_id=feed_id, project_id=project_id)

    # -- Fetch project DDL --
    registry = db.get(ProjectRegistry, project_id)
    if registry is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)
    project_def = db.get(ProjectDefinition, registry.definition_id)
    destination_schema_ddl: str = ""
    if project_def is not None and project_def.domain_config:
        destination_schema_ddl = project_def.domain_config.get("destination_schema_ddl", "")

    # -- Fetch latest approved FeedSlice --
    feed_slice = db.scalar(
        select(FeedSlice)
        .where(
            FeedSlice.source_definition_id == feed_id,
            FeedSlice.status == "approved",
        )
        .order_by(FeedSlice.approved_at.desc().nullslast(), FeedSlice.created_at.desc())
    )
    if feed_slice is None:
        raise AuthApiError(
            "feed_slice_not_ready",
            "An approved FeedSlice is required before AI analysis.",
            409,
        )

    source_headers = _parse_header_csv(feed_slice.header_csv)

    if get_adapter is None:
        raise AuthApiError("ai_adapter_unavailable", "AI adapter dependency is unavailable.", 503)

    # -- AI call 1: feed_analysis --
    fa_user = _json.dumps(
        {
            "source_headers": source_headers,
            "destination_schema_ddl": destination_schema_ddl,
        },
        ensure_ascii=False,
    )
    fa_adapter = get_adapter("feed_analysis")
    analysis_result: _FeedAnalysisResult = fa_adapter.call(
        _FEED_ANALYSIS_SYSTEM, fa_user, _FeedAnalysisResult
    )

    # -- Create lookup fibers (deferred) --
    all_fibers: list[ProjectFiber] = []
    for lookup in analysis_result.lookups:
        fiber = ProjectFiber(
            feed_id=feed_id,
            project_id=project_id,
            fiber_type="lookup",
            fiber_key=lookup.lookup_name,
            status="deferred",
            source="auto",
        )
        db.add(fiber)
        all_fibers.append(fiber)

    # -- Create domain_object fibers (ai_running initially) --
    domain_fibers: list[ProjectFiber] = []
    for domain_obj in analysis_result.domain_objects:
        fiber = ProjectFiber(
            feed_id=feed_id,
            project_id=project_id,
            fiber_type="domain_object",
            fiber_key=domain_obj.destination_table,
            status="ai_running",
            source="auto",
        )
        db.add(fiber)
        domain_fibers.append(fiber)
        all_fibers.append(fiber)

    db.flush()  # assign PKs before AI call loop

    # -- AI call 2 (per domain_object fiber): field_mapping --
    fm_user_base = {
        "source_columns": source_headers,
        "destination_schema_ddl": destination_schema_ddl,
    }
    for fiber in domain_fibers:
        fm_user = _json.dumps(
            {**fm_user_base, "destination_table": fiber.fiber_key},
            ensure_ascii=False,
        )
        fm_adapter = get_adapter("field_mapping")
        mapping_result: _FieldMappingResult = fm_adapter.call(
            _FIELD_MAPPING_SYSTEM, fm_user, _FieldMappingResult
        )
        fiber.field_bindings = [b.model_dump(mode="python") for b in mapping_result.field_bindings]
        fiber.status = "mapped"

    db.commit()

    for fiber in all_fibers:
        db.refresh(fiber)

    return [_to_response(f) for f in all_fibers]


def _parse_header_csv(header_csv: str | None) -> list[str]:
    if not header_csv:
        return []
    return list(next(_csv.reader([header_csv])))
```

Note: The imports for `select`, `Session`, `AuthApiError`, `FiberResponse`, `ProjectFiber`, `User`, `_to_response`, `_require_feed` are already present in the file from 001ak. The only new top-level import needed is `select` (if not already there) — verify and add if missing.

- [ ] **Step 2.4: Add route in `engine/src/migrations_engine/routes/fibers.py`**

Add a second router at the feed level and the `POST /analyze` endpoint. Append after the existing `fibers_router` definition:

```python
from ..management.fibers import analyze_feed  # add to existing imports at top of file


feeds_router = APIRouter(
    prefix="/projects/{project_id}/feeds/{feed_id}",
    tags=["fibers"],
)


@feeds_router.post("/analyze", response_model=list[FiberResponse])
def post_analyze_feed(
    project_id: str,
    feed_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> list[FiberResponse]:
    return analyze_feed(db, feed_id=feed_id, project_id=project_id, actor=actor)
```

- [ ] **Step 2.5: Register `feeds_router` in `engine/src/migrations_engine/app.py`**

Update the import from `routes.fibers`:

```python
from .routes.fibers import router as fibers_router, feeds_router
```

Add include after the existing `fibers_router` include:

```python
app.include_router(fibers_router)
app.include_router(feeds_router)
```

- [ ] **Step 2.6: Run the new service tests**

```bash
cd /Users/vjkotra/projects/katana/engine && python -m pytest tests/test_fiber_ai_flow.py -v 2>&1 | tail -30
```

Expected: all tests PASS.

- [ ] **Step 2.7: Run the full engine suite**

```bash
cd /Users/vjkotra/projects/katana/engine && python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests PASS.

- [ ] **Step 2.8: Commit**

```bash
git add engine/src/migrations_engine/management/fibers.py \
        engine/src/migrations_engine/routes/fibers.py \
        engine/src/migrations_engine/app.py
git commit -m "$(cat <<'EOF'
feat(001am): add analyze_feed service and POST /analyze route for mapping fiber AI flow

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: API-level tests

**Files:**
- Modify: `engine/tests/test_fiber_ai_flow.py`

**Interfaces:**
- Consumes: `TestClient(app)`, `SessionLocal`, monkeypatch targeting `migrations_engine.management.fibers.get_adapter`.
- Verifies:
  - `POST /analyze` with valid feed returns 200 and correct fiber list.
  - `POST /analyze` without auth returns 401.
  - `POST /analyze` with no approved FeedSlice returns 409.
  - `POST /analyze` with stakeholder auth returns 403.

- [ ] **Step 3.1: Write the failing API tests**

Append the following to `engine/tests/test_fiber_ai_flow.py`:

```python
# ---------------------------------------------------------------------------
# API-level tests (TestClient)
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient

from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.roles import PROJECT_STAKEHOLDER_ROLE

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _seed_admin_and_stakeholder() -> None:
    # NOTE: _setup_db fixture already called (module scope, runs first).
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")
    with SessionLocal() as db:
        from sqlalchemy import select as _select
        existing = db.scalar(_select(User).where(User.email == settings.bootstrap_admin_email.strip().lower()))
        if existing is None:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email=settings.bootstrap_admin_email.strip().lower(),
                    display_name="Admin",
                    password_hash=hash_password(settings.bootstrap_admin_password),
                    role=CENTRAL_TEAM_ROLE,
                    status="active",
                )
            )
        stakeholder_email = "stakeholder-fiber-ai@example.com"
        existing_s = db.scalar(_select(User).where(User.email == stakeholder_email))
        if existing_s is None:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email=stakeholder_email,
                    display_name="Stakeholder",
                    password_hash=hash_password("stakeholder-pass"),
                    role=PROJECT_STAKEHOLDER_ROLE,
                    status="active",
                )
            )
        db.commit()


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    get_settings.cache_clear()


def _admin_token() -> str:
    settings = get_settings()
    r = client.post("/auth/login", json={
        "email": settings.bootstrap_admin_email,
        "password": settings.bootstrap_admin_password,
    })
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _stakeholder_token() -> str:
    r = client.post("/auth/login", json={
        "email": "stakeholder-fiber-ai@example.com",
        "password": "stakeholder-pass",
    })
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _seed_feed_with_slice(
    *,
    header_csv: str = "CUST_ID,ACCT_TYPE",
    include_approved_slice: bool = True,
) -> tuple[str, str]:
    """Returns (project_id, feed_id)."""
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    feed_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(ProjectDefinition(
            definition_id=definition_id,
            project_id=project_id,
            name="Analyze API Project",
            domain_config={"destination_schema_ddl": "CREATE TABLE customers (id INT);"},
            status="active",
        ))
        db.add(ProjectRegistry(project_id=project_id, name="P", definition_id=definition_id, status="active"))
        db.add(Feed(source_definition_id=feed_id, project_id=project_id, source_type="csv", source_contract_version="v1"))
        if include_approved_slice:
            db.add(FeedSlice(
                source_slice_id=str(uuid.uuid4()),
                source_definition_id=feed_id,
                source_contract_version="v1",
                source_slice_version="v1",
                header_csv=header_csv,
                status="approved",
                approved_at=datetime.now(UTC),
            ))
        db.commit()
    return project_id, feed_id


def _make_fake_get_adapter(
    feed_analysis_result: Any,
    field_mapping_result: Any,
) -> Any:
    def fake(task: str) -> Any:
        if task == "feed_analysis":
            return FakeFeedAnalysisAdapter(feed_analysis_result)
        return FakeFieldMappingAdapter(field_mapping_result)
    return fake


def test_api_analyze_feed_returns_created_fibers(monkeypatch: pytest.MonkeyPatch) -> None:
    from migrations_engine.management.fibers import (
        _FeedAnalysisResult,
        _FieldMappingResult,
        _LookupIdentified,
        _DomainObject,
        _FieldBinding,
    )

    feed_analysis_result = _FeedAnalysisResult(
        lookups=[_LookupIdentified(column_name="ACCT_TYPE", lookup_name="account_type")],
        domain_objects=[_DomainObject(destination_table="customers")],
    )
    field_mapping_result = _FieldMappingResult(
        field_bindings=[_FieldBinding(source_field="CUST_ID", destination_field="id", lookup_name=None)]
    )
    monkeypatch.setattr(
        "migrations_engine.management.fibers.get_adapter",
        _make_fake_get_adapter(feed_analysis_result, field_mapping_result),
    )

    project_id, feed_id = _seed_feed_with_slice()
    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/analyze",
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 2

    fiber_types = {f["fiber_type"] for f in body}
    assert fiber_types == {"lookup", "domain_object"}

    domain_fiber = next(f for f in body if f["fiber_type"] == "domain_object")
    assert domain_fiber["status"] == "mapped"
    assert domain_fiber["source"] == "auto"
    assert domain_fiber["field_bindings"] is not None
    assert len(domain_fiber["field_bindings"]) == 1

    lookup_fiber = next(f for f in body if f["fiber_type"] == "lookup")
    assert lookup_fiber["status"] == "deferred"
    assert lookup_fiber["source"] == "auto"


def test_api_analyze_feed_requires_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_feed_with_slice()
    r = client.post(f"/projects/{project_id}/feeds/{feed_id}/analyze")
    assert r.status_code == 401


def test_api_analyze_feed_requires_central_team(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_feed_with_slice()
    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/analyze",
        headers={"Authorization": f"Bearer {_stakeholder_token()}"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_api_analyze_feed_returns_409_without_approved_slice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from migrations_engine.management.fibers import (
        _FeedAnalysisResult,
        _FieldMappingResult,
    )
    monkeypatch.setattr(
        "migrations_engine.management.fibers.get_adapter",
        _make_fake_get_adapter(
            _FeedAnalysisResult(lookups=[], domain_objects=[]),
            _FieldMappingResult(field_bindings=[]),
        ),
    )

    project_id, feed_id = _seed_feed_with_slice(include_approved_slice=False)
    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/analyze",
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "feed_slice_not_ready"


def test_api_analyze_feed_returns_404_for_unknown_feed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from migrations_engine.management.fibers import (
        _FeedAnalysisResult,
        _FieldMappingResult,
    )
    monkeypatch.setattr(
        "migrations_engine.management.fibers.get_adapter",
        _make_fake_get_adapter(
            _FeedAnalysisResult(lookups=[], domain_objects=[]),
            _FieldMappingResult(field_bindings=[]),
        ),
    )

    r = client.post(
        f"/projects/{str(uuid.uuid4())}/feeds/{str(uuid.uuid4())}/analyze",
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    assert r.status_code == 404
```

- [ ] **Step 3.2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/engine && python -m pytest tests/test_fiber_ai_flow.py -k "test_api" -v 2>&1 | tail -20
```

Expected: `FAILED` — 404 on the analyze route (not yet registered) or import errors.

- [ ] **Step 3.3: Verify the route is registered and tests pass**

After Task 2 completes (route registered in `app.py`), the API tests should now pass. If failing, check:
- `feeds_router` is imported and included in `app.py`.
- The route prefix is exactly `/projects/{project_id}/feeds/{feed_id}` (no trailing slash, no `/fibers`).
- `analyze_feed` is imported into `routes/fibers.py`.

```bash
cd /Users/vjkotra/projects/katana/engine && python -m pytest tests/test_fiber_ai_flow.py -v 2>&1 | tail -30
```

Expected: all tests PASS (service-level + API-level).

- [ ] **Step 3.4: Run the full engine suite (final verification)**

```bash
cd /Users/vjkotra/projects/katana/engine && python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests PASS.

- [ ] **Step 3.5: Commit**

```bash
git add engine/tests/test_fiber_ai_flow.py
git commit -m "$(cat <<'EOF'
test(001am): add service and API tests for analyze_feed AI fiber flow

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Implementation Notes

### `management/fibers.py` import consolidation

The file from 001ak already has these imports at the top:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..api.deps import AuthApiError
from ..api.schemas import FiberCreateRequest, FiberResponse
from ..db.models import Feed, ProjectFiber, User
```

Task 2 adds to these:
- `import csv as _csv` and `import json as _json` (stdlib, use private aliases to avoid polluting the module's public surface)
- `from pydantic import BaseModel as _BaseModel` (for internal response models)
- The `try/except` guard for `get_adapter`
- `FeedSlice`, `ProjectDefinition`, `ProjectRegistry` are imported inside `analyze_feed` (lazy import to avoid circular dependencies) rather than at module level.

### Header CSV parsing

`FeedSlice.header_csv` is a raw comma-separated string (e.g., `"CUST_ID,ACCT_TYPE,SURNAME"`). Use `csv.reader` for correctness:

```python
def _parse_header_csv(header_csv: str | None) -> list[str]:
    if not header_csv:
        return []
    return list(next(_csv.reader([header_csv])))
```

This handles quoted fields and embedded commas correctly, matching the pattern used in `source_analysis.py`.

### FeedSlice FK column name

After 001aj, the `FeedSlice` model's column linking it to feeds is `source_definition_id` (the column name is unchanged; only the table name and Python class name changed). The filter in `analyze_feed` is:

```python
FeedSlice.source_definition_id == feed_id
```

### `db.flush()` before the field_mapping loop

`db.flush()` after inserting all fibers assigns SQLAlchemy-generated PKs (`fiber_id`) without committing the transaction. This is needed so that `fiber.fiber_id` is populated if referenced in any audit log or future extension. The `field_bindings` and `status` mutations on in-memory ORM objects are tracked and committed in the single `db.commit()` at the end.

### Monkeypatch target path

Both service-level and API-level tests use:

```python
monkeypatch.setattr("migrations_engine.management.fibers.get_adapter", fake_fn)
```

This works because `get_adapter` is bound as a module-level name in `management/fibers.py` via the try/except import. Patching the module-level name intercepts all calls within `analyze_feed`.
