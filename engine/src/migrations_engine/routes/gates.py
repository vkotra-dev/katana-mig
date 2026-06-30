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
from ..management.gates import approve_gate, get_gate1_evidence, get_gate2_evidence, get_gate_status, reject_gate

router = APIRouter(prefix="/projects/{project_id}/runs/{run_id}/gates", tags=["gates"])


@router.get("", response_model=GateStatusResponse)
def read_gates(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GateStatusResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_gate_status(db, project_id=project_id, run_id=run_id)


@router.get("/gate-1/evidence", response_model=Gate1EvidenceResponse)
def read_gate1_evidence(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Gate1EvidenceResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_gate1_evidence(db, project_id=project_id, run_id=run_id)


@router.get("/gate-2/evidence", response_model=Gate2EvidenceResponse)
def read_gate2_evidence(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Gate2EvidenceResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_gate2_evidence(db, project_id=project_id, run_id=run_id)


@router.post("/gate-1/approve", response_model=GateStatusResponse)
def approve_gate1(
    project_id: str,
    run_id: str,
    body: GateApproveRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> GateStatusResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return approve_gate(db, project_id=project_id, run_id=run_id, gate="gate_1", actor_user_id=actor.user_id, body=body)


@router.post("/gate-1/reject", response_model=GateStatusResponse)
def reject_gate1(
    project_id: str,
    run_id: str,
    body: GatePushbackRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> GateStatusResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return reject_gate(db, project_id=project_id, run_id=run_id, gate="gate_1", actor_user_id=actor.user_id, body=body)


@router.post("/gate-2/approve", response_model=GateStatusResponse)
def approve_gate2(
    project_id: str,
    run_id: str,
    body: GateApproveRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> GateStatusResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return approve_gate(db, project_id=project_id, run_id=run_id, gate="gate_2", actor_user_id=actor.user_id, body=body)


@router.post("/gate-2/reject", response_model=GateStatusResponse)
def reject_gate2(
    project_id: str,
    run_id: str,
    body: GatePushbackRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> GateStatusResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return reject_gate(db, project_id=project_id, run_id=run_id, gate="gate_2", actor_user_id=actor.user_id, body=body)
