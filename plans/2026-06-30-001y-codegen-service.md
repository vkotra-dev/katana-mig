Task: tasks/001y-codegen-service.md
Depends on: 001r (CodeGenerationArtifact model), 001s (AI adapter), 001w (approved MappingSnapshot), 001x (approved LookupSnapshot)

## Current State

- `CodeGenerationArtifact` exists in `db/models.py` (table `code_generation_artifacts`):
  fields: `codegen_artifact_id`, `project_id`, `destination_object_name`, `run_id` (nullable),
  `source_slice_version` (nullable), `mapping_snapshot_version` (nullable),
  `lookup_snapshot_version` (nullable), `sql_bundle` (Text), `status` (String(32), default="active"),
  `created_at`, `superseded_at` (nullable).
- `MigrationProjectConfig` is a Pydantic model at `api/schemas.py:109` with
  `target_db_engine: TargetDbEngine | None` and `staging_schema: str | None`.
  `TargetDbEngine = Literal["mssql", "oracle", "postgresql", "mysql"]`.
  Stored as `ProjectDefinition.domain_config` JSON.
- `ProjectRegistry.definition_id` → FK to `ProjectDefinition`.
- `SourceDefinition.destination_object_references: list[str] | None` — set by 001w approve step.
  This is how `source_definition_id` maps to `destination_object_name`.
- AI task slot for code generation: `"script_generation"` (in `ai/factory.py`).
- `select_latest_approved_mapping_snapshot(db, *, project_id, destination_object_name)` — raises
  `SnapshotNotFoundError` if none found.
- `select_latest_approved_lookup_snapshot(db, *, project_id, lookup_name)` — raises
  `SnapshotNotFoundError` if none found. Lookup snapshot is optional for codegen.
- `management/platform.py` exports `record_management_audit(db, *, project_id, actor_user_id, event_type, payload)`.
- `management/access.py` exports `require_project_access(db, *, user, project_id)`.
- `api/deps.py` exports `get_central_team_user`, `get_current_user`, `get_db`.
- Frontend: `listSourceContracts(token, projectId)` in `sources-api.ts` returns `SourceContractRecord[]`
  where `destinationObjectReferences: string[] | null`.
- No `codegen-api.ts` exists yet.
- App router: `web/app/projects/[id]/` has `page.tsx` and `sources/`.

## Blast Radius

| File | Action | What changes |
|---|---|---|
| `engine/src/migrations_engine/api/schemas.py` | modify | Add `CodegenTriggerResponse`, `CodegenArtifactResponse`, `DeliveryBundleResponse` |
| `engine/src/migrations_engine/management/codegen.py` | create | Service layer |
| `engine/src/migrations_engine/routes/codegen.py` | create | 4 API routes |
| `engine/src/migrations_engine/app.py` | modify | Register codegen router |
| `engine/tests/test_codegen_api.py` | create | API integration tests |
| `web/lib/codegen-api.ts` | create | API client + types |
| `web/app/projects/[id]/codegen/page.tsx` | create | Codegen review page |
| `web/app/projects/[id]/codegen/page.test.tsx` | create | Page unit tests |

## Backend Specification

### Schema additions — `engine/src/migrations_engine/api/schemas.py`

Append after the existing mapping-related schemas:

```python
class CodegenTriggerResponse(BaseModel):
    codegen_artifact_id: str
    project_id: str
    destination_object_name: str
    mapping_snapshot_version: str | None
    lookup_snapshot_version: str | None
    sql_bundle_preview: str   # first 500 chars of sql_bundle
    status: str
    created_at: datetime


class CodegenArtifactResponse(BaseModel):
    codegen_artifact_id: str
    project_id: str
    destination_object_name: str
    mapping_snapshot_version: str | None
    lookup_snapshot_version: str | None
    sql_bundle: str | None
    status: str
    created_at: datetime
    superseded_at: datetime | None


class DeliveryBundleResponse(BaseModel):
    project_id: str
    artifacts: list[CodegenArtifactResponse]
```

### Service layer — `engine/src/migrations_engine/management/codegen.py`

