from __future__ import annotations

import csv
import io
import uuid

import pytest
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

from migrations_engine.auth.passwords import hash_password  # noqa: E402
from migrations_engine.config import get_settings  # noqa: E402
from migrations_engine.db.base import Base  # noqa: E402
from migrations_engine.db.models import (  # noqa: E402
    ChangeRequest,
        LookupSnapshot,
        MappingSnapshot,
        ProjectDefinition,
        ProjectRegistry,
    RunCheckpoint,
    RunRecord,
    SourceDefinition,
    SourceSlice,
    SourceSliceRow,
    User,
)
from migrations_engine.db.session import SessionLocal  # noqa: E402
from migrations_engine.execution.engine import execute_run  # noqa: E402
from migrations_engine.mapping import FieldBinding, create_approved_lookup_snapshot, create_approved_mapping_snapshot  # noqa: E402
from migrations_engine.mapping.constants import LOOKUP_DELTA_CHANGE_REQUEST_TYPE  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _setup_sqlite_db() -> None:
    Base.metadata.create_all(bind=_sqlite_engine)

    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")

    with SessionLocal() as db:
        db.add(
            User(
                user_id=str(uuid.uuid4()),
                email=settings.bootstrap_admin_email.strip().lower(),
                display_name=settings.bootstrap_admin_display_name,
                password_hash=hash_password(settings.bootstrap_admin_password),
                role=CENTRAL_TEAM_ROLE,
                status="active",
            )
        )
        db.commit()


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def _make_project(db) -> str:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    db.add(
        ProjectDefinition(
            definition_id=definition_id,
            project_id=project_id,
            name="Execution Project",
            status="active",
        )
    )
    db.add(
        ProjectRegistry(
            project_id=project_id,
            name="Execution Project",
            definition_id=definition_id,
            status="active",
        )
    )
    db.flush()
    return project_id


def _seed_source_slice(db, *, project_id: str, row_values: list[str]) -> SourceSlice:
    source_definition = SourceDefinition(
        source_definition_id=str(uuid.uuid4()),
        project_id=project_id,
        source_type="csv",
        source_contract_version="v1",
        source_details={"label": "Customers", "encoding": "utf-8"},
        status="active",
    )
    db.add(source_definition)
    db.flush()

    slice_row = SourceSlice(
        source_slice_id=str(uuid.uuid4()),
        source_definition_id=source_definition.source_definition_id,
        source_contract_version="v1",
        source_slice_version="v1",
        source_schema_artifact=None,
        masking_policy=None,
        header_csv="STATUS,PLAN",
        slice_payload=None,
        status="approved",
        parse_warnings=[],
        file_storage_path=None,
    )
    db.add(slice_row)
    db.flush()

    for index, value in enumerate(row_values):
        db.add(
            SourceSliceRow(
                source_slice_id=slice_row.source_slice_id,
                row_index=index,
                row_csv=value,
            )
        )
    db.flush()
    return slice_row


def _seed_snapshots(db, *, project_id: str) -> None:
    create_approved_mapping_snapshot(
        db,
        project_id=project_id,
        destination_object_name="Customer",
        mapping_snapshot_version="v1",
        field_bindings=[
            FieldBinding(
                source_field="STATUS",
                destination_field="status",
                lookup_name="status_map",
            ),
            FieldBinding(
                source_field="PLAN",
                destination_field="plan",
                lookup_name="plan_map",
            ),
        ],
    )
    create_approved_lookup_snapshot(
        db,
        project_id=project_id,
        lookup_name="status_map",
        lookup_snapshot_version="v1",
        value_map={"A": "ACTIVE"},
    )
    create_approved_lookup_snapshot(
        db,
        project_id=project_id,
        lookup_name="plan_map",
        lookup_snapshot_version="v7",
        value_map={"Gold": "GOLD"},
    )
    db.commit()


def _create_run(db, *, project_id: str, source_definition_id: str) -> RunRecord:
    run = RunRecord(
        run_id=str(uuid.uuid4()),
        project_id=project_id,
        destination_object_name="Customer",
        source_definition_reference=source_definition_id,
        status="queued",
    )
    db.add(run)
    db.commit()
    return run


def test_execute_run_completes_and_writes_checkpoint() -> None:
    with SessionLocal() as db:
        project_id = _make_project(db)
        source_slice = _seed_source_slice(db, project_id=project_id, row_values=["A,Gold"] * 501)
        _seed_snapshots(db, project_id=project_id)
        run = _create_run(db, project_id=project_id, source_definition_id=source_slice.source_definition_id)

        execute_run(db, project_id=project_id, run_id=run.run_id, actor_user_id=None)

        stored_run = db.get(RunRecord, run.run_id)
        checkpoints = list(db.scalars(select(RunCheckpoint).where(RunCheckpoint.run_id == run.run_id)))

    assert stored_run is not None
    assert stored_run.status == "completed"
    assert stored_run.source_slice_version == "v1"
    assert stored_run.mapping_snapshot_version == "v1"
    assert stored_run.lookup_snapshot_version is None
    assert stored_run.lookup_snapshot_versions == {
        "plan_map": "v7",
        "status_map": "v1",
    }
    assert len(checkpoints) == 1
    assert checkpoints[0].checkpoint_payload is not None
    assert checkpoints[0].checkpoint_payload["last_completed_row"] == 499


def test_execute_run_pauses_for_lookup_delta_and_resumes() -> None:
    with SessionLocal() as db:
        project_id = _make_project(db)
        source_slice = _seed_source_slice(db, project_id=project_id, row_values=["A,Gold", "B,Gold"])
        _seed_snapshots(db, project_id=project_id)
        run = _create_run(db, project_id=project_id, source_definition_id=source_slice.source_definition_id)

        execute_run(db, project_id=project_id, run_id=run.run_id, actor_user_id=None)

        paused_run = db.get(RunRecord, run.run_id)
        change_request = db.scalar(select(ChangeRequest).where(ChangeRequest.project_id == project_id))

    assert paused_run is not None
    assert paused_run.status == "awaiting_approval"
    assert paused_run.pause_metadata is not None
    assert paused_run.pause_metadata["pause_reason"] == "lookup_delta"
    assert change_request is not None
    assert change_request.change_request_type == LOOKUP_DELTA_CHANGE_REQUEST_TYPE
    assert change_request.payload is not None
    assert change_request.payload["unmapped_value"] == "B"

    with SessionLocal() as db:
        create_approved_lookup_snapshot(
            db,
            project_id=project_id,
            lookup_name="status_map",
            lookup_snapshot_version="v2",
            value_map={"A": "ACTIVE", "B": "BLOCKED"},
        )
        db.commit()

        execute_run(db, project_id=project_id, run_id=run.run_id, actor_user_id=None, resume=True)

        resumed_run = db.get(RunRecord, run.run_id)
        checkpoints = list(db.scalars(select(RunCheckpoint).where(RunCheckpoint.run_id == run.run_id)))

    assert resumed_run is not None
    assert resumed_run.status == "completed"
    assert resumed_run.lookup_snapshot_version is None
    assert resumed_run.lookup_snapshot_versions == {
        "plan_map": "v7",
        "status_map": "v2",
    }
    assert len(checkpoints) >= 1
    assert checkpoints[-1].checkpoint_payload is not None
    assert resumed_run.completion_metadata is not None
    assert resumed_run.completion_metadata["last_completed_row"] == 1
