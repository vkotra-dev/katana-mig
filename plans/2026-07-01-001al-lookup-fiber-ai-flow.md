# Lookup Fiber AI Flow — Implementation Plan (001al)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the full lifecycle that takes a lookup fiber from `deferred` → `inputs_ready` → `mapped` by (a) adding a new `lookup_mapping` AI slot, and (b) implementing all lookup entity endpoints — including the `POST /lookup-inputs` orchestrator that triggers the AI mapping call.

**Architecture:** Two self-contained tasks. Task 1 extends the existing AI config/factory with the `lookup_mapping` slot and updates all affected test fixtures. Task 2 adds the `LookupInputsRequest` schema, seven new service functions in `management/fibers.py`, and seven new routes in `routes/fibers.py`. All AI calls in service code are exposed at module level so tests can monkeypatch `get_adapter`.

**Tech Stack:** FastAPI, SQLAlchemy 2, Pydantic v2, pytest, Python `csv`/`io`/`json` stdlib; Anthropic or OpenAI adapter selected at runtime by model prefix.

## Global Constraints

- All five lookup models (`ProjectFiber`, `LookupSourceEntry`, `LookupDestFeed`, `LookupDestEntry`, `LookupMapping`) and their schemas (`FiberResponse`, `LookupSourceEntryResponse`, `LookupDestFeedResponse`, `LookupDestEntryResponse`, `LookupMappingResponse`, `LookupMappingPatchRequest`, `LookupSourceEntriesCreateRequest`, `LookupDestFeedCreateRequest`) already exist from 001ak. Do **not** redefine them.
- No new migration is needed — all five tables already exist from migration `0019_fiber_models`.
- Lookup fiber status lifecycle for this task: `deferred → inputs_ready → mapped`. The transition happens entirely inside `submit_lookup_inputs`; no intermediate commit is visible to callers.
- `LookupMapping.mapped_by` for AI-generated mappings = `"ai"`; for operator overrides = `"operator"`.
- `fiber.proposed_mappings` is a JSON denormalization (list of proposal dicts) written alongside the `LookupMapping` rows so callers can read the summary without a join.
- `LookupDestFeed` is unique per fiber (`unique=True` on `fiber_id`). `POST /dest-feed` replaces any existing feed + entries.
- `POST /source-entries` **appends** — it does not replace existing entries.
- Error codes → HTTP status: `fiber_not_lookup` → 409, `fiber_not_deferred` → 409, `fiber_not_found` → 404, `mapping_not_found` → 404.
- Route prefix: `router = APIRouter(prefix="/projects/{project_id}/feeds/{feed_id}/fibers", tags=["fibers"])` (already declared in `routes/fibers.py` from 001ak).
- Import pattern for AI: `from ..ai.factory import get_adapter` (direct import, not guarded by try/except, so monkeypatch target is `migrations_engine.management.fibers.get_adapter`).
- `Feed` model lives at `engine/src/migrations_engine/db/models.py` (renamed from `SourceDefinition` in 001aj).

## Objective

Add the `lookup_mapping` AI slot and the lookup-input/proposal flow that produces lookup fiber suggestions from source values and destination reference data.

## Out of Scope

- No mapping-fiber changes
- No approval-chain UI
- No codegen bundle sequencing changes

## File Changes

- See the blast radius table above for the exact backend and web files.

## Verification

- Run the new lookup AI flow tests
- Run the lookup page tests
- Run the touched backend and web suites

## Pitfalls

- Keep the slot name aligned everywhere
- Make sure the input format accepts the same source-value shape the UI sends
- Do not let proposal generation drift from the test fixtures

## Commit

- `feat(001al): add lookup fiber AI flow`


---

## Blast Radius

| File | Change |
|---|---|
| `engine/config/engine.yaml` | Add `lookup_mapping: ${MODEL_LOOKUP_MAPPING}` |
| `engine/tests/fixtures/engine.yaml` | Add `lookup_mapping: claude-sonnet-4-6` |
| `engine/src/migrations_engine/ai/config.py` | Add `lookup_mapping: str` field to `MigrationModelConfig`; update `_parse_config` |
| `engine/src/migrations_engine/ai/factory.py` | Add `"lookup_mapping"` entry to `_SLOT_MAP` |
| `engine/tests/test_ai_config.py` | Update inline YAML string + add assertion for `lookup_mapping` |
| `engine/tests/test_ai_adapter.py` | Add `lookup_mapping` default to `_make_config` helper |
| `engine/src/migrations_engine/api/schemas.py` | Add `LookupInputsRequest` |
| `engine/src/migrations_engine/management/fibers.py` | Add 7 service functions + private helpers + AI private models |
| `engine/src/migrations_engine/routes/fibers.py` | Add 7 new route handlers |
| `engine/tests/test_lookup_ai_slot.py` | Create — Task 1 tests |
| `engine/tests/test_lookup_fiber_api.py` | Create — Task 2 tests |

---

## Task 1: `lookup_mapping` AI Slot

**Files:**
- Modify: `engine/config/engine.yaml`
- Modify: `engine/tests/fixtures/engine.yaml`
- Modify: `engine/src/migrations_engine/ai/config.py`
- Modify: `engine/src/migrations_engine/ai/factory.py`
- Modify: `engine/tests/test_ai_config.py`
- Modify: `engine/tests/test_ai_adapter.py`
- Create: `engine/tests/test_lookup_ai_slot.py`