```python
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.adapter import AIAdapter
from ..api.deps import AuthApiError
from ..api.schemas import (
    CodegenArtifactResponse,
    CodegenTriggerResponse,
    DeliveryBundleResponse,
    MigrationProjectConfig,
)
from ..db.models import (
    CodeGenerationArtifact,
    ProjectDefinition,
    ProjectRegistry,
    SourceDefinition,
    new_id,
)
from ..mapping.exceptions import SnapshotNotFoundError
from ..mapping.snapshots import (
    select_latest_approved_lookup_snapshot,
    select_latest_approved_mapping_snapshot,
)
from .platform import record_management_audit


class _GeneratedSQL(BaseModel):
    staging_table_ddl: str
    views: list[str]
    notes: str | None = None


def _get_project_config(db: Session, *, project_id: str) -> MigrationProjectConfig:
    registry = db.scalar(
        select(ProjectRegistry).where(ProjectRegistry.project_id == project_id)
    )
    if registry is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)
    definition = db.scalar(
        select(ProjectDefinition).where(
            ProjectDefinition.definition_id == registry.definition_id
        )
    )
    raw = (definition.domain_config or {}) if definition else {}
    return MigrationProjectConfig.model_validate(raw)


def _resolve_destination_object_name(
    db: Session, *, project_id: str, source_definition_id: str
) -> str:
    source = db.scalar(
        select(SourceDefinition).where(
            SourceDefinition.source_definition_id == source_definition_id,
            SourceDefinition.project_id == project_id,
        )
    )
    if source is None:
        raise AuthApiError("source_not_found", "Source definition not found.", 404)
    refs = source.destination_object_references or []
    if not refs:
        raise AuthApiError(
            "mapping_not_approved",
            "Source has no approved mapping. Approve the mapping before generating SQL.",
            409,
        )
    return refs[0]


def _artifact_to_response(artifact: CodeGenerationArtifact) -> CodegenArtifactResponse:
    return CodegenArtifactResponse(
        codegen_artifact_id=artifact.codegen_artifact_id,
        project_id=artifact.project_id,
        destination_object_name=artifact.destination_object_name,
        mapping_snapshot_version=artifact.mapping_snapshot_version,
        lookup_snapshot_version=artifact.lookup_snapshot_version,
        sql_bundle=artifact.sql_bundle,
        status=artifact.status,
        created_at=artifact.created_at,
        superseded_at=artifact.superseded_at,
    )


def _supersede_previous(
    db: Session, *, project_id: str, destination_object_name: str
) -> None:
    now = datetime.now(UTC)
    db.query(CodeGenerationArtifact).filter_by(
        project_id=project_id,
        destination_object_name=destination_object_name,
        status="active",
    ).update({"status": "superseded", "superseded_at": now})


def trigger_codegen(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    actor_user_id: str,
    adapter: AIAdapter,
) -> CodegenTriggerResponse:
    destination_object_name = _resolve_destination_object_name(
        db, project_id=project_id, source_definition_id=source_definition_id
    )
    project_config = _get_project_config(db, project_id=project_id)
    try:
        mapping_snapshot = select_latest_approved_mapping_snapshot(
            db, project_id=project_id, destination_object_name=destination_object_name
        )
    except SnapshotNotFoundError:
        raise AuthApiError(
            "mapping_not_found",
            "No approved mapping snapshot found for this source.",
            409,
        )
    # Lookup snapshot is optional — codegen proceeds even without one
    lookup_snapshot_version: str | None = None
    lookup_info = ""
    for binding in mapping_snapshot.field_bindings:
        lookup_name = binding.get("lookup_name")
        if lookup_name:
            try:
                ls = select_latest_approved_lookup_snapshot(
                    db, project_id=project_id, lookup_name=lookup_name
                )
                lookup_snapshot_version = ls.lookup_snapshot_version
                lookup_info = f"\nLookup table '{lookup_name}' maps source values via approved snapshot."
                break
            except SnapshotNotFoundError:
                pass

    staging_table = f"stg_{destination_object_name.lower().replace(' ', '_')}"
    target_db = project_config.target_db_engine or "mssql"
    staging_schema = project_config.staging_schema or "staging"

    generated = adapter.call(
        system=(
            "You are a data migration SQL specialist. Generate DDL for a staging table "
            "and optional helper views for a given field mapping. Output ONLY a JSON object "
            "with 'staging_table_ddl' (a CREATE TABLE statement), 'views' (list of CREATE VIEW "
            "statements, may be empty), and 'notes' (optional string describing assumptions). "
            f"Target database engine: {target_db}. "
            "Standard audit columns to add: _katana_run_id NVARCHAR(36), "
            "_katana_loaded_at DATETIME2, _katana_source_slice_version NVARCHAR(255). "
            "Map TEXT source fields to VARCHAR(255), INTEGER to INT, BOOLEAN to BIT (mssql) "
            "or BOOLEAN (postgres). Do not add NOT NULL constraints on mapped columns."
        ),
        user=(
            f"Destination object: {destination_object_name}\n"
            f"Staging table name: {staging_schema}.{staging_table}\n"
            f"Field bindings: {mapping_snapshot.field_bindings!r}\n"
            f"{lookup_info}"
        ),
        response_model=_GeneratedSQL,
    )

    sql_bundle = generated.staging_table_ddl
    if generated.views:
        sql_bundle += "\n\n" + "\n\n".join(generated.views)

    _supersede_previous(
        db, project_id=project_id, destination_object_name=destination_object_name
    )

    artifact = CodeGenerationArtifact(
        codegen_artifact_id=new_id(),
        project_id=project_id,
        destination_object_name=destination_object_name,
        mapping_snapshot_version=mapping_snapshot.mapping_snapshot_version,
        lookup_snapshot_version=lookup_snapshot_version,
        sql_bundle=sql_bundle,
        status="active",
    )
    db.add(artifact)
    db.flush()

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="codegen_triggered",
        payload={
            "codegen_artifact_id": artifact.codegen_artifact_id,
            "destination_object_name": destination_object_name,
            "model_id": adapter.model_id,
            "notes": generated.notes,
        },
    )
    db.commit()
    db.refresh(artifact)

    return CodegenTriggerResponse(
        codegen_artifact_id=artifact.codegen_artifact_id,
        project_id=artifact.project_id,
        destination_object_name=artifact.destination_object_name,
        mapping_snapshot_version=artifact.mapping_snapshot_version,
        lookup_snapshot_version=artifact.lookup_snapshot_version,
        sql_bundle_preview=(artifact.sql_bundle or "")[:500],
        status=artifact.status,
        created_at=artifact.created_at,
    )


def list_codegen_artifacts(
    db: Session,
    *,
    project_id: str,
    status_filter: str | None = None,
) -> list[CodegenArtifactResponse]:
    stmt = select(CodeGenerationArtifact).where(
        CodeGenerationArtifact.project_id == project_id
    )
    if status_filter:
        stmt = stmt.where(CodeGenerationArtifact.status == status_filter)
    stmt = stmt.order_by(CodeGenerationArtifact.created_at.desc())
    artifacts = db.scalars(stmt).all()
    return [_artifact_to_response(a) for a in artifacts]


def get_codegen_artifact(
    db: Session,
    *,
    project_id: str,
    codegen_artifact_id: str,
) -> CodegenArtifactResponse:
    artifact = db.scalar(
        select(CodeGenerationArtifact).where(
            CodeGenerationArtifact.codegen_artifact_id == codegen_artifact_id,
            CodeGenerationArtifact.project_id == project_id,
        )
    )
    if artifact is None:
        raise AuthApiError("artifact_not_found", "Code generation artifact not found.", 404)
    return _artifact_to_response(artifact)


def get_delivery_bundle(
    db: Session,
    *,
    project_id: str,
) -> DeliveryBundleResponse:
    artifacts = list_codegen_artifacts(db, project_id=project_id, status_filter="active")
    return DeliveryBundleResponse(project_id=project_id, artifacts=artifacts)
```

