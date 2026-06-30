from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.db.models import ProjectDefinition, ProjectRegistry, LookupValueMap, SourceDefinition


def _seed_source_definition(db) -> str:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    source_definition_id = str(uuid.uuid4())
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
            source_details={"label": "Customer Extract", "encoding": "utf-8"},
            status="active",
        )
    )
    db.commit()
    return source_definition_id


def test_lookup_value_map_persists_and_limits_one_draft_per_lookup() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)

    with SessionLocal() as db:
        source_definition_id = _seed_source_definition(db)
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
        assert stored.lookup_name == "status_code"
        assert stored.destination_table[0]["id"] == "ACTIVE"

        db.add(
            LookupValueMap(
                source_definition_id=source_definition_id,
                lookup_name="status_code",
                destination_table=[{"id": "PENDING", "label": "Pending"}],
                status="draft",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
