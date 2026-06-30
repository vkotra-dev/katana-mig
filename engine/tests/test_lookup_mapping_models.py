from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from migrations_engine.db.base import Base
from migrations_engine.db.models import LookupValueMap, ProjectDefinition, ProjectRegistry, SourceDefinition, SourceValueSummary
from migrations_engine.db.session import SessionLocal, engine


def _seed_source_definition() -> tuple[str, str]:
    Base.metadata.create_all(bind=engine)
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    source_definition_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            ProjectDefinition(
                definition_id=definition_id,
                project_id=project_id,
                name="Lookup Project",
                status="active",
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name="Lookup Project",
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
                status="active",
            )
        )
        db.commit()
    return project_id, source_definition_id


def test_lookup_value_map_persists_and_blocks_duplicate_draft_per_lookup() -> None:
    _, source_definition_id = _seed_source_definition()

    with SessionLocal() as db:
        draft = LookupValueMap(
            source_definition_id=source_definition_id,
            lookup_name="status_code",
            destination_table=[
                {"id": "ACTIVE", "label": "Active"},
                {"id": "BLOCKED", "label": "Blocked"},
            ],
            status="draft",
        )
        db.add(draft)
        db.commit()

        stored = db.get(LookupValueMap, draft.lookup_value_map_id)
        assert stored is not None
        stored_lookup_name = stored.lookup_name
        stored_destination_table = stored.destination_table

        duplicate = LookupValueMap(
            source_definition_id=source_definition_id,
            lookup_name="status_code",
            destination_table=[{"id": "PENDING", "label": "Pending"}],
            status="draft",
        )
        db.add(duplicate)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    assert stored_lookup_name == "status_code"
    assert stored_destination_table[0]["id"] == "ACTIVE"


def test_source_value_summary_persists_counts() -> None:
    _, source_definition_id = _seed_source_definition()

    with SessionLocal() as db:
        summary = SourceValueSummary(
            source_definition_id=source_definition_id,
            source_slice_version="v1",
            field_name="status_code",
            value_counts={"A": 2, "B": 1},
        )
        db.add(summary)
        db.commit()

        stored = db.get(SourceValueSummary, summary.summary_id)

    assert stored is not None
    assert stored.field_name == "status_code"
    assert stored.value_counts == {"A": 2, "B": 1}