### Routes — `engine/src/migrations_engine/routes/codegen.py`

```python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..ai.factory import get_adapter
from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import (
    CodegenArtifactResponse,
    CodegenTriggerResponse,
    DeliveryBundleResponse,
)
from ..db.models import User
from ..management.access import require_project_access
from ..management.codegen import (
    get_codegen_artifact,
    get_delivery_bundle,
    list_codegen_artifacts,
    trigger_codegen,
)

router = APIRouter(tags=["codegen"])


@router.post(
    "/projects/{project_id}/sources/{source_definition_id}/codegen",
    response_model=CodegenTriggerResponse,
)
def post_codegen(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> CodegenTriggerResponse:
    require_project_access(db, user=actor, project_id=project_id)
    adapter = get_adapter("script_generation")
    return trigger_codegen(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        actor_user_id=actor.user_id,
        adapter=adapter,
    )


@router.get(
    "/projects/{project_id}/codegen-artifacts",
    response_model=list[CodegenArtifactResponse],
)
def get_codegen_artifacts(
    project_id: str,
    status: Annotated[str | None, Query()] = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CodegenArtifactResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_codegen_artifacts(db, project_id=project_id, status_filter=status)


@router.get(
    "/projects/{project_id}/codegen-artifacts/{codegen_artifact_id}",
    response_model=CodegenArtifactResponse,
)
def get_one_codegen_artifact(
    project_id: str,
    codegen_artifact_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CodegenArtifactResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_codegen_artifact(
        db, project_id=project_id, codegen_artifact_id=codegen_artifact_id
    )


@router.get(
    "/projects/{project_id}/delivery-bundle",
    response_model=DeliveryBundleResponse,
)
def get_project_delivery_bundle(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeliveryBundleResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_delivery_bundle(db, project_id=project_id)
```

### App registration — `engine/src/migrations_engine/app.py`

After the existing router imports, add:

```python
from .routes.codegen import router as codegen_router
```

After `app.include_router(slice_approval_router)`, add:

```python
app.include_router(codegen_router)
```

### Backend tests — `engine/tests/test_codegen_api.py`

