Task: tasks/001z-review-gates.md
Domain: docs/domain/ui.md (authoritative), docs/domain/governance.md, docs/domain/runs.md
Stitch reference: docs/design/stitch/08-gate1-review.md, 09-gate2-review.md
Depends on: 001y (CodeGenerationArtifact), 001t (RunRecord), 001w (MappingSnapshot), 001x (LookupValueMap)

## Source-of-truth corrections

The 001z task file's UI descriptions are wrong. `docs/domain/ui.md` is authoritative:

- **Gate 1** (audience: `central_team`): domain object map + PII classification + coverage gaps.
  NOT "SQL bundle viewer + mapping summary".
- **Gate 2** (audience: `project_stakeholder`): LookupValueMap — Lookup Inventory vs current
  source_value_map. NOT "staging table row count + sample rows".

Both gates use the 2-pane layout from stitch 08: evidence on left, decision panel on right.

## Current State

- `RunRecord.approvals: Mapped[list[dict[str, Any]] | None]` exists — use this for gate records.
  No new `GateApproval` model or migration needed.
- `RunRecord` fields: `status` (String(32)), `current_stage` (String(64)), `pause_metadata` (JSON),
  `source_definition_reference` (String(36)) — holds source_definition_id.
- Valid `status` values in use: `queued | running | paused | awaiting_approval | completed | failed`.
- `is_pii_field(name: str) -> bool` in `intake/masking.py` — detects PII by column name.
- `SourceSchemaArtifact.columns: list[dict]` — each dict has `name`, `inferred_type`, `nullable`.
- `MappingSnapshot.field_bindings: list[dict]` — each has `source_field`, `destination_field`, `lookup_name`.
- `LookupValueMap`: `destination_table: list[dict]` (known destination values),
  `source_value_map: dict[str,str]` (source value → destination value mappings).
  Linked to a source via `LookupValueMap.source_definition_id` and `lookup_name`.
- `list_lookup_value_maps(db, *, source_definition_id, actor) -> list[LookupValueMapResponse]`
  in `management/lookup_mapping.py`.
- `select_latest_approved_mapping_snapshot(db, *, project_id, destination_object_name)` — raises
  `SnapshotNotFoundError` if not found.
- `get_latest_source_schema_artifact(db, *, project_id, source_definition_id)` in
  `management/source_analysis.py`.
- `record_management_audit(db, *, project_id, actor_user_id, event_type, payload)` in
  `management/platform.py`.
- `require_project_access(db, *, user, project_id)` in `management/access.py`.
- `get_central_team_user`, `get_current_user`, `get_db` in `api/deps.py`.
- No `gates.py` in routes or management — both are new.

## Blast Radius

| File | Action | What changes |
|---|---|---|
| `engine/src/migrations_engine/api/schemas.py` | modify | Add gate schemas |
| `engine/src/migrations_engine/management/gates.py` | create | Service layer |
| `engine/src/migrations_engine/routes/gates.py` | create | 7 routes |
| `engine/src/migrations_engine/app.py` | modify | Register gates router |
| `engine/tests/test_gates_api.py` | create | Integration tests |
| `web/lib/gates-api.ts` | create | API client + types |
| `web/app/runs/[id]/gate-1/page.tsx` | create | Gate 1 review page |
| `web/app/runs/[id]/gate-2/page.tsx` | create | Gate 2 review page |
| `web/app/runs/[id]/gate-1/page.test.tsx` | create | Gate 1 page tests |
| `web/app/runs/[id]/gate-2/page.test.tsx` | create | Gate 2 page tests |

## RunRecord.approvals JSON schema

Each gate record appended to the list:

```python
# Approval
{
    "gate": "gate_1",            # or "gate_2"
    "decision": "approved",
    "approver_user_id": "...",
    "decided_at": "2026-06-30T12:00:00+00:00",
    "notes": "All PII fields verified."
}

# Rejection (pushback)
{
    "gate": "gate_1",
    "decision": "rejected",
    "approver_user_id": "...",
    "decided_at": "2026-06-30T12:00:00+00:00",
    "affected_objects": ["Customer"],
    "required_changes": "email field must be excluded before proceeding",
    "notes": "Lawful basis documentation missing."
}
```

## Stage transitions

| Action | `status` before | `status` after | `current_stage` after | `pause_metadata` |
|---|---|---|---|---|
| Gate 1 approve | any | `awaiting_approval` | `gate_2_pending` | unchanged |
| Gate 1 reject | any | `paused` | unchanged | `{gate: "gate_1", reason: required_changes}` |
| Gate 2 approve | `awaiting_approval` | `awaiting_approval` | `gate_2_approved` | unchanged |
| Gate 2 reject | `awaiting_approval` | `paused` | unchanged | `{gate: "gate_2", reason: required_changes}` |

Gate 2 cannot be approved unless Gate 1 already has an `approved` record in `RunRecord.approvals`.

## Backend Specification

### Schema additions — `engine/src/migrations_engine/api/schemas.py`

