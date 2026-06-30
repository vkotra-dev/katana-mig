Task: tasks/001w-mapping-stage.md
Domain: docs/domain/source-model.md, docs/domain/runs.md, docs/domain/governance.md
Depends on: 001v (SourceSchemaArtifact), 001s (AI adapter)
Reference template: mockmigration/src/components/ApprovalsView.tsx (Gate 1 evidence panel + decision matrix)

## Current State

- `MappingSnapshot` model exists in `db/models.py` with `status` (String(32), default="approved"),
  `field_bindings` (JSON), `destination_object_name`, `project_id`. No `source_definition_id` FK.
- `mapping/snapshots.py` has `create_approved_mapping_snapshot` (creates approved-only) and
  `select_latest_approved_mapping_snapshot` — used by runs. Do not modify these.
- `routes/mapping_snapshots.py` has `GET /mapping-snapshot` (approved only, for runs). Do not modify.
- `mapping-api.ts` has only `getLatestApprovedMappingSnapshot`. Needs all review functions.
- `ai/factory.py` exports `get_adapter(task: str) -> AIAdapter`. Task slot: `"field_mapping"`.
- `AIAdapter.call(system, user, response_model)` returns a validated Pydantic model.
- `management/source_analysis.py` exports `get_latest_source_schema_artifact(db, *, project_id, source_definition_id)`.
- `management/platform.py` exports `record_management_audit(db, *, project_id, actor_user_id, event_type, payload)`.
- `management/sources.py` exports `get_source_contract(db, *, project_id, source_definition_id)`.
- `management/access.py` exports `require_project_access(db, *, user, project_id)`.
- `sources-api.ts` exports `listSourceSchema(token, projectId, sourceDefinitionId) -> SourceSchemaColumnRecord[]`.
- `ProjectDefinition.domain_config["destination_schema_ddl"]` holds a CREATE TABLE DDL string.
- `ProjectRegistry.definition_id` → FK to `ProjectDefinition`.

## No migration needed

`MappingSnapshot.status` is already `String(32)`. Creating with `status="draft"` or `status="rejected"`
requires no schema change.

## Blast Radius

| File | Action | What changes |
|---|---|---|
| `engine/src/migrations_engine/api/schemas.py` | modify | Add `MappingPatchRequest`, `MappingReviewResponse` |
| `engine/src/migrations_engine/mapping/review.py` | create | Service layer: propose/get/patch/approve/reject |
| `engine/src/migrations_engine/routes/mapping.py` | create | 5 API routes |
| `engine/src/migrations_engine/app.py` | modify | Register new mapping router |
| `engine/tests/test_mapping_review_api.py` | create | API integration tests |
| `web/lib/mapping-api.ts` | modify | Add 5 new functions + types |
| `web/app/projects/[id]/sources/[sourceId]/mapping/page.tsx` | create | Mapping review page |
| `web/app/projects/[id]/sources/[sourceId]/mapping/page.test.tsx` | create | Page unit tests |

## Backend Specification

### Schema additions — `engine/src/migrations_engine/api/schemas.py`

Append after `MappingSnapshotResponse`:

```python
class MappingPatchRequest(BaseModel):
    field_bindings: list[MappingFieldBindingResponse]


class MappingReviewResponse(MappingSnapshotResponse):
    destination_fields: list[str]
```

### Service layer — `engine/src/migrations_engine/mapping/review.py`