```python
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import (
    CodeGenerationArtifact,
    MappingSnapshot,
    ProjectDefinition,
    ProjectRegistry,
    SourceDefinition,
    User,
)
from migrations_engine.management import codegen as codegen_module
from migrations_engine.roles import CENTRAL_TEAM_ROLE

client = TestClient(app)


class FakeAdapter:
    def __init__(self) -> None:
        self.model_id = "claude-sonnet-4-6"
        self.calls: list[SimpleNamespace] = []

    def call(self, system: str, user: str, response_model):
        self.calls.append(SimpleNamespace(system=system, user=user))
        return response_model(
            staging_table_ddl=(
                "CREATE TABLE staging.stg_customer (\n"
                "  customer_id INT,\n"
                "  full_name VARCHAR(255),\n"
                "  _katana_run_id NVARCHAR(36),\n"
                "  _katana_loaded_at DATETIME2,\n"
                "  _katana_source_slice_version NVARCHAR(255)\n"
                ");"
            ),
            views=[],
            notes="All text columns mapped to VARCHAR(255).",
        )


@pytest.fixture(scope="module", autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=TEST_ENGINE)
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")
    with SessionLocal() as db:
        db.add(User(
            user_id=str(uuid.uuid4()),
            email=settings.bootstrap_admin_email.strip().lower(),
            display_name="Admin",
            password_hash=hash_password(settings.bootstrap_admin_password),
            role=CENTRAL_TEAM_ROLE,
            status="active",
        ))
        db.commit()


def _login() -> str:
    settings = get_settings()
    resp = client.post("/auth/login", json={
        "email": settings.bootstrap_admin_email,
        "password": settings.bootstrap_admin_password,
    })
    return resp.json()["access_token"]


def _seed_project(db, *, staging_schema: str = "staging") -> tuple[str, str]:
    """Returns (project_id, source_definition_id)."""
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    destination_object_name = "Customer"
    domain_config = {
        "target_db_engine": "mssql",
        "staging_schema": staging_schema,
        "destination_schema_ddl": (
            "CREATE TABLE Customer (customer_id INT, full_name VARCHAR(255));"
        ),
    }
    db.add(ProjectDefinition(
        definition_id=definition_id,
        project_id=project_id,
        name="Codegen Test Project",
        status="active",
        domain_config=domain_config,
    ))
    db.add(ProjectRegistry(
        project_id=project_id,
        name="Codegen Test Project",
        definition_id=definition_id,
        status="active",
    ))
    db.add(SourceDefinition(
        source_definition_id=source_id,
        project_id=project_id,
        source_type="csv",
        label="Customers",
        encoding="utf-8",
        status="approved",
        destination_object_references=[destination_object_name],
    ))
    db.add(MappingSnapshot(
        mapping_snapshot_id=str(uuid.uuid4()),
        project_id=project_id,
        destination_object_name=destination_object_name,
        mapping_snapshot_version="v1",
        field_bindings=[
            {"source_field": "cust_id", "destination_field": "customer_id", "lookup_name": None},
            {"source_field": "name", "destination_field": "full_name", "lookup_name": None},
        ],
        status="approved",
    ))
    db.commit()
    return project_id, source_id


def test_trigger_codegen_creates_active_artifact(monkeypatch):
    token = _login()
    fake = FakeAdapter()
    monkeypatch.setattr(codegen_module, "get_adapter", lambda task: fake)
    with SessionLocal() as db:
        project_id, source_id = _seed_project(db)
    resp = client.post(
        f"/projects/{project_id}/sources/{source_id}/codegen",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert data["destination_object_name"] == "Customer"
    assert "stg_customer" in data["sql_bundle_preview"]
    assert data["mapping_snapshot_version"] == "v1"


def test_trigger_codegen_supersedes_previous(monkeypatch):
    token = _login()
    fake = FakeAdapter()
    monkeypatch.setattr(codegen_module, "get_adapter", lambda task: fake)
    with SessionLocal() as db:
        project_id, source_id = _seed_project(db)
    # First trigger
    resp1 = client.post(
        f"/projects/{project_id}/sources/{source_id}/codegen",
        headers={"Authorization": f"Bearer {token}"},
    )
    first_id = resp1.json()["codegen_artifact_id"]
    # Second trigger
    resp2 = client.post(
        f"/projects/{project_id}/sources/{source_id}/codegen",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    second_id = resp2.json()["codegen_artifact_id"]
    assert first_id != second_id
    # First is now superseded
    with SessionLocal() as db:
        first = db.get(CodeGenerationArtifact, first_id)
        second = db.get(CodeGenerationArtifact, second_id)
    assert first.status == "superseded"
    assert first.superseded_at is not None
    assert second.status == "active"


def test_trigger_codegen_409_when_no_approved_mapping(monkeypatch):
    token = _login()
    fake = FakeAdapter()
    monkeypatch.setattr(codegen_module, "get_adapter", lambda task: fake)
    with SessionLocal() as db:
        project_id = str(uuid.uuid4())
        definition_id = str(uuid.uuid4())
        source_id = str(uuid.uuid4())
        db.add(ProjectDefinition(
            definition_id=definition_id,
            project_id=project_id,
            name="No Mapping Project",
            status="active",
            domain_config={},
        ))
        db.add(ProjectRegistry(
            project_id=project_id,
            name="No Mapping Project",
            definition_id=definition_id,
            status="active",
        ))
        db.add(SourceDefinition(
            source_definition_id=source_id,
            project_id=project_id,
            source_type="csv",
            label="Customers",
            encoding="utf-8",
            status="approved",
            destination_object_references=None,  # no approved mapping
        ))
        db.commit()
    resp = client.post(
        f"/projects/{project_id}/sources/{source_id}/codegen",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "mapping_not_approved"


def test_list_artifacts_with_status_filter(monkeypatch):
    token = _login()
    fake = FakeAdapter()
    monkeypatch.setattr(codegen_module, "get_adapter", lambda task: fake)
    with SessionLocal() as db:
        project_id, source_id = _seed_project(db)
    client.post(f"/projects/{project_id}/sources/{source_id}/codegen",
                headers={"Authorization": f"Bearer {token}"})
    client.post(f"/projects/{project_id}/sources/{source_id}/codegen",
                headers={"Authorization": f"Bearer {token}"})
    resp_active = client.get(
        f"/projects/{project_id}/codegen-artifacts?status=active",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_active.status_code == 200
    assert len(resp_active.json()) == 1
    assert resp_active.json()[0]["status"] == "active"
    resp_superseded = client.get(
        f"/projects/{project_id}/codegen-artifacts?status=superseded",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(resp_superseded.json()) == 1
    assert resp_superseded.json()[0]["status"] == "superseded"


def test_get_one_artifact_returns_full_sql_bundle(monkeypatch):
    token = _login()
    fake = FakeAdapter()
    monkeypatch.setattr(codegen_module, "get_adapter", lambda task: fake)
    with SessionLocal() as db:
        project_id, source_id = _seed_project(db)
    trigger_resp = client.post(
        f"/projects/{project_id}/sources/{source_id}/codegen",
        headers={"Authorization": f"Bearer {token}"},
    )
    artifact_id = trigger_resp.json()["codegen_artifact_id"]
    resp = client.get(
        f"/projects/{project_id}/codegen-artifacts/{artifact_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "CREATE TABLE" in resp.json()["sql_bundle"]


def test_delivery_bundle_returns_only_active(monkeypatch):
    token = _login()
    fake = FakeAdapter()
    monkeypatch.setattr(codegen_module, "get_adapter", lambda task: fake)
    with SessionLocal() as db:
        project_id, source_id = _seed_project(db)
    client.post(f"/projects/{project_id}/sources/{source_id}/codegen",
                headers={"Authorization": f"Bearer {token}"})
    client.post(f"/projects/{project_id}/sources/{source_id}/codegen",
                headers={"Authorization": f"Bearer {token}"})
    resp = client.get(
        f"/projects/{project_id}/delivery-bundle",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert len(data["artifacts"]) == 1
    assert data["artifacts"][0]["status"] == "active"
```

## Frontend Specification

### API client — `web/lib/codegen-api.ts`

