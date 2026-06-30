from __future__ import annotations

import uuid

from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.db.models import (  # noqa: E402
    ProjectDefinition,
    ProjectRegistry,
    SourceDefinition,
    SourceSchemaArtifact,
    SourceValueSummary,
)


def _create_source_definition(db) -> str:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    db.add(
        ProjectDefinition(
            definition_id=definition_id,
            project_id=project_id,
            name="Source Analysis Project",
            status="active",
        )
    )
    db.add(
        ProjectRegistry(
            project_id=project_id,
            name="Source Analysis Project",
            definition_id=definition_id,
            status="active",
        )
    )
    db.add(
        SourceDefinition(
            source_definition_id=str(uuid.uuid4()),
            project_id=project_id,
            source_type="csv",
            source_contract_version="v1",
            source_details={"label": "Customer Extract", "encoding": "utf-8"},
            status="approved",
        )
    )
    db.flush()
    source_definition = db.scalar(select(SourceDefinition).where(SourceDefinition.project_id == project_id))
    assert source_definition is not None
    return source_definition.source_definition_id


def test_source_analysis_tables_persist_rows() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)

    with SessionLocal() as db:
        source_definition_id = _create_source_definition(db)
        schema_artifact = SourceSchemaArtifact(
            source_definition_id=source_definition_id,
            source_slice_version="v1",
            columns=[
                {"name": "CUST_ID", "inferred_type": "integer", "nullable": False, "max_length": 8},
                {"name": "SURNAME", "inferred_type": "text", "nullable": True, "max_length": 40},
            ],
        )
        summary = SourceValueSummary(
            source_definition_id=source_definition_id,
            source_slice_version="v1",
            field_name="SURNAME",
            value_counts={"Smith": 3, "Jones": 2},
        )
        db.add_all([schema_artifact, summary])
        db.commit()

        stored_schema = db.get(SourceSchemaArtifact, schema_artifact.schema_artifact_id)
        stored_summary = db.get(SourceValueSummary, summary.summary_id)

    assert stored_schema is not None
    assert stored_schema.source_definition_id == source_definition_id
    assert stored_schema.columns[0]["name"] == "CUST_ID"
    assert stored_summary is not None
    assert stored_summary.value_counts["Smith"] == 3