```python
from __future__ import annotations

import re
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.adapter import AIAdapter
from ..api.deps import AuthApiError
from ..api.schemas import MappingFieldBindingResponse, MappingReviewResponse
from ..db.models import MappingSnapshot, ProjectDefinition, ProjectRegistry, SourceDefinition, new_id
from ..management.platform import record_management_audit
from ..management.source_analysis import get_latest_source_schema_artifact


class _ProposedBinding(BaseModel):
    source_field: str
    destination_field: str


class _FieldMappingProposal(BaseModel):
    bindings: list[_ProposedBinding]


def _parse_ddl(ddl: str) -> tuple[str, list[str]]:
    """Extract (table_name, [column_names]) from a CREATE TABLE statement."""
    name_match = re.search(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", ddl, re.IGNORECASE
    )
    if not name_match:
        raise ValueError("Could not parse table name from destination_schema_ddl.")
    table_name = name_match.group(1)
    columns = re.findall(r"^\s{1,8}(\w+)\s+\w", ddl, re.MULTILINE)
    return table_name, columns


def _get_project_destination_schema(db: Session, *, project_id: str) -> tuple[str, list[str]]:
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
    ddl: str | None = (definition.domain_config or {}).get("destination_schema_ddl") if definition else None
    if not ddl:
        raise AuthApiError(
            "destination_schema_missing",
            "Project has no destination schema DDL configured.",
            409,
        )
    try:
        table_name, columns = _parse_ddl(ddl)
    except ValueError as exc:
        raise AuthApiError("destination_schema_invalid", str(exc), 422) from exc
    if not columns:
        raise AuthApiError(
            "destination_schema_missing",
            "Destination schema DDL has no parseable column definitions.",
            409,
        )
    return table_name, columns


def _latest_snapshot(
    db: Session, *, project_id: str, destination_object_name: str
) -> MappingSnapshot | None:
    return db.scalar(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.destination_object_name == destination_object_name,
        )
        .order_by(MappingSnapshot.created_at.desc())
    )


def _snapshot_to_response(
    snapshot: MappingSnapshot, destination_fields: list[str]
) -> MappingReviewResponse:
    return MappingReviewResponse(
        mapping_snapshot_id=snapshot.mapping_snapshot_id,
        project_id=snapshot.project_id,
        destination_object_name=snapshot.destination_object_name,
        mapping_snapshot_version=snapshot.mapping_snapshot_version,
        field_bindings=[
            MappingFieldBindingResponse(
                source_field=str(b.get("source_field", "")),
                destination_field=str(b.get("destination_field", "")),
                lookup_name=b.get("lookup_name"),
            )
            for b in snapshot.field_bindings
        ],
        status=snapshot.status,
        approved_at=snapshot.approved_at,
        approved_by_user_id=snapshot.approved_by_user_id,
        created_at=snapshot.created_at,
        destination_fields=destination_fields,
    )


def propose_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    actor_user_id: str,
    adapter: AIAdapter,
) -> MappingReviewResponse:
    destination_object_name, destination_fields = _get_project_destination_schema(
        db, project_id=project_id
    )
    schema = get_latest_source_schema_artifact(
        db, project_id=project_id, source_definition_id=source_definition_id
    )
    source_columns = [col.name for col in schema.columns]
    proposal = adapter.call(
        system=(
            "You are a data migration specialist. Given source column names and destination "
            "field names, propose the best semantic field-to-field mapping. Return ONLY a JSON "
            "object with a 'bindings' array where each item has 'source_field' and "
            "'destination_field'. Every source column must appear in bindings."
        ),
        user=(
            f"Source columns: {source_columns!r}\n"
            f"Destination fields: {destination_fields!r}\n"
            "Map each source column to the most semantically appropriate destination field. "
            "Multiple source columns may map to the same destination field if needed."
        ),
        response_model=_FieldMappingProposal,
    )
    snapshot = MappingSnapshot(
        mapping_snapshot_id=new_id(),
        project_id=project_id,
        destination_object_name=destination_object_name,
        mapping_snapshot_version=new_id(),
        field_bindings=[
            {
                "source_field": b.source_field,
                "destination_field": b.destination_field,
                "lookup_name": None,
            }
            for b in proposal.bindings
        ],
        status="draft",
    )
    db.add(snapshot)
    db.flush()
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="mapping_proposed",
        payload={
            "mapping_snapshot_id": snapshot.mapping_snapshot_id,
            "destination_object_name": destination_object_name,
            "model_id": adapter.model_id,
        },
    )
    db.commit()
    db.refresh(snapshot)
    return _snapshot_to_response(snapshot, destination_fields)


def get_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
) -> MappingReviewResponse:
    destination_object_name, destination_fields = _get_project_destination_schema(
        db, project_id=project_id
    )
    snapshot = _latest_snapshot(
        db, project_id=project_id, destination_object_name=destination_object_name
    )
    if snapshot is None:
        raise AuthApiError("mapping_not_found", "No mapping snapshot exists yet.", 404)
    return _snapshot_to_response(snapshot, destination_fields)


def patch_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    field_bindings: list[MappingFieldBindingResponse],
) -> MappingReviewResponse:
    destination_object_name, destination_fields = _get_project_destination_schema(
        db, project_id=project_id
    )
    snapshot = _latest_snapshot(
        db, project_id=project_id, destination_object_name=destination_object_name
    )
    if snapshot is None:
        raise AuthApiError("mapping_not_found", "No mapping snapshot exists yet.", 404)
    if snapshot.status != "draft":
        raise AuthApiError(
            "mapping_not_editable",
            f"Cannot edit a mapping snapshot with status '{snapshot.status}'.",
            422,
        )
    snapshot.field_bindings = [
        {
            "source_field": b.source_field,
            "destination_field": b.destination_field,
            "lookup_name": b.lookup_name,
        }
        for b in field_bindings
    ]
    db.commit()
    db.refresh(snapshot)
    return _snapshot_to_response(snapshot, destination_fields)


def approve_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    actor_user_id: str,
) -> MappingReviewResponse:
    destination_object_name, destination_fields = _get_project_destination_schema(
        db, project_id=project_id
    )
    snapshot = _latest_snapshot(
        db, project_id=project_id, destination_object_name=destination_object_name
    )
    if snapshot is None:
        raise AuthApiError("mapping_not_found", "No mapping snapshot exists yet.", 404)
    if snapshot.status != "draft":
        raise AuthApiError(
            "mapping_not_approvable",
            f"Cannot approve a mapping snapshot with status '{snapshot.status}'.",
            422,
        )
    now = datetime.now(UTC)
    snapshot.status = "approved"
    snapshot.approved_at = now
    snapshot.approved_by_user_id = actor_user_id
    # Write destination_object_references back to SourceDefinition
    source = db.scalar(
        select(SourceDefinition).where(
            SourceDefinition.source_definition_id == source_definition_id,
            SourceDefinition.project_id == project_id,
        )
    )
    if source is not None:
        source.destination_object_references = [destination_object_name]
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="mapping_approved",
        payload={
            "mapping_snapshot_id": snapshot.mapping_snapshot_id,
            "mapping_snapshot_version": snapshot.mapping_snapshot_version,
            "destination_object_name": destination_object_name,
        },
    )
    db.commit()
    db.refresh(snapshot)
    return _snapshot_to_response(snapshot, destination_fields)


def reject_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    actor_user_id: str,
) -> MappingReviewResponse:
    destination_object_name, destination_fields = _get_project_destination_schema(
        db, project_id=project_id
    )
    snapshot = _latest_snapshot(
        db, project_id=project_id, destination_object_name=destination_object_name
    )
    if snapshot is None:
        raise AuthApiError("mapping_not_found", "No mapping snapshot exists yet.", 404)
    if snapshot.status != "draft":
        raise AuthApiError(
            "mapping_not_rejectable",
            f"Cannot reject a mapping snapshot with status '{snapshot.status}'.",
            422,
        )
    snapshot.status = "rejected"
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="mapping_rejected",
        payload={
            "mapping_snapshot_id": snapshot.mapping_snapshot_id,
            "destination_object_name": destination_object_name,
        },
    )
    db.commit()
    db.refresh(snapshot)
    return _snapshot_to_response(snapshot, destination_fields)
```