```typescript
import { jsonRequest } from "./api-base";

export interface CodegenTriggerRecord {
  codegenArtifactId: string;
  projectId: string;
  destinationObjectName: string;
  mappingSnapshotVersion: string | null;
  lookupSnapshotVersion: string | null;
  sqlBundlePreview: string;
  status: string;
  createdAt: string;
}

export interface CodegenArtifactRecord {
  codegenArtifactId: string;
  projectId: string;
  destinationObjectName: string;
  mappingSnapshotVersion: string | null;
  lookupSnapshotVersion: string | null;
  sqlBundle: string | null;
  status: string;
  createdAt: string;
  supersededAt: string | null;
}

export interface DeliveryBundleRecord {
  projectId: string;
  artifacts: CodegenArtifactRecord[];
}

function mapArtifact(r: {
  codegen_artifact_id: string;
  project_id: string;
  destination_object_name: string;
  mapping_snapshot_version: string | null;
  lookup_snapshot_version: string | null;
  sql_bundle: string | null;
  status: string;
  created_at: string;
  superseded_at: string | null;
}): CodegenArtifactRecord {
  return {
    codegenArtifactId: r.codegen_artifact_id,
    projectId: r.project_id,
    destinationObjectName: r.destination_object_name,
    mappingSnapshotVersion: r.mapping_snapshot_version,
    lookupSnapshotVersion: r.lookup_snapshot_version,
    sqlBundle: r.sql_bundle,
    status: r.status,
    createdAt: r.created_at,
    supersededAt: r.superseded_at,
  };
}

export async function triggerCodegen(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<CodegenTriggerRecord> {
  const r = await jsonRequest<{
    codegen_artifact_id: string;
    project_id: string;
    destination_object_name: string;
    mapping_snapshot_version: string | null;
    lookup_snapshot_version: string | null;
    sql_bundle_preview: string;
    status: string;
    created_at: string;
  }>(`/projects/${projectId}/sources/${sourceDefinitionId}/codegen`, {
    method: "POST",
    token,
  });
  return {
    codegenArtifactId: r.codegen_artifact_id,
    projectId: r.project_id,
    destinationObjectName: r.destination_object_name,
    mappingSnapshotVersion: r.mapping_snapshot_version,
    lookupSnapshotVersion: r.lookup_snapshot_version,
    sqlBundlePreview: r.sql_bundle_preview,
    status: r.status,
    createdAt: r.created_at,
  };
}

export async function listCodegenArtifacts(
  token: string,
  projectId: string,
  status?: "active" | "superseded",
): Promise<CodegenArtifactRecord[]> {
  const qs = status ? `?status=${status}` : "";
  const rs = await jsonRequest<ReturnType<typeof mapArtifact>[]>(
    `/projects/${projectId}/codegen-artifacts${qs}`,
    { method: "GET", token },
  );
  return rs.map(mapArtifact);
}

export async function getCodegenArtifact(
  token: string,
  projectId: string,
  codegenArtifactId: string,
): Promise<CodegenArtifactRecord> {
  const r = await jsonRequest<ReturnType<typeof mapArtifact>>(
    `/projects/${projectId}/codegen-artifacts/${codegenArtifactId}`,
    { method: "GET", token },
  );
  return mapArtifact(r);
}

export async function getDeliveryBundle(
  token: string,
  projectId: string,
): Promise<DeliveryBundleRecord> {
  const r = await jsonRequest<{
    project_id: string;
    artifacts: ReturnType<typeof mapArtifact>[];
  }>(`/projects/${projectId}/delivery-bundle`, { method: "GET", token });
  return {
    projectId: r.project_id,
    artifacts: r.artifacts.map(mapArtifact),
  };
}
```

**Important:** check `api-base.ts` for the exact `jsonRequest` signature before writing — the existing clients (e.g. `mapping-api.ts`) show the correct call pattern.

### Codegen page — `web/app/projects/[id]/codegen/page.tsx`

Layout: two tabs — "SQL Artifacts" and "Delivery Bundle".

**SQL Artifacts tab**: table of sources that have `destinationObjectReferences` set; per-row "Generate SQL" button (central_team only) and latest active artifact preview (truncated SQL in a `<pre>` block with copy button); collapsible superseded history per source.

**Delivery Bundle tab**: table of all active artifacts across the project; "Download Bundle" button that concatenates all `sql_bundle` strings with `-- [destination_object_name]` separators and triggers a `Blob` download as `delivery-bundle.sql`.

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Topbar } from "../../../../components/Topbar";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../lib/session";
import { listSourceContracts, type SourceContractRecord } from "../../../../lib/sources-api";
import {
  getDeliveryBundle,
  listCodegenArtifacts,
  triggerCodegen,
  type CodegenArtifactRecord,
} from "../../../../lib/codegen-api";

type Tab = "artifacts" | "bundle";

