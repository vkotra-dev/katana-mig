from __future__ import annotations

import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_sqlite_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    future=True,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

from migrations_engine.db import session as db_session  # noqa: E402

db_session.engine = _sqlite_engine
db_session.SessionLocal = sessionmaker(
    bind=_sqlite_engine,
    autoflush=False,
    autocommit=False,
    class_=db_session.Session,
)

from migrations_engine.db.base import Base  # noqa: E402
from migrations_engine.db.models import (  # noqa: E402
    CodeGenerationArtifact,
    ProjectDefinition,
    ProjectRegistry,
    RunRecord,
)
from migrations_engine.db.session import SessionLocal  # noqa: E402


def _create_project(db) -> str:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    db.add(
        ProjectDefinition(
            definition_id=definition_id,
            project_id=project_id,
            name="Codegen Project",
            status="active",
        )
    )
    db.add(
        ProjectRegistry(
            project_id=project_id,
            name="Codegen Project",
            definition_id=definition_id,
            status="active",
        )
    )
    db.flush()
    return project_id


def test_code_generation_artifact_persists() -> None:
    Base.metadata.create_all(bind=_sqlite_engine)

    with SessionLocal() as db:
        project_id = _create_project(db)
        artifact = CodeGenerationArtifact(
            project_id=project_id,
            destination_object_name="Customer",
            source_slice_version="v1",
            mapping_snapshot_version="v1",
            lookup_snapshot_version="v1",
            sql_bundle="CREATE TABLE stg_customer (id INT);",
            status="active",
        )
        db.add(artifact)
        db.commit()

        stored = db.get(CodeGenerationArtifact, artifact.codegen_artifact_id)

    assert stored is not None
    assert stored.status == "active"
    assert stored.destination_object_name == "Customer"
    assert stored.sql_bundle == "CREATE TABLE stg_customer (id INT);"


def test_superseded_artifacts_leave_only_new_active_row() -> None:
    Base.metadata.create_all(bind=_sqlite_engine)

    with SessionLocal() as db:
        project_id = _create_project(db)
        first = CodeGenerationArtifact(
            project_id=project_id,
            destination_object_name="Customer",
            source_slice_version="v1",
            mapping_snapshot_version="v1",
            lookup_snapshot_version="v1",
            sql_bundle="-- v1",
            status="active",
        )
        db.add(first)
        db.flush()

        first.status = "superseded"

        second = CodeGenerationArtifact(
            project_id=project_id,
            destination_object_name="Customer",
            source_slice_version="v2",
            mapping_snapshot_version="v2",
            lookup_snapshot_version="v2",
            sql_bundle="-- v2",
            status="active",
        )
        db.add(second)
        db.commit()

        active_rows = list(
            db.scalars(
                select(CodeGenerationArtifact).where(
                    CodeGenerationArtifact.project_id == project_id,
                    CodeGenerationArtifact.destination_object_name == "Customer",
                    CodeGenerationArtifact.status == "active",
                )
            )
        )
        superseded_rows = list(
            db.scalars(
                select(CodeGenerationArtifact).where(
                    CodeGenerationArtifact.project_id == project_id,
                    CodeGenerationArtifact.destination_object_name == "Customer",
                    CodeGenerationArtifact.status == "superseded",
                )
            )
        )

    assert len(active_rows) == 1
    assert active_rows[0].sql_bundle == "-- v2"
    assert len(superseded_rows) == 1
    assert superseded_rows[0].status == "superseded"


def test_run_records_codegen_artifact_id_has_foreign_key() -> None:
    foreign_keys = RunRecord.__table__.c.codegen_artifact_id.foreign_keys
    assert len(foreign_keys) == 1
    foreign_key = next(iter(foreign_keys))
    assert foreign_key.column.table.name == "code_generation_artifacts"
    assert foreign_key.column.name == "codegen_artifact_id"