### Routes — `engine/src/migrations_engine/routes/mapping.py`

```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..ai.factory import get_adapter
from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import MappingPatchRequest, MappingReviewResponse
from ..db.models import User
from ..management.access import require_project_access
from ..mapping.review import (
    approve_mapping,
    get_mapping,
    patch_mapping,
    propose_mapping,
    reject_mapping,
)

router = APIRouter(
    prefix="/projects/{project_id}/sources/{source_definition_id}/mapping",
    tags=["mapping"],
)


@router.post("/propose", response_model=MappingReviewResponse)
def post_mapping_propose(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> MappingReviewResponse:
    require_project_access(db, user=actor, project_id=project_id)
    adapter = get_adapter("field_mapping")
    return propose_mapping(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        actor_user_id=actor.user_id,
        adapter=adapter,
    )


@router.get("", response_model=MappingReviewResponse)
def get_mapping_snapshot(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MappingReviewResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_mapping(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
    )


@router.patch("", response_model=MappingReviewResponse)
def patch_mapping_snapshot(
    project_id: str,
    source_definition_id: str,
    body: MappingPatchRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> MappingReviewResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return patch_mapping(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        field_bindings=body.field_bindings,
    )


@router.post("/approve", response_model=MappingReviewResponse)
def post_mapping_approve(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> MappingReviewResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return approve_mapping(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        actor_user_id=actor.user_id,
    )


@router.post("/reject", response_model=MappingReviewResponse)
def post_mapping_reject(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> MappingReviewResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return reject_mapping(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        actor_user_id=actor.user_id,
    )
```

### App registration — `engine/src/migrations_engine/app.py`

Add after the existing router imports:

```python
from .routes.mapping import router as mapping_router
```

Add after `app.include_router(mapping_snapshots_router)`:

```python
app.include_router(mapping_router)
```

### Backend tests — `engine/tests/test_mapping_review_api.py`

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import (
    MappingSnapshot,
    ProjectDefinition,
    ProjectRegistry,
    SourceDefinition,
    SourceSlice,
    SourceSchemaArtifact,
    User,
)
from migrations_engine.mapping import review as mapping_review_module
from migrations_engine.roles import CENTRAL_TEAM_ROLE

client = TestClient(app)

SAMPLE_DDL = (
    "CREATE TABLE Customer (\n"
    "  customer_id INT NOT NULL,\n"
    "  full_name VARCHAR(200),\n"
    "  email_address VARCHAR(255)\n"
    ");"
)


class FakeAdapter:
    def __init__(self, bindings: list[dict]) -> None:
        self.bindings = bindings
        self.model_id = "claude-sonnet-4-6"
        self.calls: list[SimpleNamespace] = []

    def call(self, system: str, user: str, response_model):
        self.calls.append(SimpleNamespace(system=system, user=user))
        return response_model(
            bindings=[
                mapping_review_module._ProposedBinding(**b) for b in self.bindings
            ]
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


def _seed_project(db, *, with_ddl: bool = True) -> tuple[str, str]:
    """Returns (project_id, source_definition_id)."""
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    domain_config = {"destination_schema_ddl": SAMPLE_DDL} if with_ddl else {}
    db.add(ProjectDefinition(
        definition_id=definition_id,
        project_id=project_id,
        name="Mapping Test Project",
        status="active",
        domain_config=domain_config,
    ))
    db.add(ProjectRegistry(
        project_id=project_id,
        name="Mapping Test Project",
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
    ))
    db.add(SourceSchemaArtifact(
        schema_artifact_id=str(uuid.uuid4()),
        source_definition_id=source_id,
        source_slice_version="v1",
        columns=[
            {"name": "cust_id", "inferred_type": "integer", "nullable": False, "max_length": None},
            {"name": "name", "inferred_type": "text", "nullable": True, "max_length": 200},
            {"name": "email", "inferred_type": "text", "nullable": True, "max_length": 255},
        ],
    ))
    db.commit()
    return project_id, source_id


def test_propose_creates_draft_snapshot(monkeypatch):
    token = _login()
    fake = FakeAdapter([
        {"source_field": "cust_id", "destination_field": "customer_id"},
        {"source_field": "name", "destination_field": "full_name"},
        {"source_field": "email", "destination_field": "email_address"},
    ])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)
    with SessionLocal() as db:
        project_id, source_id = _seed_project(db)
    resp = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "draft"
    assert data["destination_object_name"] == "Customer"
    assert len(data["field_bindings"]) == 3
    assert data["destination_fields"] == ["customer_id", "full_name", "email_address"]


def test_propose_409_when_no_ddl(monkeypatch):
    token = _login()
    fake = FakeAdapter([])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)
    with SessionLocal() as db:
        project_id, source_id = _seed_project(db, with_ddl=False)
    resp = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "destination_schema_missing"