**Interfaces:**
- Produces: `get_adapter("lookup_mapping")` returns an `AIAdapter`; `MigrationModelConfig.lookup_mapping` holds the model ID string.

---

- [ ] **Step 1: Write the failing test**

Create `engine/tests/test_lookup_ai_slot.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from migrations_engine.ai.config import (
    AIConfig,
    ConfigurationError,
    MigrationModelConfig,
    PlatformModelConfig,
    ProviderConfig,
    get_ai_config,
)
from migrations_engine.ai.factory import get_adapter


FIXTURE_YAML = Path(__file__).parent / "fixtures" / "engine.yaml"


@pytest.fixture(autouse=True)
def _clear_ai_config_cache() -> None:
    get_ai_config.cache_clear()


def _make_config(*, lookup_mapping: str = "claude-sonnet-4-6") -> AIConfig:
    return AIConfig(
        models=PlatformModelConfig(
            planning="claude-opus-4-8",
            review="claude-sonnet-4-6",
            implementation="claude-sonnet-4-6",
        ),
        migration_models=MigrationModelConfig(
            pii_review="claude-haiku-4-5-20251001",
            field_mapping="claude-opus-4-8",
            script_generation="gpt-4o-mini",
            script_correction="claude-sonnet-4-6",
            lookup_mapping=lookup_mapping,
        ),
        providers=ProviderConfig(
            anthropic_api_key_env="ANTHROPIC_API_KEY",
            openai_api_key_env="OPENAI_API_KEY",
        ),
    )


def test_migration_model_config_has_lookup_mapping_field() -> None:
    config = _make_config(lookup_mapping="claude-sonnet-4-6")
    assert config.migration_models.lookup_mapping == "claude-sonnet-4-6"


def test_fixture_yaml_includes_lookup_mapping() -> None:
    config = get_ai_config(FIXTURE_YAML)
    assert config.migration_models.lookup_mapping == "claude-sonnet-4-6"


def test_get_adapter_routes_lookup_mapping_to_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("migrations_engine.ai.factory.get_ai_config", lambda: _make_config())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")

    adapter = get_adapter("lookup_mapping")
    assert adapter.__class__.__name__ == "AnthropicAdapter"


def test_get_adapter_unknown_task_still_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("migrations_engine.ai.factory.get_ai_config", lambda: _make_config())

    with pytest.raises(ConfigurationError, match="Unknown AI task"):
        get_adapter("not_a_real_task")
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_lookup_ai_slot.py -v
```

Expected: FAIL — `TypeError: MigrationModelConfig.__init__() got an unexpected keyword argument 'lookup_mapping'` (or similar import error on the fixture YAML).

- [ ] **Step 3: Add `lookup_mapping` to `engine/tests/fixtures/engine.yaml`**

Current file `engine/tests/fixtures/engine.yaml`:
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
providers:
  anthropic_api_key_env: ANTHROPIC_API_KEY
  openai_api_key_env: OPENAI_API_KEY
```

Replace with:
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
    lookup_mapping: claude-sonnet-4-6
providers:
  anthropic_api_key_env: ANTHROPIC_API_KEY
  openai_api_key_env: OPENAI_API_KEY
```

- [ ] **Step 4: Add `lookup_mapping` to `engine/config/engine.yaml`**

Current file `engine/config/engine.yaml`:
```yaml
migration:
  models:
    pii_review: ${MODEL_PII_REVIEW}
    field_mapping: ${MODEL_FIELD_MAPPING}
    script_generation: ${MODEL_SCRIPT_GENERATION}
    script_correction: ${MODEL_SCRIPT_CORRECTION}
```

Replace the migration.models section with:
```yaml
migration:
  models:
    pii_review: ${MODEL_PII_REVIEW}
    field_mapping: ${MODEL_FIELD_MAPPING}
    script_generation: ${MODEL_SCRIPT_GENERATION}
    script_correction: ${MODEL_SCRIPT_CORRECTION}
    lookup_mapping: ${MODEL_LOOKUP_MAPPING}
```

- [ ] **Step 5: Update `MigrationModelConfig` and `_parse_config` in `engine/src/migrations_engine/ai/config.py`**

In the `MigrationModelConfig` dataclass, add the new field after `script_correction`:

```python
@dataclass(frozen=True)
class MigrationModelConfig:
    pii_review: str
    field_mapping: str
    script_generation: str
    script_correction: str
    lookup_mapping: str
```

In `_parse_config`, update the `MigrationModelConfig(...)` constructor call to add:

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
            lookup_mapping=_require_str(
                migration_models,
                "lookup_mapping",
                "migration.models.lookup_mapping",
            ),
        ),
