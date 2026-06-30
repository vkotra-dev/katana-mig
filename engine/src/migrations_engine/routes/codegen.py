from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import CodegenArtifactResponse, CodegenTriggerResponse
from ..db.models import User
from ..management.access import require_project_access
from ..codegen.service import (
    build_delivery_bundle_text,
    generate_codegen_artifact,
    get_codegen_artifact,
    list_codegen_artifacts,
)

router = APIRouter(tags=["codegen"])


@router.post(
    "/projects/{project_id}/sources/{source_definition_id}/codegen",
    response_model=CodegenTriggerResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_codegen(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> CodegenTriggerResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return generate_codegen_artifact(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
    )


@router.get("/projects/{project_id}/codegen-artifacts", response_model=list[CodegenArtifactResponse])
def get_codegen_artifacts(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CodegenArtifactResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_codegen_artifacts(db, project_id=project_id)


@router.get("/projects/{project_id}/codegen-artifacts/{codegen_artifact_id}", response_model=CodegenArtifactResponse)
def get_codegen_artifact_route(
    project_id: str,
    codegen_artifact_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CodegenArtifactResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_codegen_artifact(db, project_id=project_id, codegen_artifact_id=codegen_artifact_id)


@router.get("/projects/{project_id}/delivery-bundle")
def download_delivery_bundle(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_project_access(db, user=actor, project_id=project_id)
    bundle = build_delivery_bundle_text(db, project_id=project_id)
    return Response(
        content=bundle.sql_bundle,
        media_type="text/plain",
        headers={"Content-Disposition": 'attachment; filename="delivery-bundle.sql"'},
    )