def test_get_returns_latest_snapshot(monkeypatch):
    token = _login()
    fake = FakeAdapter([
        {"source_field": "cust_id", "destination_field": "customer_id"},
    ])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)
    with SessionLocal() as db:
        project_id, source_id = _seed_project(db)
    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.get(
        f"/projects/{project_id}/sources/{source_id}/mapping",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "draft"


def test_get_404_when_none():
    token = _login()
    with SessionLocal() as db:
        project_id, source_id = _seed_project(db)
    resp = client.get(
        f"/projects/{project_id}/sources/{source_id}/mapping",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_patch_updates_field_bindings(monkeypatch):
    token = _login()
    fake = FakeAdapter([
        {"source_field": "cust_id", "destination_field": "customer_id"},
    ])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)
    with SessionLocal() as db:
        project_id, source_id = _seed_project(db)
    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.patch(
        f"/projects/{project_id}/sources/{source_id}/mapping",
        headers={"Authorization": f"Bearer {token}"},
        json={"field_bindings": [
            {"source_field": "cust_id", "destination_field": "full_name", "lookup_name": None}
        ]},
    )
    assert resp.status_code == 200
    assert resp.json()["field_bindings"][0]["destination_field"] == "full_name"


def test_approve_writes_destination_object_references(monkeypatch):
    token = _login()
    fake = FakeAdapter([
        {"source_field": "cust_id", "destination_field": "customer_id"},
    ])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)
    with SessionLocal() as db:
        project_id, source_id = _seed_project(db)
    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    with SessionLocal() as db:
        source = db.scalar(
            select(SourceDefinition).where(SourceDefinition.source_definition_id == source_id)
        )
        assert source.destination_object_references == ["Customer"]


def test_reject_marks_snapshot_rejected(monkeypatch):
    token = _login()
    fake = FakeAdapter([
        {"source_field": "cust_id", "destination_field": "customer_id"},
    ])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)
    with SessionLocal() as db:
        project_id, source_id = _seed_project(db)
    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/reject",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_patch_422_on_approved_snapshot(monkeypatch):
    token = _login()
    fake = FakeAdapter([
        {"source_field": "cust_id", "destination_field": "customer_id"},
    ])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)
    with SessionLocal() as db:
        project_id, source_id = _seed_project(db)
    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {token}"},
    )
    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.patch(
        f"/projects/{project_id}/sources/{source_id}/mapping",
        headers={"Authorization": f"Bearer {token}"},
        json={"field_bindings": [
            {"source_field": "cust_id", "destination_field": "full_name", "lookup_name": None}
        ]},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "mapping_not_editable"
```

## Frontend Specification

### API client additions — `web/lib/mapping-api.ts`

Append the following **after** the existing content:

```typescript
export interface MappingReviewRecord extends MappingSnapshotRecord {
  destinationFields: string[];
}

function mapMappingReviewResponse(response: Parameters<typeof mapMappingSnapshotResponse>[0] & {
  destination_fields: string[];
}): MappingReviewRecord {
  return {
    ...mapMappingSnapshotResponse(response),
    destinationFields: response.destination_fields,
  };
}

export class MappingApiError extends Error {
  code: string;
  status: number;
  constructor(code: string, message: string, status: number) {
    super(message || code);
    this.name = "MappingApiError";
    this.code = code;
    this.status = status;
  }
}

async function mappingRequest<T>(
  path: string,
  init: RequestInit & { token: string },
): Promise<T> {
  const { token, ...rest } = init;
  const response = await fetch(`${import.meta.env?.VITE_API_BASE_URL ?? ""}/api${path}`, {
    ...rest,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(rest.headers ?? {}),
    },
  });
  if (!response.ok) {
    try {
      const body = (await response.json()) as { error?: { code?: string; message?: string } };
      throw new MappingApiError(
        body.error?.code ?? "api_error",
        body.error?.message ?? "api_error",
        response.status,
      );
    } catch (e) {
      if (e instanceof MappingApiError) throw e;
      throw new MappingApiError("api_error", await response.text(), response.status);
    }
  }
  return response.json() as Promise<T>;
}
```

**Wait** — the existing `mapping-api.ts` already uses `jsonRequest` from `"./api-base"`. Follow the same pattern instead of defining a new `mappingRequest`. Replace the four functions below using `jsonRequest` from the existing import:

```typescript
// Add to imports at top of file:
// import { jsonRequest } from "./api-base";  ← already imported

export interface MappingReviewRecord extends MappingSnapshotRecord {
  destinationFields: string[];
}

type MappingReviewRaw = Parameters<typeof mapMappingSnapshotResponse>[0] & {
  destination_fields: string[];
};

function mapMappingReviewResponse(response: MappingReviewRaw): MappingReviewRecord {
  return {
    ...mapMappingSnapshotResponse(response),
    destinationFields: response.destination_fields,
  };
}

export async function proposeMappingSnapshot(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<MappingReviewRecord> {
  const response = await jsonRequest<MappingReviewRaw>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/mapping/propose`,
    { method: "POST", token },
  );
  return mapMappingReviewResponse(response);
}

export async function getMappingSnapshot(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<MappingReviewRecord> {
  const response = await jsonRequest<MappingReviewRaw>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/mapping`,
    { method: "GET", token },
  );
  return mapMappingReviewResponse(response);
}

export async function patchMappingSnapshot(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  fieldBindings: Array<{ sourceField: string; destinationField: string; lookupName: string | null }>,
): Promise<MappingReviewRecord> {
  const response = await jsonRequest<MappingReviewRaw>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/mapping`,
    {
      method: "PATCH",
      token,
      body: JSON.stringify({
        field_bindings: fieldBindings.map((b) => ({
          source_field: b.sourceField,
          destination_field: b.destinationField,
          lookup_name: b.lookupName,
        })),
      }),
    },
  );
  return mapMappingReviewResponse(response);
}

export async function approveMappingSnapshot(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<MappingReviewRecord> {
  const response = await jsonRequest<MappingReviewRaw>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/mapping/approve`,
    { method: "POST", token },
  );
  return mapMappingReviewResponse(response);
}