export default function CodegenPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = params.id;

  const [session, setSession] = useState<UiSession | null>(null);
  const [tab, setTab] = useState<Tab>("artifacts");
  const [sources, setSources] = useState<SourceContractRecord[]>([]);
  const [artifacts, setArtifacts] = useState<CodegenArtifactRecord[]>([]);
  const [bundleArtifacts, setBundleArtifacts] = useState<CodegenArtifactRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  // per-source generating state: sourceId → "idle" | "generating" | "error"
  const [generatingMap, setGeneratingMap] = useState<Record<string, "idle" | "generating" | "error">>({});
  const [generateErrors, setGenerateErrors] = useState<Record<string, string>>({});
  // expanded superseded sections: destinationObjectName → boolean
  const [expandedHistory, setExpandedHistory] = useState<Record<string, boolean>>({});
  const [supersededMap, setSupersededMap] = useState<Record<string, CodegenArtifactRecord[]>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    setSession(loadUiSession());
  }, []);

  useEffect(() => {
    if (!session) return;
    let active = true;
    void Promise.all([
      listSourceContracts(session.accessToken, projectId),
      listCodegenArtifacts(session.accessToken, projectId),
      getDeliveryBundle(session.accessToken, projectId),
    ]).then(([srcs, arts, bundle]) => {
      if (!active) return;
      setSources(srcs);
      setArtifacts(arts.filter((a) => a.status === "active"));
      setBundleArtifacts(bundle.artifacts);
      setLoading(false);
    }).catch((e: unknown) => {
      if (active) {
        setErrorMessage(e instanceof Error ? e.message : "Failed to load codegen data.");
        setLoading(false);
      }
    });
    return () => { active = false; };
  }, [session, projectId]);

  async function handleGenerate(sourceId: string) {
    if (!session) return;
    setGeneratingMap((prev) => ({ ...prev, [sourceId]: "generating" }));
    setGenerateErrors((prev) => { const n = { ...prev }; delete n[sourceId]; return n; });
    try {
      await triggerCodegen(session.accessToken, projectId, sourceId);
      // Reload artifacts and bundle after generation
      const [arts, bundle] = await Promise.all([
        listCodegenArtifacts(session.accessToken, projectId),
        getDeliveryBundle(session.accessToken, projectId),
      ]);
      setArtifacts(arts.filter((a) => a.status === "active"));
      setBundleArtifacts(bundle.artifacts);
      setGeneratingMap((prev) => ({ ...prev, [sourceId]: "idle" }));
    } catch (e: unknown) {
      setGeneratingMap((prev) => ({ ...prev, [sourceId]: "error" }));
      setGenerateErrors((prev) => ({
        ...prev,
        [sourceId]: e instanceof Error ? e.message : "Generation failed.",
      }));
    }
  }

  async function handleExpandHistory(destinationObjectName: string) {
    if (!session) return;
    if (expandedHistory[destinationObjectName]) {
      setExpandedHistory((prev) => ({ ...prev, [destinationObjectName]: false }));
      return;
    }
    const all = await listCodegenArtifacts(session.accessToken, projectId);
    const superseded = all.filter(
      (a) => a.status === "superseded" && a.destinationObjectName === destinationObjectName
    );
    setSupersededMap((prev) => ({ ...prev, [destinationObjectName]: superseded }));
    setExpandedHistory((prev) => ({ ...prev, [destinationObjectName]: true }));
  }

  function handleDownloadBundle() {
    if (!bundleArtifacts.length) return;
    const content = bundleArtifacts
      .map((a) => `-- ${a.destinationObjectName}\n${a.sqlBundle ?? ""}`)
      .join("\n\n");
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "delivery-bundle.sql";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleCopy(text: string, id: string) {
    await navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  }

  const role: SessionRole = session?.role ?? "read_only_auditor";
  const canAct = role === "central_team";
  const mappedSources = sources.filter(
    (s) => s.destinationObjectReferences && s.destinationObjectReferences.length > 0
  );

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-6">
        <div className="flex items-center gap-2 text-xs text-neutral">
          <button
            className="hover:text-primary hover:underline"
            onClick={() => { router.back(); }}
            type="button"
          >
            ← Back
          </button>
          <span className="text-slate-300">|</span>
          <span className="font-mono uppercase tracking-wider">SQL Code Generation</span>
        </div>

        {errorMessage && (
          <div role="alert" className="rounded border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
            {errorMessage}
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2">
          {(["artifacts", "bundle"] as Tab[]).map((t) => (
            <button
              key={t}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                tab === t
                  ? "bg-primary text-white"
                  : "border border-outline-variant bg-surface-container text-slate-700 hover:bg-outline-variant"
              }`}
              onClick={() => setTab(t)}
              type="button"
            >
              {t === "artifacts" ? "SQL Artifacts" : "Delivery Bundle"}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            Loading…
          </div>
        ) : tab === "artifacts" ? (
          /* SQL Artifacts tab */
          <div className="space-y-4">
            {mappedSources.length === 0 && (
              <div className="rounded-2xl border border-dashed border-outline-variant bg-surface-container p-10 text-center text-sm text-neutral font-mono">
                No sources with approved mappings. Approve a field mapping first.
              </div>
            )}
            {mappedSources.map((source) => {
              const destName = source.destinationObjectReferences![0];
              const activeArtifact = artifacts.find(
                (a) => a.destinationObjectName === destName
              );
              const genState = generatingMap[source.sourceDefinitionId] ?? "idle";
              const genError = generateErrors[source.sourceDefinitionId];
              const historyExpanded = expandedHistory[destName] ?? false;
              const historyArtifacts = supersededMap[destName] ?? [];

              return (
                <div
                  key={source.sourceDefinitionId}
                  className="rounded-2xl border border-outline-variant bg-surface-container p-5 shadow-sm space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-mono font-bold text-primary uppercase">
                        {destName}
                      </p>
                      <p className="text-[10px] text-neutral mt-0.5">
                        {source.label} · {source.sourceDefinitionId.slice(0, 8)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {activeArtifact && (
                        <span className="status-chip rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 text-[10px] font-bold text-emerald-600 uppercase font-mono">
                          active
                        </span>
                      )}
                      {canAct && (
                        <button
                          className="rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-white hover:opacity-95 disabled:opacity-60 transition"
                          disabled={genState === "generating"}
                          onClick={() => { void handleGenerate(source.sourceDefinitionId); }}
                          type="button"
                        >
                          {genState === "generating"
                            ? "Generating…"
                            : activeArtifact
                            ? "Regenerate SQL"
                            : "Generate SQL"}
                        </button>
                      )}
                    </div>
                  </div>

                  {genError && (
                    <p className="rounded bg-error/10 border border-error/20 p-2 text-[10px] font-mono text-error">
                      {genError}
                    </p>
                  )}

                  {activeArtifact?.sqlBundle && (
                    <div className="relative">
                      <pre className="max-h-48 overflow-y-auto rounded-lg border border-outline-variant bg-slate-900 p-3 text-[11px] text-emerald-300 font-mono leading-relaxed whitespace-pre-wrap">
                        {activeArtifact.sqlBundle}
                      </pre>
                      <button
                        className="absolute right-2 top-2 rounded bg-slate-700 px-2 py-1 text-[10px] font-mono text-slate-200 hover:bg-slate-600 transition"
                        onClick={() => { void handleCopy(activeArtifact.sqlBundle!, activeArtifact.codegenArtifactId); }}
                        type="button"
                      >
                        {copiedId === activeArtifact.codegenArtifactId ? "Copied!" : "Copy"}
                      </button>
                      <p className="mt-1 text-[10px] text-neutral font-mono">
                        Mapping v{activeArtifact.mappingSnapshotVersion} · Generated {activeArtifact.createdAt.slice(0, 10)}
                      </p>
                    </div>
                  )}

                  <button
                    className="text-[10px] font-mono text-neutral hover:text-primary underline transition"
                    onClick={() => { void handleExpandHistory(destName); }}
                    type="button"
                  >
                    {historyExpanded ? "Hide" : "Show"} superseded history
                  </button>

                  {historyExpanded && (
                    <div className="space-y-2 pt-1">
                      {historyArtifacts.length === 0 ? (
                        <p className="text-[10px] text-neutral font-mono">No superseded artifacts.</p>
                      ) : historyArtifacts.map((a) => (
                        <div
                          key={a.codegenArtifactId}
                          className="rounded border border-outline-variant bg-surface p-3 text-[10px] text-neutral font-mono"
                        >
                          {a.codegenArtifactId.slice(0, 8)} · mapping v{a.mappingSnapshotVersion} ·
                          generated {a.createdAt.slice(0, 10)} · superseded {a.supersededAt?.slice(0, 10) ?? "—"}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          /* Delivery Bundle tab */
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-neutral">
                  Delivery Bundle
                </p>
                <h2 className="mt-0.5 text-sm font-bold text-slate-900 uppercase">
                  Active SQL Artifacts — {bundleArtifacts.length} object{bundleArtifacts.length !== 1 ? "s" : ""}
                </h2>
              </div>
              {bundleArtifacts.length > 0 && (
                <button
                  className="rounded-md bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800 transition"
                  onClick={handleDownloadBundle}
                  type="button"
                >
                  Download Bundle (.sql)
                </button>
              )}
            </div>

            {bundleArtifacts.length === 0 ? (
              <p className="text-sm text-neutral font-mono text-center py-6">
                No active SQL artifacts yet. Generate SQL for your sources first.
              </p>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-outline-variant">
                <table className="w-full border-collapse text-xs">
                  <thead className="bg-surface">
                    <tr className="text-left text-[10px] font-bold uppercase tracking-widest text-slate-500">
                      <th className="px-4 py-2">Destination Object</th>
                      <th className="px-4 py-2">Mapping Version</th>
                      <th className="px-4 py-2">Generated</th>
                      <th className="px-4 py-2">SQL Preview</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bundleArtifacts.map((a) => (
                      <tr key={a.codegenArtifactId} className="border-t border-outline-variant hover:bg-surface-container-lowest">
                        <td className="px-4 py-3 font-mono font-bold text-primary">
                          {a.destinationObjectName}
                        </td>
                        <td className="px-4 py-3 font-mono text-neutral">
                          {a.mappingSnapshotVersion ?? "—"}
                        </td>
                        <td className="px-4 py-3 text-neutral">
                          {a.createdAt.slice(0, 10)}
                        </td>
                        <td className="px-4 py-3 max-w-xs">
                          <code className="block truncate text-[10px] text-slate-600 bg-slate-100 rounded px-1.5 py-0.5">
                            {(a.sqlBundle ?? "").slice(0, 80)}…
                          </code>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
```

### Page tests — `web/app/projects/[id]/codegen/page.test.tsx`

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, beforeEach, describe, it, expect } from "vitest";
import CodegenPage from "./page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
  useParams: () => ({ id: "proj-1" }),
}));
vi.mock("../../../../lib/session", () => ({ loadUiSession: vi.fn() }));
vi.mock("../../../../lib/sources-api", () => ({ listSourceContracts: vi.fn() }));
vi.mock("../../../../lib/codegen-api", () => ({
  triggerCodegen: vi.fn(),
  listCodegenArtifacts: vi.fn(),
  getDeliveryBundle: vi.fn(),
}));

import { loadUiSession } from "../../../../lib/session";
import { listSourceContracts } from "../../../../lib/sources-api";
import {
  triggerCodegen,
  listCodegenArtifacts,
  getDeliveryBundle,
} from "../../../../lib/codegen-api";

const SESSION = {
  accessToken: "tok",
  expiresAt: "2099-01-01T00:00:00Z",
  userId: "u1",
  role: "central_team" as const,
  sessionVersion: 1,
};

const MAPPED_SOURCE = {
  sourceDefinitionId: "src-1",
  projectId: "proj-1",
  sourceType: "csv",
  label: "Customers",
  encoding: "utf-8",
  status: "approved",
  destinationObjectReferences: ["Customer"],
};

const ACTIVE_ARTIFACT = {
  codegenArtifactId: "art-1",
  projectId: "proj-1",
  destinationObjectName: "Customer",
  mappingSnapshotVersion: "v1",
  lookupSnapshotVersion: null,
  sqlBundle: "CREATE TABLE staging.stg_customer (customer_id INT);",
  status: "active",
  createdAt: "2026-06-30T00:00:00Z",
  supersededAt: null,
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getDeliveryBundle).mockResolvedValue({ projectId: "proj-1", artifacts: [] });
});

