from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.db.models import (  # noqa: E402
    ProjectDefinition,
    ProjectRegistry,
    SourceDefinition,
    SourceSchemaArtifact,
    SourceSlice,
    SourceSliceRow,
    SourceValueSummary,
    User,
)
from migrations_engine.management.source_analysis import (  # noqa: E402
    AnalysisResult,
    ColumnSchema,
    analyze_source_slice,
)
from migrations_engine.roles import CENTRAL_TEAM_ROLE  # noqa: E402


class FakeAdapter:
    def __init__(self, *, analysis_result: AnalysisResult) -> None:
        self.analysis_result = analysis_result
        self.calls: list[SimpleNamespace] = []
        self.model_id = "claude-haiku-4-5-20251001"

    def call(self, system: str, user: str, response_model: type[AnalysisResult]) -> AnalysisResult:
        self.calls.append(SimpleNamespace(system=system, user=user, response_model=response_model))
        return self.analysis_result


def _seed_approved_slice(
    db,
    *,
    row_count: int,
    unique_values: bool = False,
    mask_rows: bool = True,
) -> tuple[User, str, str]:
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
    source_definition_id = str(uuid.uuid4())
    db.add(actor)
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
            source_definition_id=source_definition_id,
            project_id=project_id,
            source_type="csv",
            source_contract_version="v1",
            source_details={"label": "Customer Extract", "encoding": "utf-8"},
            status="active",
        )
    )
    db.flush()
    db.add(
        SourceSlice(
            source_slice_id=str(uuid.uuid4()),
            source_definition_id=source_definition_id,
            source_contract_version="v1",
            source_slice_version="v1",
            source_schema_artifact=None,
            masking_policy={"masked_fields": ["SURNAME"]},
            header_csv="CUST_ID,SURNAME",
            slice_payload=None,
            status="approved",
            parse_warnings=[],
            file_storage_path="/tmp/source.csv",
            approved_at=datetime.now(UTC),
            approved_by_user_id=actor.user_id,
        )
    )
    db.flush()
    source_slice = db.scalar(select(SourceSlice).where(SourceSlice.source_definition_id == source_definition_id))
    assert source_slice is not None
    for index in range(row_count):
        if mask_rows:
            surname = "***"
        elif unique_values:
            surname = f"Value{index:03d}"
        else:
            surname = f"Value{index % 4:03d}"
        db.add(
            SourceSliceRow(
                source_slice_id=source_slice.source_slice_id,
                row_index=index,
                row_csv=f"{100000 + index},{surname}",
            )
        )
    db.commit()
    return actor, project_id, source_definition_id


def test_analyze_source_slice_caps_sample_and_masks_pii(monkeypatch: pytest.MonkeyPatch) -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)

    fake_adapter = FakeAdapter(
        analysis_result=AnalysisResult(
            columns=[
                ColumnSchema(name="CUST_ID", inferred_type="integer", nullable=False, max_length=8),
                ColumnSchema(name="SURNAME", inferred_type="text", nullable=True, max_length=40),
            ]
        )
    )
    monkeypatch.setattr("migrations_engine.management.source_analysis.get_adapter", lambda task: fake_adapter)

    with SessionLocal() as db:
        actor, project_id, source_definition_id = _seed_approved_slice(db, row_count=201)
        response = analyze_source_slice(
            db,
            actor=actor,
            project_id=project_id,
            source_definition_id=source_definition_id,
        )

        schemas = list(
            db.scalars(
                select(SourceSchemaArtifact).where(
                    SourceSchemaArtifact.source_definition_id == source_definition_id
                )
            )
        )
        summaries = list(
            db.scalars(
                select(SourceValueSummary).where(
                    SourceValueSummary.source_definition_id == source_definition_id
                )
            )
        )

    assert response.status == "completed"
    assert len(fake_adapter.calls) == 1
    assert fake_adapter.calls[0].system.startswith("You are a data analyst.")
    assert len(fake_adapter.calls[0].user.splitlines()) == 201
    assert "***" in fake_adapter.calls[0].user
    assert len(schemas) == 1
    assert len(summaries) == 2


def test_analyze_source_slice_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)

    fake_adapter = FakeAdapter(
        analysis_result=AnalysisResult(
            columns=[
                ColumnSchema(name="CUST_ID", inferred_type="integer", nullable=False, max_length=8),
            ]
        )
    )
    monkeypatch.setattr("migrations_engine.management.source_analysis.get_adapter", lambda task: fake_adapter)

    with SessionLocal() as db:
        actor, project_id, source_definition_id = _seed_approved_slice(db, row_count=2)
        first = analyze_source_slice(
            db,
            actor=actor,
            project_id=project_id,
            source_definition_id=source_definition_id,
        )
        second = analyze_source_slice(
            db,
            actor=actor,
            project_id=project_id,
            source_definition_id=source_definition_id,
        )

    assert first.schema_artifact_id == second.schema_artifact_id
    assert len(fake_adapter.calls) == 1


def test_analyze_source_slice_uses_field_mapping_adapter_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)

    fake_adapter = FakeAdapter(
        analysis_result=AnalysisResult(
            columns=[
                ColumnSchema(name="CUST_ID", inferred_type="integer", nullable=False, max_length=8),
            ]
        )
    )
    requested_tasks: list[str] = []

    def capture_adapter(task: str) -> FakeAdapter:
        requested_tasks.append(task)
        return fake_adapter

    monkeypatch.setattr("migrations_engine.management.source_analysis.get_adapter", capture_adapter)

    with SessionLocal() as db:
        actor, project_id, source_definition_id = _seed_approved_slice(db, row_count=1)
        response = analyze_source_slice(
            db,
            actor=actor,
            project_id=project_id,
            source_definition_id=source_definition_id,
        )

    assert response.status == "completed"
    assert requested_tasks == ["field_mapping"]
    assert len(fake_adapter.calls) == 1


def test_analyze_source_slice_caps_value_summary_distinct_values(monkeypatch: pytest.MonkeyPatch) -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)

    fake_adapter = FakeAdapter(
        analysis_result=AnalysisResult(
            columns=[
                ColumnSchema(name="CUST_ID", inferred_type="integer", nullable=False, max_length=8),
                ColumnSchema(name="SURNAME", inferred_type="text", nullable=True, max_length=40),
            ]
        )
    )
    monkeypatch.setattr("migrations_engine.management.source_analysis.get_adapter", lambda task: fake_adapter)

    with SessionLocal() as db:
        actor, project_id, source_definition_id = _seed_approved_slice(
            db,
            row_count=600,
            unique_values=True,
            mask_rows=False,
        )
        analyze_source_slice(
            db,
            actor=actor,
            project_id=project_id,
            source_definition_id=source_definition_id,
        )

        stored_summary = db.scalar(
            select(SourceValueSummary).where(
                SourceValueSummary.source_definition_id == source_definition_id,
                SourceValueSummary.field_name == "SURNAME",
            )
        )

    assert stored_summary is not None
    assert len(stored_summary.value_counts) == 500