export async function rejectMappingSnapshot(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<MappingReviewRecord> {
  const response = await jsonRequest<MappingReviewRaw>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/mapping/reject`,
    { method: "POST", token },
  );
  return mapMappingReviewResponse(response);
}
```

**Important**: Check the existing `jsonRequest` signature in `mapping-api.ts`. If it takes `{ method, token, body? }`, use it exactly. Do not change the import.

### Mapping review page — `web/app/projects/[id]/sources/[sourceId]/mapping/page.tsx`

Visual layout is modelled on `mockmigration/src/components/ApprovalsView.tsx`:
- Left 2/3: "Auditable Evidence Panel" (field binding table, editable in draft)
- Right 1/3: "Governed Audit Panel" (Approve / Push Back, submitting state, role lock)

```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Topbar } from "../../../../../../components/Topbar";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../../../lib/session";
import {
  getMappingSnapshot,
  proposeMappingSnapshot,
  patchMappingSnapshot,
  approveMappingSnapshot,
  rejectMappingSnapshot,
  type MappingReviewRecord,
  type MappingFieldBindingRecord,
} from "../../../../../../lib/mapping-api";
import { listSourceSchema, type SourceSchemaColumnRecord } from "../../../../../../lib/sources-api";

type PageState = "loading" | "no_snapshot" | "draft" | "approved" | "rejected";

function statusChipClass(status: string): string {
  if (status === "approved") return "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20";
  if (status === "rejected") return "bg-red-500/10 text-red-600 border border-red-500/20";
  return "bg-amber-500/10 text-amber-600 border border-amber-500/20 animate-pulse";
}

export default function MappingReviewPage() {
  const router = useRouter();
  const params = useParams<{ id: string; sourceId: string }>();
  const projectId = params.id;
  const sourceDefinitionId = params.sourceId;

  const [session, setSession] = useState<UiSession | null>(null);
  const [pageState, setPageState] = useState<PageState>("loading");
  const [snapshot, setSnapshot] = useState<MappingReviewRecord | null>(null);
  const [sourceColumns, setSourceColumns] = useState<SourceSchemaColumnRecord[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Draft editing state
  const [editedBindings, setEditedBindings] = useState<MappingFieldBindingRecord[]>([]);
  const [isDirty, setIsDirty] = useState(false);

  // Decision panel state
  const [decision, setDecision] = useState<"approved" | "rejected" | null>(null);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);
  const [proposing, setProposing] = useState(false);

  useEffect(() => {
    setSession(loadUiSession());
  }, []);

  useEffect(() => {
    if (!session) return;
    let active = true;

    void Promise.all([
      getMappingSnapshot(session.accessToken, projectId, sourceDefinitionId).catch((e: { status?: number }) =>
        e?.status === 404 ? null : Promise.reject(e),
      ),
      listSourceSchema(session.accessToken, projectId, sourceDefinitionId).catch(() => [] as SourceSchemaColumnRecord[]),
    ]).then(([snap, cols]) => {
      if (!active) return;
      setSourceColumns(cols);
      if (snap === null) {
        setPageState("no_snapshot");
      } else {
        setSnapshot(snap);
        setEditedBindings(snap.fieldBindings.map((b) => ({ ...b })));
        setPageState(snap.status as PageState);
      }
    }).catch((e: unknown) => {
      if (active) {
        setErrorMessage(e instanceof Error ? e.message : "Failed to load mapping.");
        setPageState("draft"); // fallback so error shows
      }
    });

    return () => { active = false; };
  }, [session, projectId, sourceDefinitionId]);

  async function handlePropose() {
    if (!session) return;
    setProposing(true);
    setErrorMessage(null);
    try {
      const snap = await proposeMappingSnapshot(session.accessToken, projectId, sourceDefinitionId);
      setSnapshot(snap);
      setEditedBindings(snap.fieldBindings.map((b) => ({ ...b })));
      setPageState("draft");
    } catch (e: unknown) {
      setErrorMessage(e instanceof Error ? e.message : "Failed to propose mapping.");
    } finally {
      setProposing(false);
    }
  }

  async function handleSaveBindings() {
    if (!session || !snapshot) return;
    setSubmitting(true);
    try {
      const updated = await patchMappingSnapshot(
        session.accessToken,
        projectId,
        sourceDefinitionId,
        editedBindings.map((b) => ({
          sourceField: b.sourceField,
          destinationField: b.destinationField,
          lookupName: b.lookupName,
        })),
      );
      setSnapshot(updated);
      setEditedBindings(updated.fieldBindings.map((b) => ({ ...b })));
      setIsDirty(false);
    } catch (e: unknown) {
      setSubmitError(e instanceof Error ? e.message : "Failed to save bindings.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSubmitDecision(e: React.FormEvent) {
    e.preventDefault();
    if (!session || !decision) {
      setSubmitError("Please select Approve or Push Back.");
      return;
    }
    if (decision === "rejected" && !comment.trim()) {
      setSubmitError("A rejection comment is required for audit trails.");
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const snap = decision === "approved"
        ? await approveMappingSnapshot(session.accessToken, projectId, sourceDefinitionId)
        : await rejectMappingSnapshot(session.accessToken, projectId, sourceDefinitionId);
      setSnapshot(snap);
      setPageState(snap.status as PageState);
      setSubmitSuccess(
        decision === "approved"
          ? "Mapping approved. Destination object references updated."
          : "Mapping rejected. You may propose a new mapping.",
      );
      setDecision(null);
      setComment("");
    } catch (e: unknown) {
      setSubmitError(e instanceof Error ? e.message : "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  }

  const role: SessionRole = session?.role ?? "read_only_auditor";
  const canAct = role === "central_team";

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-6">

        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-neutral">
          <button
            className="hover:text-primary hover:underline"
            onClick={() => { router.back(); }}
            type="button"
          >
            ← Back
          </button>
          <span className="text-slate-300">|</span>
          <span className="font-mono uppercase tracking-wider">Field Mapping Review</span>
          {snapshot && (
            <>
              <span className="text-slate-300">—</span>
              <span
                className={`status-chip inline-flex items-center px-2 py-0.5 text-[10px] font-bold uppercase rounded-full ${statusChipClass(snapshot.status)}`}
              >
                {snapshot.status}
              </span>
            </>
          )}
        </div>

        {errorMessage && (
          <div role="alert" className="rounded border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
            {errorMessage}
          </div>
        )}

        {/* No snapshot state */}
        {pageState === "no_snapshot" && (
          <div className="flex flex-col items-center gap-4 rounded-2xl border border-dashed border-outline-variant bg-surface-container p-12 text-center shadow-sm">
            <p className="text-sm text-neutral font-mono uppercase tracking-wider">
              No field mapping proposed yet.
            </p>
            {canAct && (
              <button
                className="rounded-md bg-primary px-5 py-2 text-sm font-semibold text-white hover:opacity-95 disabled:opacity-60"
                disabled={proposing}
                onClick={() => { void handlePropose(); }}
                type="button"
              >
                {proposing ? "Proposing mapping…" : "Propose Mapping via AI"}
              </button>
            )}
            {!canAct && (
              <p className="text-xs text-neutral font-mono">
                A central_team member must propose the mapping.
              </p>
            )}
          </div>
        )}

        {/* Loading */}
        {pageState === "loading" && (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            Loading mapping…
          </div>
        )}

        {/* Draft / Approved / Rejected — 2/3 + 1/3 grid */}
        {(pageState === "draft" || pageState === "approved" || pageState === "rejected") && snapshot && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">

            {/* Left 2/3: Evidence panel */}
            <div className="lg:col-span-2 space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
              <div className="border-b border-outline-variant pb-3 flex items-center justify-between">
                <div>
                  <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-primary">
                    Auditable Evidence Panel
                  </p>
                  <h2 className="mt-1 text-base font-bold text-slate-900 uppercase">
                    {snapshot.destinationObjectName} — Field Bindings
                  </h2>
                </div>
                <span className="font-mono text-xs text-neutral">{snapshot.mappingSnapshotVersion.slice(0, 8)}</span>
              </div>

              {pageState === "draft" && isDirty && canAct && (
                <div className="flex justify-end">
                  <button
                    className="rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-white hover:opacity-95 disabled:opacity-60"
                    disabled={submitting}
                    onClick={() => { void handleSaveBindings(); }}
                    type="button"
                  >
                    {submitting ? "Saving…" : "Save changes"}
                  </button>
                </div>
              )}

              <div className="overflow-x-auto rounded-xl border border-outline-variant">
                <table className="w-full border-collapse text-xs">
                  <thead className="bg-surface">
                    <tr className="text-left text-[10px] font-bold uppercase tracking-widest text-slate-500">
                      <th className="px-4 py-2">Source Field</th>
                      <th className="px-4 py-2">Destination Field</th>
                      <th className="px-4 py-2">Lookup</th>
                    </tr>
                  </thead>
                  <tbody>
                    {editedBindings.map((binding, idx) => (
                      <tr
                        key={binding.sourceField}
                        className="border-t border-outline-variant hover:bg-surface-container-lowest"
                      >
                        <td className="px-4 py-2.5 font-mono font-semibold text-slate-800">
                          {binding.sourceField}
                        </td>
                        <td className="px-4 py-2.5">
                          {pageState === "draft" && canAct ? (
                            <select
                              aria-label={`Destination field for ${binding.sourceField}`}
                              className="rounded border border-outline-variant bg-surface px-2 py-1 text-xs font-mono text-primary focus:outline-none focus:ring-1 focus:ring-primary"
                              onChange={(e) => {
                                const next = editedBindings.map((b, i) =>
                                  i === idx ? { ...b, destinationField: e.target.value } : b,
                                );
                                setEditedBindings(next);
                                setIsDirty(true);
                              }}
                              value={binding.destinationField}
                            >
                              {snapshot.destinationFields.map((f) => (
                                <option key={f} value={f}>{f}</option>
                              ))}
                            </select>
                          ) : (
                            <span className="font-mono font-semibold text-primary">
                              {binding.destinationField}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2.5">
                          {pageState === "draft" && canAct ? (
                            <input
                              aria-label={`Lookup name for ${binding.sourceField}`}
                              className="w-32 rounded border border-outline-variant bg-surface px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                              onChange={(e) => {
                                const next = editedBindings.map((b, i) =>
                                  i === idx
                                    ? { ...b, lookupName: e.target.value || null }
                                    : b,
                                );
                                setEditedBindings(next);
                                setIsDirty(true);
                              }}
                              placeholder="none"
                              type="text"
                              value={binding.lookupName ?? ""}
                            />
                          ) : binding.lookupName ? (
                            <span className="rounded bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.5 text-[10px] font-bold font-mono text-amber-700 uppercase">
                              {binding.lookupName}
                            </span>
                          ) : (
                            <span className="text-neutral">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <p className="text-[10px] text-neutral font-mono">
                Version {snapshot.mappingSnapshotVersion} · Created {snapshot.createdAt.slice(0, 10)}
                {snapshot.approvedAt ? ` · Approved ${snapshot.approvedAt.slice(0, 10)}` : ""}
              </p>
            </div>

            {/* Right 1/3: Decision panel */}
            <div className="rounded-2xl border border-outline-variant bg-surface-container p-5 shadow-sm space-y-4">
              <div className="border-b border-outline-variant pb-2.5">
                <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-neutral">
                  Governed Audit Panel
                </p>
                <h3 className="mt-0.5 text-sm font-bold uppercase text-slate-900">Decision Matrix</h3>
              </div>

              {pageState === "draft" && canAct && (
                <form className="space-y-4 text-xs" onSubmit={(e) => { void handleSubmitDecision(e); }}>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      className={`rounded py-2 font-semibold border transition ${
                        decision === "approved"
                          ? "bg-emerald-600 text-white border-emerald-600"
                          : "border-outline-variant text-slate-700 hover:bg-surface-container-lowest"
                      }`}
                      onClick={() => { setDecision("approved"); setSubmitError(null); }}
                      type="button"
                    >
                      Approve Gate
                    </button>
                    <button
                      className={`rounded py-2 font-semibold border transition ${
                        decision === "rejected"
                          ? "bg-red-500 text-white border-red-500"
                          : "border-outline-variant text-slate-700 hover:bg-surface-container-lowest"
                      }`}
                      onClick={() => { setDecision("rejected"); setSubmitError(null); }}
                      type="button"
                    >
                      Push Back
                    </button>
                  </div>
                  <div>
                    <label className="block text-[9px] font-bold uppercase tracking-wider text-neutral font-mono mb-1">
                      Review comment (required for rejections)
                    </label>
                    <textarea
                      className="w-full rounded border border-outline-variant bg-surface px-2.5 py-1.5 text-xs font-mono placeholder:text-neutral focus:outline-none focus:ring-1 focus:ring-primary"
                      onChange={(e) => { setComment(e.target.value); }}
                      placeholder={decision === "rejected" ? "Describe what needs to change…" : "Optional — e.g., verified all bindings."}
                      rows={4}
                      value={comment}
                    />
                  </div>
                  {submitError && (
                    <p className="rounded bg-error/10 border border-error/20 p-2 text-[10px] font-mono text-error leading-tight">
                      {submitError}
                    </p>
                  )}
                  {submitSuccess && (
                    <p className="rounded bg-emerald-500/10 border border-emerald-500/20 p-2 text-[10px] font-mono text-emerald-600 leading-tight">
                      {submitSuccess}
                    </p>
                  )}
                  <button
                    className="w-full rounded bg-slate-900 py-2 text-xs font-bold text-white hover:bg-slate-800 disabled:opacity-60 transition"
                    disabled={submitting || !decision}
                    type="submit"
                  >
                    {submitting ? "Filing audit record…" : "Submit Audit Decision"}
                  </button>
                </form>
              )}

              {pageState === "draft" && !canAct && (
                <div className="rounded border border-outline-variant bg-surface p-3 text-center text-[10px] font-mono text-neutral">
                  Auditor accounts do not possess approval privileges.
                </div>
              )}

              {(pageState === "approved" || pageState === "rejected") && (
                <div className="space-y-3">
                  <div className="rounded border border-outline-variant bg-surface p-4 text-center space-y-2 text-xs text-neutral">
                    <p className="font-bold uppercase text-[10px] font-mono text-emerald-600">
                      Decision Settled
                    </p>
                    <p className="text-[10px]">
                      This mapping has been submitted as <strong className="uppercase">{pageState}</strong>.
                      Immutable logs are stored.
                    </p>
                  </div>
                  {pageState === "rejected" && canAct && (
                    <button
                      className="w-full rounded border border-primary px-4 py-2 text-xs font-semibold text-primary hover:bg-primary-container transition disabled:opacity-60"
                      disabled={proposing}
                      onClick={() => { void handlePropose(); }}
                      type="button"
                    >
                      {proposing ? "Proposing…" : "Propose New Mapping"}
                    </button>
                  )}
                </div>
              )}

              {submitSuccess && (pageState === "approved" || pageState === "rejected") && (
                <p className="rounded bg-emerald-500/10 border border-emerald-500/20 p-2 text-[10px] font-mono text-emerald-600 leading-tight">
                  {submitSuccess}
                </p>
              )}
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
```

### Page tests — `web/app/projects/[id]/sources/[sourceId]/mapping/page.test.tsx`

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, beforeEach, describe, it, expect } from "vitest";
import MappingReviewPage from "./page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
  useParams: () => ({ id: "proj-1", sourceId: "src-1" }),
}));
vi.mock("../../../../../../lib/session", () => ({ loadUiSession: vi.fn() }));
vi.mock("../../../../../../lib/mapping-api", () => ({
  getMappingSnapshot: vi.fn(),
  proposeMappingSnapshot: vi.fn(),
  patchMappingSnapshot: vi.fn(),
  approveMappingSnapshot: vi.fn(),
  rejectMappingSnapshot: vi.fn(),
}));
vi.mock("../../../../../../lib/sources-api", () => ({ listSourceSchema: vi.fn() }));