```python
class GateApproveRequest(BaseModel):
    notes: str | None = None


class GatePushbackRequest(BaseModel):
    affected_objects: list[str]
    required_changes: str
    notes: str | None = None


class GateRecordResponse(BaseModel):
    gate: str
    decision: str
    approver_user_id: str | None
    decided_at: datetime
    notes: str | None
    affected_objects: list[str] | None = None
    required_changes: str | None = None


class GateStatusResponse(BaseModel):
    run_id: str
    gate_1: GateRecordResponse | None
    gate_2: GateRecordResponse | None


class FieldBindingSummary(BaseModel):
    source_field: str
    destination_field: str
    lookup_name: str | None


class Gate1EvidenceResponse(BaseModel):
    run_id: str
    destination_object_name: str
    mapping_snapshot_version: str | None
    field_bindings: list[FieldBindingSummary]   # domain object map
    pii_fields: list[str]                        # source fields flagged as PII
    coverage_gaps: list[str]                     # source columns not in any binding


class LookupRowResponse(BaseModel):
    source_value: str
    destination_value: str | None
    state: str   # "confirmed" | "unmapped"


class Gate2EvidenceResponse(BaseModel):
    run_id: str
    lookup_name: str
    rows: list[LookupRowResponse]
    confirmed_count: int
    unmapped_count: int
```

### Service layer — `engine/src/migrations_engine/management/gates.py`

