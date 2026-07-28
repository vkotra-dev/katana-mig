"""
Tests for mapping_ownership_warnings on FeedResponse.

Covers:
- Feed B's destination_object_references includes a table Feed A owns → Feed B gets a warning.
- No conflict → field is null.
- Project-scoped (NULL source_definition_id) approved snapshot → warning with null fields.
- Discarded owning feed → excluded.
- Batch path (list_source_contracts) matches single-feed path.
- A feed's own approved table → no self-warning.
"""

import uuid
from typing import Any, cast

import pytest
from sqlalchemy.orm import Session

from migrations_engine.db.models import Feed, MappingSnapshot, ProjectDefinition, ProjectRegistry, User
from migrations_engine.management.feeds import (
    _batch_ownership_warnings,
    _compute_ownership_warnings,
    list_source_contracts,
    _source_contract_response,
)

from sqlite_test_support import SessionLocal


@pytest.fixture
def db() -> Session:
    with SessionLocal() as s:
        yield s


@pytest.fixture
def project_id(db: Session) -> str:
    pid = f"proj_{uuid.uuid4().hex}"
    def_id = f"def_{uuid.uuid4().hex}"
    db.add(ProjectDefinition(definition_id=def_id, project_id=pid, name="Test Project"))
    db.add(ProjectRegistry(project_id=pid, name="Test Project", definition_id=def_id, status="active"))
    db.commit()
    return pid


def _create_feed(db: Session, project_id: str, feed_id: str | None = None, status: str = "active",
                 destination_object_references: list[str] | None = None,
                 label: str | None = None) -> str:
    sid = feed_id or f"feed_{uuid.uuid4().hex}"
    f = Feed(
        source_definition_id=sid,
        project_id=project_id,
        source_type="csv",
        source_contract_version="v1",
        source_details={"label": label or f"Feed {sid[:8]}"},
        status=status,
        destination_object_references=destination_object_references or [],
    )
    db.add(f)
    db.commit()
    return sid


def _create_snapshot(db: Session, project_id: str, source_definition_id: str | None,
                     destination_object_name: str, status: str = "approved") -> None:
    snap = MappingSnapshot(
        mapping_snapshot_id=f"snap_{uuid.uuid4().hex}",
        project_id=project_id,
        source_definition_id=source_definition_id,
        destination_object_name=destination_object_name,
        mapping_snapshot_version="v1",
        field_bindings=[],
        status=status,
    )
    db.add(snap)
    db.commit()


# --- Single-feed _compute_ownership_warnings ---

def test_cross_feed_warning(db: Session, project_id: str) -> None:
    feed_a = _create_feed(db, project_id, label="Feed A", destination_object_references=["Customer"])
    feed_b = _create_feed(db, project_id, label="Feed B", destination_object_references=["Customer"])

    # Feed A owns "Customer"
    _create_snapshot(db, project_id, feed_a, "Customer", "approved")

    # Get Feed B's response
    feed_obj = db.query(Feed).filter(Feed.source_definition_id == feed_b).first()
    resp = _source_contract_response(cast(Any, feed_obj), db=db)

    warnings = resp.mapping_ownership_warnings
    assert warnings is not None
    assert "Customer" in warnings
    assert warnings["Customer"].source_definition_id == feed_a


def test_no_conflict_field_null(db: Session, project_id: str) -> None:
    _create_feed(db, project_id, label="Feed A", destination_object_references=["Customer"])
    feed_b = _create_feed(db, project_id, label="Feed B", destination_object_references=["Orders"])
    _create_snapshot(db, project_id, feed_b, "Orders", "approved")

    feed_obj = db.query(Feed).filter(Feed.source_definition_id == feed_b).first()
    resp = _source_contract_response(cast(Any, feed_obj), db=db)

    assert resp.mapping_ownership_warnings is None


def test_project_scoped_snapshot(db: Session, project_id: str) -> None:
    """Project-scoped (NULL source_definition_id) approved snapshot → warning with null fields."""
    feed_b = _create_feed(db, project_id, label="Feed B", destination_object_references=["Customer"])

    _create_snapshot(db, project_id, None, "Customer", "approved")

    feed_obj = db.query(Feed).filter(Feed.source_definition_id == feed_b).first()
    resp = _source_contract_response(cast(Any, feed_obj), db=db)

    warnings = resp.mapping_ownership_warnings
    assert warnings is not None
    assert "Customer" in warnings
    assert warnings["Customer"].source_definition_id is None
    assert warnings["Customer"].feed_label is None
    assert warnings["Customer"].feed_source_type is None


def test_discarded_feed_excluded(db: Session, project_id: str) -> None:
    feed_a = _create_feed(db, project_id, label="Feed A", destination_object_references=["Customer"])
    feed_b = _create_feed(db, project_id, label="Feed B", destination_object_references=["Customer"])

    _create_snapshot(db, project_id, feed_a, "Customer", "approved")

    # Discard Feed A
    feed_a_obj = db.query(Feed).filter(Feed.source_definition_id == feed_a).first()
    feed_a_obj.status = "discarded"
    db.commit()

    feed_obj = db.query(Feed).filter(Feed.source_definition_id == feed_b).first()
    resp = _source_contract_response(cast(Any, feed_obj), db=db)

    # Feed A's snapshot should be excluded because Feed A is discarded
    assert resp.mapping_ownership_warnings is None


def test_own_table_no_self_warning(db: Session, project_id: str) -> None:
    feed = _create_feed(db, project_id, label="Feed A")
    _create_snapshot(db, project_id, feed, "Customer", "approved")

    feed_obj = db.query(Feed).filter(Feed.source_definition_id == feed).first()
    resp = _source_contract_response(cast(Any, feed_obj), db=db)

    # Feed should not warn against itself
    assert resp.mapping_ownership_warnings is None


# --- Batch path: list_source_contracts ---

def test_batch_list_source_contracts_includes_ownership_warnings(db: Session, project_id: str) -> None:
    feed_a = _create_feed(db, project_id, label="Feed A", destination_object_references=["Customer"])
    feed_b = _create_feed(db, project_id, label="Feed B", destination_object_references=["Customer"])

    _create_snapshot(db, project_id, feed_a, "Customer", "approved")

    rows = list_source_contracts(db, project_id=project_id)
    by_id = {r.source_definition_id: r for r in rows}

    b_resp = by_id.get(feed_b)
    assert b_resp is not None
    assert b_resp.mapping_ownership_warnings is not None
    assert "Customer" in b_resp.mapping_ownership_warnings