import { loadUiSession } from "../../../../../../lib/session";
import {
  getMappingSnapshot,
  proposeMappingSnapshot,
  approveMappingSnapshot,
  rejectMappingSnapshot,
} from "../../../../../../lib/mapping-api";
import { listSourceSchema } from "../../../../../../lib/sources-api";

const SESSION = {
  accessToken: "tok",
  expiresAt: "2099-01-01T00:00:00Z",
  userId: "u1",
  role: "central_team" as const,
  sessionVersion: 1,
};

const DRAFT_SNAPSHOT = {
  mappingSnapshotId: "snap-1",
  projectId: "proj-1",
  destinationObjectName: "Customer",
  mappingSnapshotVersion: "v1",
  fieldBindings: [
    { sourceField: "cust_id", destinationField: "customer_id", lookupName: null },
    { sourceField: "name", destinationField: "full_name", lookupName: null },
  ],
  status: "draft",
  approvedAt: null,
  approvedByUserId: null,
  createdAt: "2026-06-30T00:00:00Z",
  destinationFields: ["customer_id", "full_name", "email_address"],
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listSourceSchema).mockResolvedValue([]);
});

describe("MappingReviewPage", () => {
  it("shows 'no snapshot' state and Propose button when no mapping exists", async () => {
    vi.mocked(loadUiSession).mockReturnValue(SESSION);
    vi.mocked(getMappingSnapshot).mockRejectedValue({ status: 404 });
    render(<MappingReviewPage />);
    await waitFor(() => {
      expect(screen.getByText(/no field mapping proposed yet/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /propose mapping/i })).toBeInTheDocument();
  });

  it("renders field binding table in draft state", async () => {
    vi.mocked(loadUiSession).mockReturnValue(SESSION);
    vi.mocked(getMappingSnapshot).mockResolvedValue(DRAFT_SNAPSHOT);
    render(<MappingReviewPage />);
    await waitFor(() => {
      expect(screen.getByText("cust_id")).toBeInTheDocument();
    });
    expect(screen.getByText("name")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve gate/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /push back/i })).toBeInTheDocument();
  });

  it("disables approve submit without selecting a decision", async () => {
    vi.mocked(loadUiSession).mockReturnValue(SESSION);
    vi.mocked(getMappingSnapshot).mockResolvedValue(DRAFT_SNAPSHOT);
    render(<MappingReviewPage />);
    await waitFor(() => { expect(screen.getByText(/submit audit decision/i)).toBeInTheDocument(); });
    expect(screen.getByRole("button", { name: /submit audit decision/i })).toBeDisabled();
  });

  it("requires rejection comment before submit", async () => {
    vi.mocked(loadUiSession).mockReturnValue(SESSION);
    vi.mocked(getMappingSnapshot).mockResolvedValue(DRAFT_SNAPSHOT);
    render(<MappingReviewPage />);
    await waitFor(() => { expect(screen.getByRole("button", { name: /push back/i })).toBeInTheDocument(); });
    fireEvent.click(screen.getByRole("button", { name: /push back/i }));
    fireEvent.click(screen.getByRole("button", { name: /submit audit decision/i }));
    await waitFor(() => {
      expect(screen.getByText(/rejection comment is required/i)).toBeInTheDocument();
    });
  });

  it("calls approveMappingSnapshot on approve submit", async () => {
    vi.mocked(loadUiSession).mockReturnValue(SESSION);
    vi.mocked(getMappingSnapshot).mockResolvedValue(DRAFT_SNAPSHOT);
    vi.mocked(approveMappingSnapshot).mockResolvedValue({ ...DRAFT_SNAPSHOT, status: "approved", approvedAt: "2026-06-30T01:00:00Z" });
    render(<MappingReviewPage />);
    await waitFor(() => { expect(screen.getByRole("button", { name: /approve gate/i })).toBeInTheDocument(); });
    fireEvent.click(screen.getByRole("button", { name: /approve gate/i }));
    fireEvent.click(screen.getByRole("button", { name: /submit audit decision/i }));
    await waitFor(() => {
      expect(approveMappingSnapshot).toHaveBeenCalledWith("tok", "proj-1", "src-1");
    });
  });

  it("shows 'Decision Settled' after approval", async () => {
    vi.mocked(loadUiSession).mockReturnValue(SESSION);
    vi.mocked(getMappingSnapshot).mockResolvedValue({ ...DRAFT_SNAPSHOT, status: "approved" });
    render(<MappingReviewPage />);
    await waitFor(() => {
      expect(screen.getByText(/decision settled/i)).toBeInTheDocument();
    });
  });

  it("hides decision controls for read_only_auditor", async () => {
    vi.mocked(loadUiSession).mockReturnValue({ ...SESSION, role: "read_only_auditor" });
    vi.mocked(getMappingSnapshot).mockResolvedValue(DRAFT_SNAPSHOT);
    render(<MappingReviewPage />);
    await waitFor(() => { expect(screen.getByText("cust_id")).toBeInTheDocument(); });
    expect(screen.queryByRole("button", { name: /approve gate/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /push back/i })).not.toBeInTheDocument();
  });
});
```

## Implementation Order

1. Add `MappingPatchRequest` and `MappingReviewResponse` to `api/schemas.py`
2. Create `mapping/review.py` and run backend tests
3. Create `routes/mapping.py` and register in `app.py`
4. Run `pytest engine/tests/test_mapping_review_api.py`
5. Extend `web/lib/mapping-api.ts` with the 5 new functions
6. Create `web/app/projects/[id]/sources/[sourceId]/mapping/page.tsx`
7. Create `web/app/projects/[id]/sources/[sourceId]/mapping/page.test.tsx`
8. Run `pnpm --filter web test`

## Verification

```bash
cd engine && pytest tests/test_mapping_review_api.py -v
pnpm --filter web test
pnpm --filter web lint
pnpm --filter web build
```

## Pitfalls

- Do NOT modify `mapping/snapshots.py` or `routes/mapping_snapshots.py` — those serve runs.
- `MappingSnapshot.destination_object_name` is the join key between propose and get. It comes
  from parsing `destination_schema_ddl` — parse the same DDL on every request so GET/PATCH/approve
  find the draft created by propose.
- `get_adapter("field_mapping")` is the correct task slot for the AI call (from `ai/factory.py`).
  Do NOT pass a config_path — `get_adapter` reads the config internally via `get_ai_config()`.
- In tests, monkeypatch `mapping_review_module.get_adapter`, not `ai.factory.get_adapter`,
  because `review.py` uses its own import reference.
- The `_parse_ddl` regex `r"^\s{1,8}(\w+)\s+\w"` matches lines indented 1–8 spaces where
  a word is followed by a space and another word (the column type). This handles standard DDL
  indentation but will NOT match zero-indented columns or CONSTRAINT lines (which is correct).
- The frontend `useParams` path is `[id]` for project and `[sourceId]` for source — verify
  the actual Next.js route segment names in `web/app/projects/` before wiring.

## Commit

```bash
feat(mapping): add AI-proposed field binding review with approve/reject flow
```