```python
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import (
    Gate1EvidenceResponse,
    Gate2EvidenceResponse,
    GateApproveRequest,
    GatePushbackRequest,
    GateRecordResponse,
    GateStatusResponse,
    FieldBindingSummary,
    LookupRowResponse,
)
from ..db.models import LookupValueMap, RunRecord, SourceDefinition
from ..intake.masking import is_pii_field
from ..management.platform import record_management_audit
from ..management.source_analysis import get_latest_source_schema_artifact
from ..mapping.exceptions import SnapshotNotFoundError
from ..mapping.snapshots import select_latest_approved_mapping_snapshot


def _get_run_or_404(db: Session, *, project_id: str, run_id: str) -> RunRecord:
    run = db.scalar(
        select(RunRecord).where(
            RunRecord.run_id == run_id,
            RunRecord.project_id == project_id,
        )
    )
    if run is None:
        raise AuthApiError("run_not_found", "Run not found.", 404)
    return run


def _get_gate_record(run: RunRecord, gate: str) -> dict | None:
    for record in (run.approvals or []):
        if record.get("gate") == gate:
            return record
    return None


def _to_gate_record_response(record: dict | None) -> GateRecordResponse | None:
    if record is None:
        return None
    return GateRecordResponse(
        gate=record["gate"],
        decision=record["decision"],
        approver_user_id=record.get("approver_user_id"),
        decided_at=datetime.fromisoformat(record["decided_at"]),
        notes=record.get("notes"),
        affected_objects=record.get("affected_objects"),
        required_changes=record.get("required_changes"),
    )


def get_gate_status(
    db: Session,
    *,
    project_id: str,
    run_id: str,
) -> GateStatusResponse:
    run = _get_run_or_404(db, project_id=project_id, run_id=run_id)
    return GateStatusResponse(
        run_id=run_id,
        gate_1=_to_gate_record_response(_get_gate_record(run, "gate_1")),
        gate_2=_to_gate_record_response(_get_gate_record(run, "gate_2")),
    )


def get_gate1_evidence(
    db: Session,
    *,
    project_id: str,
    run_id: str,
) -> Gate1EvidenceResponse:
    run = _get_run_or_404(db, project_id=project_id, run_id=run_id)
    source_definition_id = run.source_definition_reference
    destination_object_name = run.destination_object_name

    field_bindings: list[FieldBindingSummary] = []
    pii_fields: list[str] = []
    coverage_gaps: list[str] = []

    try:
        mapping_snapshot = select_latest_approved_mapping_snapshot(
            db,
            project_id=project_id,
            destination_object_name=destination_object_name,
        )
        field_bindings = [
            FieldBindingSummary(
                source_field=b["source_field"],
                destination_field=b["destination_field"],
                lookup_name=b.get("lookup_name"),
            )
            for b in mapping_snapshot.field_bindings
        ]
        mapped_source_fields = {b["source_field"] for b in mapping_snapshot.field_bindings}
        mapping_snapshot_version = mapping_snapshot.mapping_snapshot_version
    except SnapshotNotFoundError:
        mapped_source_fields = set()
        mapping_snapshot_version = None

    if source_definition_id:
        try:
            schema = get_latest_source_schema_artifact(
                db,
                project_id=project_id,
                source_definition_id=source_definition_id,
            )
            for col in schema.columns:
                if is_pii_field(col.name):
                    pii_fields.append(col.name)
                if col.name not in mapped_source_fields:
                    coverage_gaps.append(col.name)
        except AuthApiError:
            pass  # no schema artifact yet — gaps/PII left empty

    return Gate1EvidenceResponse(
        run_id=run_id,
        destination_object_name=destination_object_name,
        mapping_snapshot_version=mapping_snapshot_version,
        field_bindings=field_bindings,
        pii_fields=pii_fields,
        coverage_gaps=coverage_gaps,
    )


def get_gate2_evidence(
    db: Session,
    *,
    project_id: str,
    run_id: str,
) -> Gate2EvidenceResponse:
    run = _get_run_or_404(db, project_id=project_id, run_id=run_id)
    source_definition_id = run.source_definition_reference
    if not source_definition_id:
        raise AuthApiError(
            "source_not_linked",
            "Run has no linked source definition; cannot load Gate 2 evidence.",
            409,
        )

    # Find lookup binding from the run's mapping snapshot
    lookup_name: str | None = None
    try:
        mapping = select_latest_approved_mapping_snapshot(
            db,
            project_id=project_id,
            destination_object_name=run.destination_object_name,
        )
        for b in mapping.field_bindings:
            if b.get("lookup_name"):
                lookup_name = b["lookup_name"]
                break
    except SnapshotNotFoundError:
        pass

    if not lookup_name:
        # No lookup binding — Gate 2 has no lookup rows to review
        return Gate2EvidenceResponse(
            run_id=run_id,
            lookup_name="",
            rows=[],
            confirmed_count=0,
            unmapped_count=0,
        )

    lookup_value_map = db.scalar(
        select(LookupValueMap).where(
            LookupValueMap.source_definition_id == source_definition_id,
            LookupValueMap.lookup_name == lookup_name,
        )
    )
    if lookup_value_map is None:
        return Gate2EvidenceResponse(
            run_id=run_id,
            lookup_name=lookup_name,
            rows=[],
            confirmed_count=0,
            unmapped_count=0,
        )

    destination_values = {
        row.get("value", row.get("id", "")) for row in lookup_value_map.destination_table
    }
    source_value_map: dict[str, str] = lookup_value_map.source_value_map or {}

    rows = []
    for source_val, dest_val in source_value_map.items():
        state = "confirmed" if dest_val in destination_values else "unmapped"
        rows.append(LookupRowResponse(
            source_value=source_val,
            destination_value=dest_val or None,
            state=state,
        ))

    confirmed = sum(1 for r in rows if r.state == "confirmed")
    unmapped = sum(1 for r in rows if r.state == "unmapped")

    return Gate2EvidenceResponse(
        run_id=run_id,
        lookup_name=lookup_name,
        rows=rows,
        confirmed_count=confirmed,
        unmapped_count=unmapped,
    )


def approve_gate(
    db: Session,
    *,
    project_id: str,
    run_id: str,
    gate: str,
    actor_user_id: str,
    body: GateApproveRequest,
) -> GateStatusResponse:
    run = _get_run_or_404(db, project_id=project_id, run_id=run_id)

    if gate == "gate_2":
        gate1_record = _get_gate_record(run, "gate_1")
        if gate1_record is None or gate1_record.get("decision") != "approved":
            raise AuthApiError(
                "gate_1_not_approved",
                "Gate 1 must be approved before Gate 2 can be approved.",
                422,
            )

    existing = _get_gate_record(run, gate)
    if existing and existing.get("decision") == "approved":
        raise AuthApiError(
            "gate_already_approved",
            f"{gate} is already approved.",
            422,
        )

    record = {
        "gate": gate,
        "decision": "approved",
        "approver_user_id": actor_user_id,
        "decided_at": datetime.now(UTC).isoformat(),
        "notes": body.notes,
    }
    approvals = [a for a in (run.approvals or []) if a.get("gate") != gate]
    approvals.append(record)
    run.approvals = approvals

    if gate == "gate_1":
        run.current_stage = "gate_2_pending"
        run.status = "awaiting_approval"
    elif gate == "gate_2":
        run.current_stage = "gate_2_approved"

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type=f"{gate}_approved",
        payload={"run_id": run_id, "notes": body.notes},
    )
    db.commit()
    db.refresh(run)
    return get_gate_status(db, project_id=project_id, run_id=run_id)


def reject_gate(
    db: Session,
    *,
    project_id: str,
    run_id: str,
    gate: str,
    actor_user_id: str,
    body: GatePushbackRequest,
) -> GateStatusResponse:
    run = _get_run_or_404(db, project_id=project_id, run_id=run_id)

    record = {
        "gate": gate,
        "decision": "rejected",
        "approver_user_id": actor_user_id,
        "decided_at": datetime.now(UTC).isoformat(),
        "affected_objects": body.affected_objects,
        "required_changes": body.required_changes,
        "notes": body.notes,
    }
    approvals = [a for a in (run.approvals or []) if a.get("gate") != gate]
    approvals.append(record)
    run.approvals = approvals
    run.status = "paused"
    run.pause_metadata = {
        "gate": gate,
        "reason": body.required_changes,
        "paused_at": datetime.now(UTC).isoformat(),
    }

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type=f"{gate}_rejected",
        payload={
            "run_id": run_id,
            "affected_objects": body.affected_objects,
            "required_changes": body.required_changes,
        },
    )
    db.commit()
    db.refresh(run)
    return get_gate_status(db, project_id=project_id, run_id=run_id)
```

### Routes — `engine/src/migrations_engine/routes/gates.py`