```

- [ ] **Step 6: Add `lookup_mapping` entry to `_SLOT_MAP` in `engine/src/migrations_engine/ai/factory.py`**

```python
_SLOT_MAP = {
    "planning": lambda config: config.models.planning,
    "review": lambda config: config.models.review,
    "implementation": lambda config: config.models.implementation,
    "pii_review": lambda config: config.migration_models.pii_review,
    "field_mapping": lambda config: config.migration_models.field_mapping,
    "script_generation": lambda config: config.migration_models.script_generation,
    "script_correction": lambda config: config.migration_models.script_correction,
    "lookup_mapping": lambda config: config.migration_models.lookup_mapping,
}
```

- [ ] **Step 7: Update existing test helpers to include `lookup_mapping`**

In `engine/tests/test_ai_adapter.py`, update `_make_config` to add the new field with a default:

```python
def _make_config(
    *,
    planning: str = "claude-opus-4-8",
    review: str = "claude-sonnet-4-6",
    implementation: str = "claude-sonnet-4-6",
    pii_review: str = "claude-haiku-4-5-20251001",
    field_mapping: str = "claude-opus-4-8",
    script_generation: str = "gpt-4o-mini",
    script_correction: str = "claude-sonnet-4-6",
    lookup_mapping: str = "claude-sonnet-4-6",
) -> AIConfig:
    return AIConfig(
        models=PlatformModelConfig(
            planning=planning,
            review=review,
            implementation=implementation,
        ),
        migration_models=MigrationModelConfig(
            pii_review=pii_review,
            field_mapping=field_mapping,
            script_generation=script_generation,
            script_correction=script_correction,
            lookup_mapping=lookup_mapping,
        ),
        providers=ProviderConfig(
            anthropic_api_key_env="ANTHROPIC_API_KEY",
            openai_api_key_env="OPENAI_API_KEY",
        ),
    )
```

In `engine/tests/test_ai_config.py`, update the inline YAML string in `test_substitutes_env_values_and_raises_for_missing_env` to include `lookup_mapping`:

Find the `config_path.write_text(...)` call and add the new line:

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
        "    lookup_mapping: ${MODEL_LOOKUP_MAPPING}\n"
        "providers:\n"
        "  anthropic_api_key_env: ANTHROPIC_API_KEY\n"
        "  openai_api_key_env: OPENAI_API_KEY\n",
        encoding="utf-8",
    )
```

Also add the corresponding `monkeypatch.setenv` line:

```python
    monkeypatch.setenv("MODEL_LOOKUP_MAPPING", "claude-sonnet-4-6")
```

And add a check in `test_load_valid_config_from_fixture` after the existing assertions:

```python
    assert config.migration_models.lookup_mapping == "claude-sonnet-4-6"
```

- [ ] **Step 8: Run all AI-related tests to verify**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_lookup_ai_slot.py test_ai_config.py test_ai_adapter.py -v
```

Expected: all tests PASS.

- [ ] **Step 9: Run the full suite to verify no regressions**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 10: Commit**

```bash
git add \
  engine/config/engine.yaml \
  engine/tests/fixtures/engine.yaml \
  engine/src/migrations_engine/ai/config.py \
  engine/src/migrations_engine/ai/factory.py \
  engine/tests/test_ai_config.py \
  engine/tests/test_ai_adapter.py \
  engine/tests/test_lookup_ai_slot.py
git commit -m "feat(001al): add lookup_mapping AI slot to config, factory, and fixtures"
```

---

## Task 2: Lookup Entity Service + Routes

**Files:**
- Modify: `engine/src/migrations_engine/api/schemas.py`
- Modify: `engine/src/migrations_engine/management/fibers.py`
- Modify: `engine/src/migrations_engine/routes/fibers.py`
- Create: `engine/tests/test_lookup_fiber_api.py`

**Interfaces:**
- Consumes: all five lookup models from `db.models`, all lookup schemas from `api.schemas`, `get_adapter` from `ai.factory`
- Produces:
  - `submit_lookup_inputs(db, *, feed_id, fiber_id, project_id, body) -> FiberResponse`
  - `list_source_entries(db, *, feed_id, fiber_id, project_id) -> list[LookupSourceEntryResponse]`
  - `add_source_entries(db, *, feed_id, fiber_id, project_id, body) -> list[LookupSourceEntryResponse]`
  - `create_or_replace_dest_feed(db, *, feed_id, fiber_id, project_id, body) -> LookupDestFeedResponse`
  - `list_dest_entries(db, *, feed_id, fiber_id, project_id) -> list[LookupDestEntryResponse]`
  - `list_mappings(db, *, feed_id, fiber_id, project_id) -> list[LookupMappingResponse]`
  - `patch_mapping(db, *, feed_id, fiber_id, mapping_id, project_id, body) -> LookupMappingResponse`
  - `POST   /…/fibers/{fiber_id}/lookup-inputs` → `FiberResponse` 200
  - `GET    /…/fibers/{fiber_id}/source-entries` → `list[LookupSourceEntryResponse]` 200
  - `POST   /…/fibers/{fiber_id}/source-entries` → `list[LookupSourceEntryResponse]` 201
  - `POST   /…/fibers/{fiber_id}/dest-feed` → `LookupDestFeedResponse` 201
  - `GET    /…/fibers/{fiber_id}/dest-feed/entries` → `list[LookupDestEntryResponse]` 200
  - `GET    /…/fibers/{fiber_id}/mappings` → `list[LookupMappingResponse]` 200
  - `PATCH  /…/fibers/{fiber_id}/mappings/{mapping_id}` → `LookupMappingResponse` 200

---

- [ ] **Step 1: Write the failing tests**

Create `engine/tests/test_lookup_fiber_api.py`:

```python
from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import (
    Feed,
    ProjectDefinition,
    ProjectFiber,
    ProjectRegistry,
    User,
)
from migrations_engine.management import fibers as fibers_module
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fake AI adapter — reads destination_rows from the user message so it can
# return valid entry_ids without knowing them in advance.
# ---------------------------------------------------------------------------