describe("CodegenPage", () => {
  it("shows 'no sources' message when no mapped sources exist", async () => {
    vi.mocked(loadUiSession).mockReturnValue(SESSION);
    vi.mocked(listSourceContracts).mockResolvedValue([]);
    vi.mocked(listCodegenArtifacts).mockResolvedValue([]);
    render(<CodegenPage />);
    await waitFor(() => {
      expect(screen.getByText(/no sources with approved mappings/i)).toBeInTheDocument();
    });
  });

  it("renders Generate SQL button for mapped source", async () => {
    vi.mocked(loadUiSession).mockReturnValue(SESSION);
    vi.mocked(listSourceContracts).mockResolvedValue([MAPPED_SOURCE]);
    vi.mocked(listCodegenArtifacts).mockResolvedValue([]);
    render(<CodegenPage />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /generate sql/i })).toBeInTheDocument();
    });
  });

  it("calls triggerCodegen on Generate SQL click", async () => {
    vi.mocked(loadUiSession).mockReturnValue(SESSION);
    vi.mocked(listSourceContracts).mockResolvedValue([MAPPED_SOURCE]);
    vi.mocked(listCodegenArtifacts).mockResolvedValue([]);
    vi.mocked(triggerCodegen).mockResolvedValue({
      codegenArtifactId: "art-new",
      projectId: "proj-1",
      destinationObjectName: "Customer",
      mappingSnapshotVersion: "v1",
      lookupSnapshotVersion: null,
      sqlBundlePreview: "CREATE TABLE",
      status: "active",
      createdAt: "2026-06-30T01:00:00Z",
    });
    vi.mocked(listCodegenArtifacts).mockResolvedValueOnce([]).mockResolvedValueOnce([ACTIVE_ARTIFACT]);
    vi.mocked(getDeliveryBundle).mockResolvedValue({ projectId: "proj-1", artifacts: [ACTIVE_ARTIFACT] });
    render(<CodegenPage />);
    await waitFor(() => { expect(screen.getByRole("button", { name: /generate sql/i })).toBeInTheDocument(); });
    fireEvent.click(screen.getByRole("button", { name: /generate sql/i }));
    await waitFor(() => {
      expect(triggerCodegen).toHaveBeenCalledWith("tok", "proj-1", "src-1");
    });
  });

  it("shows active artifact SQL bundle after generation", async () => {
    vi.mocked(loadUiSession).mockReturnValue(SESSION);
    vi.mocked(listSourceContracts).mockResolvedValue([MAPPED_SOURCE]);
    vi.mocked(listCodegenArtifacts).mockResolvedValue([ACTIVE_ARTIFACT]);
    vi.mocked(getDeliveryBundle).mockResolvedValue({ projectId: "proj-1", artifacts: [ACTIVE_ARTIFACT] });
    render(<CodegenPage />);
    await waitFor(() => {
      expect(screen.getByText(/CREATE TABLE staging.stg_customer/)).toBeInTheDocument();
    });
  });

  it("hides Generate button for read_only_auditor", async () => {
    vi.mocked(loadUiSession).mockReturnValue({ ...SESSION, role: "read_only_auditor" });
    vi.mocked(listSourceContracts).mockResolvedValue([MAPPED_SOURCE]);
    vi.mocked(listCodegenArtifacts).mockResolvedValue([ACTIVE_ARTIFACT]);
    render(<CodegenPage />);
    await waitFor(() => { expect(screen.getByText("Customer")).toBeInTheDocument(); });
    expect(screen.queryByRole("button", { name: /generate sql/i })).not.toBeInTheDocument();
  });

  it("shows delivery bundle tab with download button when artifacts exist", async () => {
    vi.mocked(loadUiSession).mockReturnValue(SESSION);
    vi.mocked(listSourceContracts).mockResolvedValue([MAPPED_SOURCE]);
    vi.mocked(listCodegenArtifacts).mockResolvedValue([ACTIVE_ARTIFACT]);
    vi.mocked(getDeliveryBundle).mockResolvedValue({ projectId: "proj-1", artifacts: [ACTIVE_ARTIFACT] });
    render(<CodegenPage />);
    await waitFor(() => { expect(screen.getByRole("button", { name: /delivery bundle/i })).toBeInTheDocument(); });
    fireEvent.click(screen.getByRole("button", { name: /delivery bundle/i }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /download bundle/i })).toBeInTheDocument();
    });
  });
});
```

## Implementation Order

1. Add `CodegenTriggerResponse`, `CodegenArtifactResponse`, `DeliveryBundleResponse` to `api/schemas.py`
2. Create `management/codegen.py`
3. Create `routes/codegen.py` and register in `app.py`
4. Run `pytest engine/tests/test_codegen_api.py -v`
5. Create `web/lib/codegen-api.ts`
6. Create `web/app/projects/[id]/codegen/page.tsx`
7. Create `web/app/projects/[id]/codegen/page.test.tsx`
8. Run `pnpm --filter web test` and `pnpm --filter web build`

## Verification

```bash
cd engine && pytest tests/test_codegen_api.py -v
pnpm --filter web test
pnpm --filter web lint
pnpm --filter web build
```

## Pitfalls

- AI task slot is `"script_generation"` — NOT `"codegen"`. Wrong slot raises `ConfigurationError`.
- `_resolve_destination_object_name` reads `SourceDefinition.destination_object_references[0]`.
  This is set by 001w's approve step. If the source has no approved mapping, `refs` is `[]` or
  `None` → raise 409 `mapping_not_approved`, not 404.
- `_supersede_previous` uses `.update()` directly on the query — this does NOT trigger SQLAlchemy
  ORM events. That's fine here (no after-update hooks needed). Call it BEFORE inserting the new
  artifact so both changes are in the same transaction.
- `listCodegenArtifacts` in the frontend is called twice on the artifacts tab (once on mount,
  once after generate). Both calls filter to `status="active"` on the frontend side. Do NOT
  pass `status` filter to the API on the first mount call — load all and filter on frontend so
  the superseded history can be loaded without a second trip when toggled.
- The "Delivery Bundle" download uses `URL.createObjectURL` — ensure `URL.revokeObjectURL` is
  called to avoid memory leaks.
- `SourceContractRecord` not `SourceRecord` — the correct type from `sources-api.ts`.
  Field is `sourceDefinitionId` (camelCase). Check exact field names before writing page code.
- `monkeypatch.setattr(codegen_module, "get_adapter", ...)` — patch at the management module
  level, not at `ai.factory`. Same pattern as 001w tests.

## Commit

```bash
feat(codegen): add AI-driven SQL bundle generation with supersession and delivery bundle
```