```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import (
    Gate1EvidenceResponse,
    Gate2EvidenceResponse,
    GateApproveRequest,
    GatePushbackRequest,
    GateStatusResponse,
)
from ..db.models import User
from ..management.access import require_project_access
from ..management.gates import (
    approve_gate,
    get_gate1_evidence,
    get_gate2_evidence,
    get_gate_status,
    reject_gate,
)

router = APIRouter(
    prefix="/projects/{project_id}/runs/{run_id}/gates",
    tags=["gates"],
)


@router.get("", response_model=GateStatusResponse)
def get_gates(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GateStatusResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_gate_status(db, project_id=project_id, run_id=run_id)


@router.get("/gate-1/evidence", response_model=Gate1EvidenceResponse)
def get_gate1_evidence_route(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Gate1EvidenceResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_gate1_evidence(db, project_id=project_id, run_id=run_id)


@router.get("/gate-2/evidence", response_model=Gate2EvidenceResponse)
def get_gate2_evidence_route(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Gate2EvidenceResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_gate2_evidence(db, project_id=project_id, run_id=run_id)


@router.post("/gate-1/approve", response_model=GateStatusResponse)
def approve_gate_1(
    project_id: str,
    run_id: str,
    body: GateApproveRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> GateStatusResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return approve_gate(
        db, project_id=project_id, run_id=run_id,
        gate="gate_1", actor_user_id=actor.user_id, body=body,
    )


@router.post("/gate-1/reject", response_model=GateStatusResponse)
def reject_gate_1(
    project_id: str,
    run_id: str,
    body: GatePushbackRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> GateStatusResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return reject_gate(
        db, project_id=project_id, run_id=run_id,
        gate="gate_1", actor_user_id=actor.user_id, body=body,
    )


@router.post("/gate-2/approve", response_model=GateStatusResponse)
def approve_gate_2(
    project_id: str,
    run_id: str,
    body: GateApproveRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> GateStatusResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return approve_gate(
        db, project_id=project_id, run_id=run_id,
        gate="gate_2", actor_user_id=actor.user_id, body=body,
    )


@router.post("/gate-2/reject", response_model=GateStatusResponse)
def reject_gate_2(
    project_id: str,
    run_id: str,
    body: GatePushbackRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> GateStatusResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return reject_gate(
        db, project_id=project_id, run_id=run_id,
        gate="gate_2", actor_user_id=actor.user_id, body=body,
    )
```

### App registration — `engine/src/migrations_engine/app.py`

After existing router imports:
```python
from .routes.gates import router as gates_router
```

After `app.include_router(codegen_router)`:
```python
app.include_router(gates_router)
```

### Backend tests — `engine/tests/test_gates_api.py`

```python
from __future__ import annotations

import uuid

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
    RunRecord,
    SourceDefinition,
    SourceSchemaArtifact,
    User,
)
from migrations_engine.roles import CENTRAL_TEAM_ROLE

client = TestClient(app)


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


def _seed(db) -> tuple[str, str]:
    """Returns (project_id, run_id)."""
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    db.add(ProjectDefinition(
        definition_id=definition_id,
        project_id=project_id,
        name="Gate Test Project",
        status="active",
        domain_config={},
    ))
    db.add(ProjectRegistry(
        project_id=project_id,
        name="Gate Test Project",
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
        destination_object_references=["Customer"],
    ))
    db.add(SourceSchemaArtifact(
        schema_artifact_id=str(uuid.uuid4()),
        source_definition_id=source_id,
        source_slice_version="v1",
        columns=[
            {"name": "cust_id", "inferred_type": "integer", "nullable": False, "max_length": None},
            {"name": "email", "inferred_type": "text", "nullable": True, "max_length": 255},
            {"name": "notes", "inferred_type": "text", "nullable": True, "max_length": None},
        ],
    ))
    db.add(MappingSnapshot(
        mapping_snapshot_id=str(uuid.uuid4()),
        project_id=project_id,
        destination_object_name="Customer",
        mapping_snapshot_version="v1",
        field_bindings=[
            {"source_field": "cust_id", "destination_field": "customer_id", "lookup_name": None},
            {"source_field": "email", "destination_field": "email_address", "lookup_name": None},
        ],
        status="approved",
    ))
    db.add(RunRecord(
        run_id=run_id,
        project_id=project_id,
        destination_object_name="Customer",
        source_definition_reference=source_id,
        status="queued",
        approvals=[],
    ))
    db.commit()
    return project_id, run_id


def test_get_gate_status_returns_empty_gates():
    token = _login()
    with SessionLocal() as db:
        project_id, run_id = _seed(db)
    resp = client.get(
        f"/projects/{project_id}/runs/{run_id}/gates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["gate_1"] is None
    assert data["gate_2"] is None


def test_gate1_evidence_derives_pii_and_coverage_gaps():
    token = _login()
    with SessionLocal() as db:
        project_id, run_id = _seed(db)
    resp = client.get(
        f"/projects/{project_id}/runs/{run_id}/gates/gate-1/evidence",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # email is PII
    assert "email" in data["pii_fields"]
    # notes is not in any binding — it's a coverage gap
    assert "notes" in data["coverage_gaps"]
    # cust_id and email are mapped
    assert len(data["field_bindings"]) == 2


def test_approve_gate1_transitions_stage():
    token = _login()
    with SessionLocal() as db:
        project_id, run_id = _seed(db)
    resp = client.post(
        f"/projects/{project_id}/runs/{run_id}/gates/gate-1/approve",
        headers={"Authorization": f"Bearer {token}"},
        json={"notes": "Reviewed and approved."},
    )
    assert resp.status_code == 200
    assert resp.json()["gate_1"]["decision"] == "approved"
    with SessionLocal() as db:
        run = db.get(RunRecord, run_id)
    assert run.current_stage == "gate_2_pending"
    assert run.status == "awaiting_approval"


def test_gate2_blocked_without_gate1():
    token = _login()
    with SessionLocal() as db:
        project_id, run_id = _seed(db)
    resp = client.post(
        f"/projects/{project_id}/runs/{run_id}/gates/gate-2/approve",
        headers={"Authorization": f"Bearer {token}"},
        json={"notes": ""},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "gate_1_not_approved"


def test_reject_gate1_pauses_run():
    token = _login()
    with SessionLocal() as db:
        project_id, run_id = _seed(db)
    resp = client.post(
        f"/projects/{project_id}/runs/{run_id}/gates/gate-1/reject",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "affected_objects": ["Customer"],
            "required_changes": "PII field email must be excluded.",
            "notes": None,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["gate_1"]["decision"] == "rejected"
    with SessionLocal() as db:
        run = db.get(RunRecord, run_id)
    assert run.status == "paused"
    assert run.pause_metadata["gate"] == "gate_1"


def test_approve_gate2_after_gate1():
    token = _login()
    with SessionLocal() as db:
        project_id, run_id = _seed(db)
    client.post(
        f"/projects/{project_id}/runs/{run_id}/gates/gate-1/approve",
        headers={"Authorization": f"Bearer {token}"},
        json={"notes": None},
    )
    resp = client.post(
        f"/projects/{project_id}/runs/{run_id}/gates/gate-2/approve",
        headers={"Authorization": f"Bearer {token}"},
        json={"notes": "Lookup values all confirmed."},
    )
    assert resp.status_code == 200
    assert resp.json()["gate_2"]["decision"] == "approved"
    with SessionLocal() as db:
        run = db.get(RunRecord, run_id)
    assert run.current_stage == "gate_2_approved"
```