class FakeLookupAdapter:
    model_id = "claude-sonnet-4-6"

    def __init__(self) -> None:
        self.calls: list[SimpleNamespace] = []

    def call(self, system: str, user: str, response_model: type) -> Any:
        import json
        self.calls.append(SimpleNamespace(system=system, user=user, response_model=response_model))
        data = json.loads(user)
        source_values: list[str] = data["source_values"]
        dest_rows: list[dict[str, Any]] = data["destination_rows"]
        first_id = dest_rows[0]["entry_id"] if dest_rows else "no-entry"
        proposals = [
            {"source_value": sv, "dest_entry_id": first_id, "confidence_score": 0.9}
            for sv in source_values
        ]
        return response_model(proposals=proposals)


# ---------------------------------------------------------------------------
# Module-level fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _setup_db() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == settings.bootstrap_admin_email.strip().lower())) is None:
            db.add(User(
                user_id=str(uuid.uuid4()),
                email=settings.bootstrap_admin_email.strip().lower(),
                display_name="Admin",
                password_hash=hash_password(settings.bootstrap_admin_password),
                role=CENTRAL_TEAM_ROLE,
                status="active",
            ))
        if db.scalar(select(User).where(User.email == "stakeholder-fiber@example.com")) is None:
            db.add(User(
                user_id=str(uuid.uuid4()),
                email="stakeholder-fiber@example.com",
                display_name="Stakeholder",
                password_hash=hash_password("stakeholder-fiber-pass"),
                role=PROJECT_STAKEHOLDER_ROLE,
                status="active",
            ))
        db.commit()


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _login_admin() -> str:
    settings = get_settings()
    r = client.post("/auth/login", json={
        "email": settings.bootstrap_admin_email,
        "password": settings.bootstrap_admin_password,
    })
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _login_stakeholder() -> str:
    r = client.post("/auth/login", json={
        "email": "stakeholder-fiber@example.com",
        "password": "stakeholder-fiber-pass",
    })
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed_project_and_feed() -> tuple[str, str]:
    """Return (project_id, feed_id)."""
    project_id = str(uuid.uuid4())
    feed_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(ProjectDefinition(project_id=project_id, name="Fiber AI Test", domain_config={}))
        db.add(ProjectRegistry(project_id=project_id, status="active"))
        db.add(Feed(
            source_definition_id=feed_id,
            project_id=project_id,
            source_type="csv",
            source_contract_version="v1",
        ))
        db.commit()
    return project_id, feed_id


def _create_fiber(project_id: str, feed_id: str, *, fiber_type: str = "lookup") -> str:
    """Return fiber_id (via API, fiber is in deferred status for lookup)."""
    token = _login_admin()
    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers",
        json={"fiber_type": fiber_type, "fiber_key": "account_type"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["fiber_id"]


_DEST_CSV = "id,description\n1,Database\n2,Savings\n3,Current"
_SOURCE_VALUES = ["DB", "SAV", "CUR"]


# ===========================================================================
# Tests: POST /lookup-inputs
# ===========================================================================

def test_lookup_inputs_transitions_fiber_to_mapped(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    token = _login_admin()
    fake = FakeLookupAdapter()
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: fake)

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": _SOURCE_VALUES, "destination_lookup_csv": _DEST_CSV},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "mapped"
    assert body["fiber_id"] == fiber_id
    assert body["proposed_mappings"] is not None
    assert len(body["proposed_mappings"]) == 3


def test_lookup_inputs_creates_source_entries_and_dest_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    token = _login_admin()
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": _SOURCE_VALUES, "destination_lookup_csv": _DEST_CSV},
        headers={"Authorization": f"Bearer {token}"},
    )

    src_r = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/source-entries",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert src_r.status_code == 200
    assert len(src_r.json()) == 3
    assert {e["source_value"] for e in src_r.json()} == {"DB", "SAV", "CUR"}

    dest_r = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed/entries",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dest_r.status_code == 200
    assert len(dest_r.json()) == 3


def test_lookup_inputs_creates_mapping_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    token = _login_admin()
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": _SOURCE_VALUES, "destination_lookup_csv": _DEST_CSV},
        headers={"Authorization": f"Bearer {token}"},
    )

    map_r = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert map_r.status_code == 200
    mappings = map_r.json()
    assert len(mappings) == 3
    for m in mappings:
        assert m["status"] == "proposed"
        assert m["mapped_by"] == "ai"
        assert m["confidence_score"] == pytest.approx(0.9)


def test_lookup_inputs_rejects_non_lookup_fiber(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id, fiber_type="domain_object")
    token = _login_admin()
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": _SOURCE_VALUES, "destination_lookup_csv": _DEST_CSV},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 409
    assert r.json()["error"]["code"] == "fiber_not_lookup"


def test_lookup_inputs_rejects_already_mapped_fiber(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    token = _login_admin()
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    # First call transitions to mapped
    client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": _SOURCE_VALUES, "destination_lookup_csv": _DEST_CSV},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Second call should be rejected
    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": _SOURCE_VALUES, "destination_lookup_csv": _DEST_CSV},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 409
    assert r.json()["error"]["code"] == "fiber_not_deferred"


def test_lookup_inputs_requires_central_team() -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    stakeholder_token = _login_stakeholder()

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": _SOURCE_VALUES, "destination_lookup_csv": _DEST_CSV},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )

    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_lookup_inputs_unauthenticated_returns_401() -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": _SOURCE_VALUES, "destination_lookup_csv": _DEST_CSV},
    )

    assert r.status_code == 401


# ===========================================================================
# Tests: GET /source-entries  and  POST /source-entries
# ===========================================================================

def test_get_source_entries_returns_empty_before_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    token = _login_admin()

    r = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/source-entries",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() == []