## Frontend Specification

### API client — `web/lib/gates-api.ts`

```typescript
import { jsonRequest } from "./api-base";

export interface GateRecordRecord {
  gate: string;
  decision: "approved" | "rejected";
  approverUserId: string | null;
  decidedAt: string;
  notes: string | null;
  affectedObjects?: string[] | null;
  requiredChanges?: string | null;
}

export interface GateStatusRecord {
  runId: string;
  gate1: GateRecordRecord | null;
  gate2: GateRecordRecord | null;
}

export interface FieldBindingSummaryRecord {
  sourceField: string;
  destinationField: string;
  lookupName: string | null;
}

export interface Gate1EvidenceRecord {
  runId: string;
  destinationObjectName: string;
  mappingSnapshotVersion: string | null;
  fieldBindings: FieldBindingSummaryRecord[];
  piiFields: string[];
  coverageGaps: string[];
}

export interface LookupRowRecord {
  sourceValue: string;
  destinationValue: string | null;
  state: "confirmed" | "unmapped";
}

export interface Gate2EvidenceRecord {
  runId: string;
  lookupName: string;
  rows: LookupRowRecord[];
  confirmedCount: number;
  unmappedCount: number;
}

function mapGateRecord(r: {
  gate: string; decision: string; approver_user_id: string | null;
  decided_at: string; notes: string | null;
  affected_objects?: string[] | null; required_changes?: string | null;
}): GateRecordRecord {
  return {
    gate: r.gate, decision: r.decision as "approved" | "rejected",
    approverUserId: r.approver_user_id, decidedAt: r.decided_at, notes: r.notes,
    affectedObjects: r.affected_objects, requiredChanges: r.required_changes,
  };
}

export async function getGateStatus(
  token: string, projectId: string, runId: string,
): Promise<GateStatusRecord> {
  const r = await jsonRequest<{
    run_id: string;
    gate_1: Parameters<typeof mapGateRecord>[0] | null;
    gate_2: Parameters<typeof mapGateRecord>[0] | null;
  }>(`/projects/${projectId}/runs/${runId}/gates`, { method: "GET", token });
  return {
    runId: r.run_id,
    gate1: r.gate_1 ? mapGateRecord(r.gate_1) : null,
    gate2: r.gate_2 ? mapGateRecord(r.gate_2) : null,
  };
}

export async function getGate1Evidence(
  token: string, projectId: string, runId: string,
): Promise<Gate1EvidenceRecord> {
  const r = await jsonRequest<{
    run_id: string; destination_object_name: string;
    mapping_snapshot_version: string | null;
    field_bindings: { source_field: string; destination_field: string; lookup_name: string | null }[];
    pii_fields: string[]; coverage_gaps: string[];
  }>(`/projects/${projectId}/runs/${runId}/gates/gate-1/evidence`, { method: "GET", token });
  return {
    runId: r.run_id, destinationObjectName: r.destination_object_name,
    mappingSnapshotVersion: r.mapping_snapshot_version,
    fieldBindings: r.field_bindings.map((b) => ({
      sourceField: b.source_field, destinationField: b.destination_field, lookupName: b.lookup_name,
    })),
    piiFields: r.pii_fields, coverageGaps: r.coverage_gaps,
  };
}

export async function getGate2Evidence(
  token: string, projectId: string, runId: string,
): Promise<Gate2EvidenceRecord> {
  const r = await jsonRequest<{
    run_id: string; lookup_name: string;
    rows: { source_value: string; destination_value: string | null; state: string }[];
    confirmed_count: number; unmapped_count: number;
  }>(`/projects/${projectId}/runs/${runId}/gates/gate-2/evidence`, { method: "GET", token });
  return {
    runId: r.run_id, lookupName: r.lookup_name,
    rows: r.rows.map((row) => ({
      sourceValue: row.source_value, destinationValue: row.destination_value,
      state: row.state as "confirmed" | "unmapped",
    })),
    confirmedCount: r.confirmed_count, unmappedCount: r.unmapped_count,
  };
}

export async function approveGate(
  token: string, projectId: string, runId: string,
  gate: "gate-1" | "gate-2", notes: string | null,
): Promise<GateStatusRecord> {
  return getGateStatus(
    token, projectId, runId,
  ).then(() => jsonRequest<Parameters<typeof getGateStatus>[0]>(
    `/projects/${projectId}/runs/${runId}/gates/${gate}/approve`,
    { method: "POST", token, body: JSON.stringify({ notes }) },
  ).then(() => getGateStatus(token, projectId, runId)));
}

export async function rejectGate(
  token: string, projectId: string, runId: string,
  gate: "gate-1" | "gate-2",
  body: { affectedObjects: string[]; requiredChanges: string; notes: string | null },
): Promise<GateStatusRecord> {
  await jsonRequest(
    `/projects/${projectId}/runs/${runId}/gates/${gate}/reject`,
    {
      method: "POST", token,
      body: JSON.stringify({
        affected_objects: body.affectedObjects,
        required_changes: body.requiredChanges,
        notes: body.notes,
      }),
    },
  );
  return getGateStatus(token, projectId, runId);
}
```

### Gate 1 page — `web/app/runs/[id]/gate-1/page.tsx`

Layout: 2-pane (stitch 08). Left 2/3 = evidence (domain object map, PII, coverage gaps). Right 1/3 = decision panel (Approve / Push Back with structured fields).

```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Topbar } from "../../../../components/Topbar";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../lib/session";
import {
  approveGate, getGate1Evidence, getGateStatus, rejectGate,
  type Gate1EvidenceRecord, type GateStatusRecord,
} from "../../../../lib/gates-api";

export default function Gate1ReviewPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const runId = params.id;

  const [session, setSession] = useState<UiSession | null>(null);
  const [evidence, setEvidence] = useState<Gate1EvidenceRecord | null>(null);
  const [gateStatus, setGateStatus] = useState<GateStatusRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Decision state
  const [decision, setDecision] = useState<"approved" | "rejected" | null>(null);
  const [notes, setNotes] = useState("");
  const [affectedObjects, setAffectedObjects] = useState("");
  const [requiredChanges, setRequiredChanges] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  // Derived project ID is not available from runId alone — the run detail page
  // must pass projectId via query param or the URL must include it.
  // Route assumption: /projects/[projectId]/runs/[id]/gate-1/page.tsx
  // Adjust this page if the actual route shape differs.
  const projectId = useParams<{ projectId?: string }>()?.projectId ?? "";

  useEffect(() => { setSession(loadUiSession()); }, []);

  useEffect(() => {
    if (!session || !projectId) return;
    let active = true;
    void Promise.all([
      getGate1Evidence(session.accessToken, projectId, runId),
      getGateStatus(session.accessToken, projectId, runId),
    ]).then(([ev, gs]) => {
      if (!active) return;
      setEvidence(ev);
      setGateStatus(gs);
      setLoading(false);
    }).catch((e: unknown) => {
      if (active) {
        setErrorMessage(e instanceof Error ? e.message : "Failed to load gate evidence.");
        setLoading(false);
      }
    });
    return () => { active = false; };
  }, [session, projectId, runId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!session || !decision) return;
    if (decision === "rejected") {
      if (!affectedObjects.trim()) { setSubmitError("Affected objects is required."); return; }
      if (!requiredChanges.trim()) { setSubmitError("Required changes is required."); return; }
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      let updated: GateStatusRecord;
      if (decision === "approved") {
        updated = await approveGate(session.accessToken, projectId, runId, "gate-1", notes || null);
      } else {
        updated = await rejectGate(session.accessToken, projectId, runId, "gate-1", {
          affectedObjects: affectedObjects.split(",").map((s) => s.trim()).filter(Boolean),
          requiredChanges: requiredChanges.trim(),
          notes: notes || null,
        });
      }
      setGateStatus(updated);
      setSubmitSuccess(decision === "approved" ? "Gate 1 approved. Run advanced to Gate 2." : "Gate 1 pushed back. Run paused.");
      setDecision(null);
    } catch (e: unknown) {
      setSubmitError(e instanceof Error ? e.message : "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  }

  const role: SessionRole = session?.role ?? "read_only_auditor";
  const canAct = role === "central_team";
  const settled = gateStatus?.gate1 !== null;

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-6">
        <div className="flex items-center gap-2 text-xs text-neutral">
          <button className="hover:text-primary hover:underline" onClick={() => { router.back(); }} type="button">← Back</button>
          <span className="text-slate-300">|</span>
          <span className="font-mono uppercase tracking-wider">Gate 1 Review</span>
          {gateStatus?.gate1 && (
            <span className={`status-chip rounded-full px-2 py-0.5 text-[10px] font-bold uppercase font-mono ${
              gateStatus.gate1.decision === "approved"
                ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
                : "bg-red-500/10 text-red-600 border border-red-500/20"
            }`}>{gateStatus.gate1.decision}</span>
          )}
        </div>

        {errorMessage && (
          <div role="alert" className="rounded border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{errorMessage}</div>
        )}

        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">Loading evidence…</div>
        ) : evidence && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Left 2/3: Evidence */}
            <div className="lg:col-span-2 space-y-4">
              {/* Domain Object Map */}
              <div className="rounded-2xl border border-outline-variant bg-surface-container p-5 shadow-sm">
                <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-primary mb-2">Domain Object Map</p>
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
                      {evidence.fieldBindings.map((b) => (
                        <tr key={b.sourceField} className="border-t border-outline-variant">
                          <td className="px-4 py-2.5 font-mono font-semibold text-slate-800">{b.sourceField}</td>
                          <td className="px-4 py-2.5 font-mono text-primary">{b.destinationField}</td>
                          <td className="px-4 py-2.5 text-neutral">{b.lookupName ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* PII Classification */}
              <div className="rounded-2xl border border-outline-variant bg-surface-container p-5 shadow-sm">
                <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-primary mb-2">PII Classification</p>
                {evidence.piiFields.length === 0 ? (
                  <p className="text-xs text-neutral font-mono">No PII fields detected.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {evidence.piiFields.map((f) => (
                      <span key={f} className="rounded-full bg-red-500/10 border border-red-500/20 px-2.5 py-0.5 text-[10px] font-bold font-mono text-red-600 uppercase">{f}</span>
                    ))}
                  </div>
                )}
              </div>

              {/* Coverage Gaps */}
              <div className="rounded-2xl border border-outline-variant bg-surface-container p-5 shadow-sm">
                <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-amber-600 mb-2">Coverage Gaps</p>
                {evidence.coverageGaps.length === 0 ? (
                  <p className="text-xs text-neutral font-mono">All source fields are mapped.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {evidence.coverageGaps.map((f) => (
                      <span key={f} className="rounded-full bg-amber-500/10 border border-amber-500/20 px-2.5 py-0.5 text-[10px] font-bold font-mono text-amber-700 uppercase">{f}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Right 1/3: Decision Panel */}
            <div className="rounded-2xl border border-outline-variant bg-surface-container p-5 shadow-sm space-y-4">
              <div className="border-b border-outline-variant pb-2.5">
                <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-neutral">Governed Audit Panel</p>
                <h3 className="mt-0.5 text-sm font-bold uppercase text-slate-900">Gate 1 Decision</h3>
              </div>
              <p className="text-[10px] text-neutral font-mono leading-relaxed">
                Submitting records an approval — it does not call execution directly.
              </p>

              {settled && gateStatus?.gate1 ? (
                <div className="space-y-2">
                  <div className={`rounded border p-3 text-center text-[10px] font-mono ${
                    gateStatus.gate1.decision === "approved"
                      ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-600"
                      : "border-red-500/20 bg-red-500/10 text-red-600"
                  }`}>
                    <p className="font-bold uppercase">Decision Settled — {gateStatus.gate1.decision}</p>
                    <p className="mt-1">{gateStatus.gate1.decidedAt.slice(0, 10)}</p>
                  </div>
                </div>
              ) : canAct ? (
                <form className="space-y-3 text-xs" onSubmit={(e) => { void handleSubmit(e); }}>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      className={`rounded py-2 font-semibold border transition ${decision === "approved" ? "bg-emerald-600 text-white border-emerald-600" : "border-outline-variant text-slate-700 hover:bg-surface-container-lowest"}`}
                      onClick={() => { setDecision("approved"); setSubmitError(null); }}
                      type="button"
                    >Approve</button>
                    <button
                      className={`rounded py-2 font-semibold border transition ${decision === "rejected" ? "bg-red-500 text-white border-red-500" : "border-outline-variant text-slate-700 hover:bg-surface-container-lowest"}`}
                      onClick={() => { setDecision("rejected"); setSubmitError(null); }}
                      type="button"
                    >Push Back</button>
                  </div>

                  {decision === "rejected" && (
                    <div className="space-y-2">
                      <div>
                        <label className="block text-[9px] font-bold uppercase tracking-wider text-neutral font-mono mb-1">Affected Objects (required, comma-separated)</label>
                        <input
                          className="w-full rounded border border-outline-variant bg-surface px-2.5 py-1.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                          onChange={(e) => { setAffectedObjects(e.target.value); }}
                          placeholder="Customer, Account"
                          type="text"
                          value={affectedObjects}
                        />
                      </div>
                      <div>
                        <label className="block text-[9px] font-bold uppercase tracking-wider text-neutral font-mono mb-1">Required Changes (required)</label>
                        <textarea
                          className="w-full rounded border border-outline-variant bg-surface px-2.5 py-1.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                          onChange={(e) => { setRequiredChanges(e.target.value); }}
                          placeholder="Describe what must change before resubmission…"
                          rows={3}
                          value={requiredChanges}
                        />
                      </div>
                    </div>
                  )}

                  <div>
                    <label className="block text-[9px] font-bold uppercase tracking-wider text-neutral font-mono mb-1">Notes (optional)</label>
                    <textarea
                      className="w-full rounded border border-outline-variant bg-surface px-2.5 py-1.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                      onChange={(e) => { setNotes(e.target.value); }}
                      placeholder="Optional context for the audit record."
                      rows={2}
                      value={notes}
                    />
                  </div>

                  {submitError && <p className="rounded bg-error/10 border border-error/20 p-2 text-[10px] font-mono text-error">{submitError}</p>}
                  {submitSuccess && <p className="rounded bg-emerald-500/10 border border-emerald-500/20 p-2 text-[10px] font-mono text-emerald-600">{submitSuccess}</p>}

                  <button
                    className="w-full rounded bg-slate-900 py-2 text-xs font-bold text-white hover:bg-slate-800 disabled:opacity-60 transition"
                    disabled={submitting || !decision}
                    type="submit"
                  >{submitting ? "Filing audit record…" : "Submit Gate 1 Decision"}</button>
                </form>
              ) : (
                <p className="text-[10px] font-mono text-neutral text-center">
                  Gate 1 decisions require <strong>central_team</strong> role.
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

**Route note**: The page uses `useParams` for both `[id]` (runId) and `projectId`. Verify the actual Next.js route segment before wiring — if the URL is `/projects/[projectId]/runs/[id]/gate-1`, both params are available. If the URL is `/runs/[id]/gate-1`, projectId must come from the gate status API or a different source. Adjust the file path and `useParams` call accordingly.

### Gate 2 page — `web/app/runs/[id]/gate-2/page.tsx`

Follow the same 2-pane shell as Gate 1. Left 2/3 = lookup inventory table (source value → destination value, state chip per row). Right 1/3 = decision panel with same Approve / Push Back structure.

Key differences from Gate 1:
- Load `getGate2Evidence` instead of `getGate1Evidence`
- Evidence left panel: table of `rows` with `sourceValue`, `destinationValue`, `state` chip
  - confirmed: `bg-emerald-500/10 text-emerald-600`
  - unmapped: `bg-red-500/10 text-red-600`
- Show `unmappedCount` count in amber warning if > 0: "N unmapped values must be resolved before approval"
- Approve button disabled when `unmappedCount > 0` — show helper text
- Role guard: audience is `project_stakeholder` per ui.md — but `central_team` can also act; hide controls for `read_only_auditor`
- Gate check: Gate 2 approve fails at backend if Gate 1 not approved — show 422 error

Structure mirrors Gate 1 page exactly; reuse the same decision form, submit handler, and settled state rendering.

### Gate 1 and Gate 2 page tests

Follow same vi.mock pattern as existing page tests. Tests must cover:

**Gate 1 (`page.test.tsx`)**:
- renders PII chips when `piiFields` is non-empty
- renders coverage gap chips when `coverageGaps` is non-empty
- hides decision form for `read_only_auditor`
- shows "Affected Objects" and "Required Changes" fields only when Push Back selected
- disables submit when no decision selected
- calls `approveGate` on approve submit
- calls `rejectGate` on pushback submit with structured fields
- shows settled state when `gateStatus.gate1` is non-null

**Gate 2 (`page.test.tsx`)**:
- renders lookup rows with correct state chips
- disables approve when `unmappedCount > 0`
- calls `approveGate("gate-2", ...)` on approve
- shows settled state when `gateStatus.gate2` is non-null

## Implementation Order

1. Schema additions to `api/schemas.py`
2. Create `management/gates.py`
3. Create `routes/gates.py` + register in `app.py`
4. Run `pytest engine/tests/test_gates_api.py -v`
5. Create `web/lib/gates-api.ts`
6. Create Gate 1 page + tests; run `pnpm --filter web test`
7. Create Gate 2 page + tests; run `pnpm --filter web test`
8. Run `pnpm --filter web build`

## Verification

```bash
cd engine && pytest tests/test_gates_api.py -v
pnpm --filter web test
pnpm --filter web lint
pnpm --filter web build
```

## Pitfalls

- Gate 1 audience is `central_team`; Gate 2 audience is `project_stakeholder` per ui.md. Backend
  uses `get_central_team_user` for both currently (as a simplification) — if Gate 2 should be
  restricted to `project_stakeholder`, change the Gate 2 approve/reject deps to
  `get_project_stakeholder_user` if that dep exists, or add role checking in the service.
- `RunRecord.approvals` is a JSON column — SQLAlchemy won't detect in-place list mutation.
  Always reassign: `run.approvals = new_list` not `run.approvals.append(...)`.
- `LookupValueMap.destination_table` is a `list[dict]` where each dict shape may vary.
  The `get_gate2_evidence` function reads `row.get("value", row.get("id", ""))` defensively.
  Check the actual shape in `management/lookup_mapping.py` before implementing.
- The page-level `projectId` param depends on the actual route file location. If gate pages
  live at `web/app/runs/[id]/gate-1/`, they have no access to `projectId` from the URL —
  either move them to `web/app/projects/[projectId]/runs/[id]/gate-1/` or pass projectId
  via a query string.

## Commit

```bash
feat(gates): add Gate 1 and Gate 2 review with approval/rejection and structured pushback
```