def test_post_source_entries_appends_new_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    token = _login_admin()
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    # Seed with initial inputs
    client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": ["DB"], "destination_lookup_csv": _DEST_CSV},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Append additional entries
    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/source-entries",
        json={"values": ["RETD", "CLSD"], "discovery_type": "delta"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    added = r.json()
    assert len(added) == 2
    assert {e["source_value"] for e in added} == {"RETD", "CLSD"}
    assert all(e["discovery_type"] == "delta" for e in added)

    # Verify total count is now 3 (1 original + 2 new)
    all_r = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/source-entries",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(all_r.json()) == 3


def test_post_source_entries_requires_central_team() -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    stakeholder_token = _login_stakeholder()

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/source-entries",
        json={"values": ["X"], "discovery_type": "sample"},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert r.status_code == 403


# ===========================================================================
# Tests: POST /dest-feed  and  GET /dest-feed/entries
# ===========================================================================

def test_post_dest_feed_creates_feed_and_entries() -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    token = _login_admin()

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed",
        json={
            "columns": ["id", "label"],
            "rows": [{"id": "1", "label": "Alpha"}, {"id": "2", "label": "Beta"}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["columns"] == ["id", "label"]
    assert body["fiber_id"] == fiber_id

    entries_r = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed/entries",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert entries_r.status_code == 200
    assert len(entries_r.json()) == 2


def test_post_dest_feed_replaces_existing_feed() -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    token = _login_admin()

    client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed",
        json={"columns": ["id"], "rows": [{"id": "1"}, {"id": "2"}, {"id": "3"}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed",
        json={"columns": ["code", "name"], "rows": [{"code": "A", "name": "Alpha"}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201

    entries_r = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed/entries",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Old 3 entries gone, new 1 entry present
    assert len(entries_r.json()) == 1
    assert entries_r.json()[0]["row_data"]["code"] == "A"


def test_post_dest_feed_requires_central_team() -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    stakeholder_token = _login_stakeholder()

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed",
        json={"columns": ["id"], "rows": [{"id": "1"}]},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert r.status_code == 403


# ===========================================================================
# Tests: GET /mappings  and  PATCH /mappings/{mapping_id}
# ===========================================================================

def test_get_mappings_returns_ai_proposals_after_lookup_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    token = _login_admin()
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": ["X", "Y"], "destination_lookup_csv": "id,label\n1,One\n2,Two"},
        headers={"Authorization": f"Bearer {token}"},
    )

    r = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_patch_mapping_updates_dest_and_sets_operator(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    token = _login_admin()
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": ["DB"], "destination_lookup_csv": "id,label\n1,One\n2,Two"},
        headers={"Authorization": f"Bearer {token}"},
    )
    mappings_r = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings",
        headers={"Authorization": f"Bearer {token}"},
    )
    mapping_id = mappings_r.json()[0]["mapping_id"]

    # Get dest entry ids from entries list
    entries_r = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed/entries",
        headers={"Authorization": f"Bearer {token}"},
    )
    second_entry_id = entries_r.json()[-1]["entry_id"]

    r = client.patch(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings/{mapping_id}",
        json={"dest_entry_id": second_entry_id, "status": "overridden"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "overridden"
    assert body["mapped_by"] == "operator"
    assert body["dest_entry_id"] == second_entry_id


def test_patch_mapping_accessible_to_stakeholder_with_project_access(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    admin_token = _login_admin()
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    # Add stakeholder membership to project
    with SessionLocal() as db:
        stakeholder = db.scalar(select(User).where(User.email == "stakeholder-fiber@example.com"))
        from migrations_engine.db.models import ProjectMembership
        db.add(ProjectMembership(project_id=project_id, user_id=stakeholder.user_id))
        db.commit()

    client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": ["DB"], "destination_lookup_csv": "id,label\n1,One"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    mappings_r = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    mapping_id = mappings_r.json()[0]["mapping_id"]
    entries_r = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed/entries",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    entry_id = entries_r.json()[0]["entry_id"]

    stakeholder_token = _login_stakeholder()
    r = client.patch(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings/{mapping_id}",
        json={"dest_entry_id": entry_id, "status": "confirmed"},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert r.status_code == 200
    assert r.json()["mapped_by"] == "operator"


def test_patch_mapping_returns_404_for_missing_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    token = _login_admin()

    r = client.patch(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings/nonexistent-id",
        json={"dest_entry_id": "any-id", "status": "confirmed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "mapping_not_found"
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_lookup_fiber_api.py -v
```

Expected: FAIL — `ImportError` on `LookupInputsRequest` (schema not yet added) or 404/405 (routes not yet added).

- [ ] **Step 3: Add `LookupInputsRequest` schema to `engine/src/migrations_engine/api/schemas.py`**

Add after the existing `LookupDestFeedCreateRequest` class (already present from 001ak):

```python
class LookupInputsRequest(BaseModel):
    source_values: list[str] = Field(min_length=1)
    destination_lookup_csv: str = Field(min_length=1)
```

- [ ] **Step 4: Add private AI models + helper functions to `engine/src/migrations_engine/management/fibers.py`**

Add these imports at the top of `management/fibers.py` (alongside existing imports):

```python
import csv
import io
import json
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..ai.factory import get_adapter
from ..api.deps import AuthApiError
from ..api.schemas import (
    FiberCreateRequest,
    FiberResponse,
    LookupDestEntryResponse,
    LookupDestFeedCreateRequest,
    LookupDestFeedResponse,
    LookupInputsRequest,
    LookupMappingPatchRequest,
    LookupMappingResponse,
    LookupSourceEntriesCreateRequest,
    LookupSourceEntryResponse,
)
from ..db.models import (
    Feed,
    LookupDestEntry,
    LookupDestFeed,
    LookupMapping,
    LookupSourceEntry,
    ProjectFiber,
    User,
)
```

Add these private models and constants after the imports and before any existing service functions:

```python
_LOOKUP_MAPPING_SYSTEM_PROMPT = (
    "You are a lookup value mapper. Given a list of source values and "
    "destination reference rows, propose the best match for each source value. "
    "Return a JSON array."
)


class _LookupProposal(BaseModel):
    source_value: str
    dest_entry_id: str
    confidence_score: float  # 0.0 to 1.0


class _LookupMappingResult(BaseModel):
    proposals: list[_LookupProposal]
```

Add these private helper functions (after `_to_response` and `_require_feed` which already exist from 001ak):

```python
def _require_lookup_fiber(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    project_id: str,
) -> ProjectFiber:
    """Load the fiber, validate it belongs to the feed/project, and is of type 'lookup'."""
    _require_feed(db, feed_id=feed_id, project_id=project_id)
    fiber = db.scalar(
        select(ProjectFiber).where(
            ProjectFiber.fiber_id == fiber_id,
            ProjectFiber.feed_id == feed_id,
        )
    )
    if fiber is None:
        raise AuthApiError("fiber_not_found", "Fiber not found.", 404)
    if fiber.fiber_type != "lookup":
        raise AuthApiError("fiber_not_lookup", "Fiber is not a lookup fiber.", 409)
    return fiber


def _parse_destination_csv(csv_text: str) -> tuple[list[str], list[dict[str, Any]]]:
    """Parse a header-first CSV string into (columns, rows)."""
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    columns = list(reader.fieldnames or [])
    rows = [dict(row) for row in reader]
    return columns, rows


def _source_entry_response(e: LookupSourceEntry) -> LookupSourceEntryResponse:
    return LookupSourceEntryResponse(
        entry_id=e.entry_id,
        fiber_id=e.fiber_id,
        lookup_name=e.lookup_name,
        source_value=e.source_value,
        discovery_type=e.discovery_type,
        created_at=e.created_at,
    )


def _dest_feed_response(f: LookupDestFeed) -> LookupDestFeedResponse:
    return LookupDestFeedResponse(
        dest_feed_id=f.dest_feed_id,
        fiber_id=f.fiber_id,
        lookup_name=f.lookup_name,
        columns=f.columns,
        created_at=f.created_at,
    )


def _dest_entry_response(e: LookupDestEntry) -> LookupDestEntryResponse:
    return LookupDestEntryResponse(
        entry_id=e.entry_id,
        dest_feed_id=e.dest_feed_id,
        row_data=e.row_data,
        created_at=e.created_at,
    )


def _mapping_response(m: LookupMapping) -> LookupMappingResponse:
    return LookupMappingResponse(
        mapping_id=m.mapping_id,
        fiber_id=m.fiber_id,
        lookup_name=m.lookup_name,
        source_entry_id=m.source_entry_id,
        source_value=m.source_value,
        dest_entry_id=m.dest_entry_id,
        dest_row=m.dest_row,
        confidence_score=m.confidence_score,
        status=m.status,
        mapped_by=m.mapped_by,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )
```

Add these service functions (after the existing `get_fiber` function from 001ak):

```python
def submit_lookup_inputs(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    project_id: str,
    body: LookupInputsRequest,
) -> FiberResponse:
    """
    Orchestrates the full deferred → mapped transition for a lookup fiber:
    1. Parse destination CSV into LookupDestFeed + LookupDestEntry rows.
    2. Create LookupSourceEntry rows from source_values.
    3. Advance fiber.status to "inputs_ready".
    4. Call the "lookup_mapping" AI slot.
    5. Persist LookupMapping rows (status="proposed", mapped_by="ai").
    6. Denormalize proposals into fiber.proposed_mappings.
    7. Advance fiber.status to "mapped".
    """
    fiber = _require_lookup_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)

    if fiber.status != "deferred":
        raise AuthApiError("fiber_not_deferred", "Fiber must be in 'deferred' status.", 409)

    # 1. Parse CSV → columns + rows
    columns, dest_rows = _parse_destination_csv(body.destination_lookup_csv)

    # 2. Create LookupDestFeed
    dest_feed = LookupDestFeed(
        fiber_id=fiber.fiber_id,
        lookup_name=fiber.fiber_key,
        columns=columns,
    )
    db.add(dest_feed)
    db.flush()

    # 3. Create LookupDestEntry rows
    dest_entries: list[LookupDestEntry] = []
    for row in dest_rows:
        entry = LookupDestEntry(dest_feed_id=dest_feed.dest_feed_id, row_data=row)
        db.add(entry)
        dest_entries.append(entry)
    db.flush()

    # 4. Create LookupSourceEntry rows (discovery_type="sample" for initial inputs)
    source_entries: list[LookupSourceEntry] = []
    for sv in body.source_values:
        entry = LookupSourceEntry(
            fiber_id=fiber.fiber_id,
            lookup_name=fiber.fiber_key,
            source_value=sv,
            discovery_type="sample",
        )
        db.add(entry)
        source_entries.append(entry)
    db.flush()

    # 5. Advance to inputs_ready
    fiber.status = "inputs_ready"
    db.flush()

    # 6. Call AI adapter
    adapter = get_adapter("lookup_mapping")
    user_message = json.dumps({
        "source_values": [e.source_value for e in source_entries],
        "destination_rows": [
            {"entry_id": e.entry_id, "row_data": e.row_data}
            for e in dest_entries
        ],
    })
    ai_result = adapter.call(_LOOKUP_MAPPING_SYSTEM_PROMPT, user_message, _LookupMappingResult)

    # 7. Index for fast lookup
    source_entry_by_value = {e.source_value: e for e in source_entries}
    dest_entry_by_id = {e.entry_id: e for e in dest_entries}

    # 8. Persist LookupMapping rows + build denorm list
    proposals_for_denorm: list[dict[str, Any]] = []
    for proposal in ai_result.proposals:
        source_entry = source_entry_by_value.get(proposal.source_value)
        if source_entry is None:
            continue  # AI returned an unknown source value; skip safely
        dest_entry = dest_entry_by_id.get(proposal.dest_entry_id)
        mapping = LookupMapping(
            fiber_id=fiber.fiber_id,
            lookup_name=fiber.fiber_key,
            source_entry_id=source_entry.entry_id,
            source_value=proposal.source_value,
            dest_entry_id=proposal.dest_entry_id if dest_entry else None,
            dest_row=dest_entry.row_data if dest_entry else None,
            confidence_score=proposal.confidence_score,
            status="proposed",
            mapped_by="ai",
        )
        db.add(mapping)
        proposals_for_denorm.append({
            "source_value": proposal.source_value,
            "dest_entry_id": proposal.dest_entry_id,
            "dest_row": dest_entry.row_data if dest_entry else None,
            "confidence_score": proposal.confidence_score,
        })

    # 9. Denormalize + final status
    fiber.proposed_mappings = proposals_for_denorm
    fiber.status = "mapped"

    db.commit()
    db.refresh(fiber)
    return _to_response(fiber)


def list_source_entries(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    project_id: str,
) -> list[LookupSourceEntryResponse]:
    fiber = _require_lookup_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    entries = db.scalars(
        select(LookupSourceEntry)
        .where(LookupSourceEntry.fiber_id == fiber.fiber_id)
        .order_by(LookupSourceEntry.created_at.asc())
    ).all()
    return [_source_entry_response(e) for e in entries]


def add_source_entries(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    project_id: str,
    body: LookupSourceEntriesCreateRequest,
) -> list[LookupSourceEntryResponse]:
    fiber = _require_lookup_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    new_entries: list[LookupSourceEntry] = []
    for sv in body.values:
        entry = LookupSourceEntry(
            fiber_id=fiber.fiber_id,
            lookup_name=fiber.fiber_key,
            source_value=sv,
            discovery_type=body.discovery_type,
        )
        db.add(entry)
        new_entries.append(entry)
    db.commit()
    for e in new_entries:
        db.refresh(e)
    return [_source_entry_response(e) for e in new_entries]


def create_or_replace_dest_feed(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    project_id: str,
    body: LookupDestFeedCreateRequest,
) -> LookupDestFeedResponse:
    fiber = _require_lookup_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)

    # Delete existing dest feed and all its entries before replacing
    existing = db.scalar(
        select(LookupDestFeed).where(LookupDestFeed.fiber_id == fiber.fiber_id)
    )
    if existing is not None:
        db.execute(
            delete(LookupDestEntry).where(
                LookupDestEntry.dest_feed_id == existing.dest_feed_id
            )
        )
        db.delete(existing)
        db.flush()

    dest_feed = LookupDestFeed(
        fiber_id=fiber.fiber_id,
        lookup_name=fiber.fiber_key,
        columns=body.columns,
    )
    db.add(dest_feed)
    db.flush()

    for row in body.rows:
        db.add(LookupDestEntry(dest_feed_id=dest_feed.dest_feed_id, row_data=row))

    db.commit()
    db.refresh(dest_feed)
    return _dest_feed_response(dest_feed)


def list_dest_entries(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    project_id: str,
) -> list[LookupDestEntryResponse]:
    fiber = _require_lookup_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    dest_feed = db.scalar(
        select(LookupDestFeed).where(LookupDestFeed.fiber_id == fiber.fiber_id)
    )
    if dest_feed is None:
        return []
    entries = db.scalars(
        select(LookupDestEntry)
        .where(LookupDestEntry.dest_feed_id == dest_feed.dest_feed_id)
        .order_by(LookupDestEntry.created_at.asc())
    ).all()
    return [_dest_entry_response(e) for e in entries]


def list_mappings(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    project_id: str,
) -> list[LookupMappingResponse]:
    fiber = _require_lookup_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    mappings = db.scalars(
        select(LookupMapping)
        .where(LookupMapping.fiber_id == fiber.fiber_id)
        .order_by(LookupMapping.created_at.asc())
    ).all()
    return [_mapping_response(m) for m in mappings]


def patch_mapping(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    mapping_id: str,
    project_id: str,
    body: LookupMappingPatchRequest,
) -> LookupMappingResponse:
    fiber = _require_lookup_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    mapping = db.scalar(
        select(LookupMapping).where(
            LookupMapping.mapping_id == mapping_id,
            LookupMapping.fiber_id == fiber.fiber_id,
        )
    )
    if mapping is None:
        raise AuthApiError("mapping_not_found", "Mapping not found.", 404)

    dest_entry = db.get(LookupDestEntry, body.dest_entry_id)
    mapping.dest_entry_id = body.dest_entry_id
    mapping.dest_row = dest_entry.row_data if dest_entry else None
    mapping.status = body.status
    mapping.mapped_by = "operator"

    db.commit()
    db.refresh(mapping)
    return _mapping_response(mapping)
```

- [ ] **Step 5: Add seven new route handlers to `engine/src/migrations_engine/routes/fibers.py`**

Add these imports alongside the existing imports in `routes/fibers.py`:

```python
from ..api.schemas import (
    FiberCreateRequest,
    FiberResponse,
    LookupDestEntryResponse,
    LookupDestFeedCreateRequest,
    LookupDestFeedResponse,
    LookupInputsRequest,
    LookupMappingPatchRequest,
    LookupMappingResponse,
    LookupSourceEntriesCreateRequest,
    LookupSourceEntryResponse,
)
from ..management.access import require_non_auditor, require_project_access
from ..management.fibers import (
    add_source_entries,
    create_fiber,
    create_or_replace_dest_feed,
    get_fiber,
    list_dest_entries,
    list_fibers,
    list_mappings,
    list_source_entries,
    patch_mapping,
    submit_lookup_inputs,
)
```

Add the following seven route handlers after the three existing routes (POST create, GET list, GET one):

```python
@router.post(
    "/{fiber_id}/lookup-inputs",
    response_model=FiberResponse,
    status_code=status.HTTP_200_OK,
)
def post_lookup_inputs(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    body: LookupInputsRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> FiberResponse:
    return submit_lookup_inputs(
        db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id, body=body
    )


@router.get("/{fiber_id}/source-entries", response_model=list[LookupSourceEntryResponse])
def get_source_entries(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LookupSourceEntryResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_source_entries(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)


@router.post(
    "/{fiber_id}/source-entries",
    response_model=list[LookupSourceEntryResponse],
    status_code=status.HTTP_201_CREATED,
)
def post_source_entries(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    body: LookupSourceEntriesCreateRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> list[LookupSourceEntryResponse]:
    return add_source_entries(
        db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id, body=body
    )


@router.post(
    "/{fiber_id}/dest-feed",
    response_model=LookupDestFeedResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_dest_feed(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    body: LookupDestFeedCreateRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> LookupDestFeedResponse:
    return create_or_replace_dest_feed(
        db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id, body=body
    )


@router.get("/{fiber_id}/dest-feed/entries", response_model=list[LookupDestEntryResponse])
def get_dest_feed_entries(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LookupDestEntryResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_dest_entries(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)


@router.get("/{fiber_id}/mappings", response_model=list[LookupMappingResponse])
def get_mappings(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LookupMappingResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_mappings(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)


@router.patch(
    "/{fiber_id}/mappings/{mapping_id}",
    response_model=LookupMappingResponse,
    status_code=status.HTTP_200_OK,
)
def patch_mapping_by_id(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    mapping_id: str,
    body: LookupMappingPatchRequest,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LookupMappingResponse:
    # Requires central_team or project_stakeholder (not read-only auditors)
    require_non_auditor(actor)
    require_project_access(db, user=actor, project_id=project_id)
    return patch_mapping(
        db,
        feed_id=feed_id,
        fiber_id=fiber_id,
        mapping_id=mapping_id,
        project_id=project_id,
        body=body,
    )
```

- [ ] **Step 6: Run Task 2 tests**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_lookup_fiber_api.py -v
```

Expected: all tests PASS.

- [ ] **Step 7: Run the full suite**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest -v
```

Expected: all tests PASS with no regressions.

- [ ] **Step 8: Commit**

```bash
git add \
  engine/src/migrations_engine/api/schemas.py \
  engine/src/migrations_engine/management/fibers.py \
  engine/src/migrations_engine/routes/fibers.py \
  engine/tests/test_lookup_fiber_api.py
git commit -m "feat(001al): add lookup fiber AI flow — lookup-inputs, source-entries, dest-feed, mappings endpoints"
```

---

## Verification Checklist

Before marking 001al complete, confirm:

- [ ] `get_adapter("lookup_mapping")` resolves to an `AnthropicAdapter` when `MODEL_LOOKUP_MAPPING` starts with `claude-`
- [ ] `POST /lookup-inputs` with valid inputs returns `{"status": "mapped", "proposed_mappings": [...]}` (monkeypatched)
- [ ] `POST /lookup-inputs` on a `domain_object` fiber returns `409 fiber_not_lookup`
- [ ] `POST /lookup-inputs` on a fiber already in `"mapped"` status returns `409 fiber_not_deferred`
- [ ] `POST /lookup-inputs` without auth returns `401`; with stakeholder token returns `403`
- [ ] `GET /source-entries` returns entries created by `POST /lookup-inputs`
- [ ] `POST /source-entries` appends rows (does not wipe existing)
- [ ] `POST /dest-feed` called twice replaces the first feed + all entries
- [ ] `GET /dest-feed/entries` returns empty list when no dest feed exists yet
- [ ] `GET /mappings` returns `status="proposed"` and `mapped_by="ai"` for AI-generated rows
- [ ] `PATCH /mappings/{id}` returns `mapped_by="operator"` and the updated `dest_entry_id`
- [ ] `PATCH /mappings/nonexistent` returns `404 mapping_not_found`
- [ ] Full pytest suite passes with no regressions
