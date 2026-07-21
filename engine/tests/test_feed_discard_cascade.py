#!/usr/bin/env python3
"""
Test suite for feed discard cascade functionality.
This tests the cascade behavior when discarding feeds to MappingSnapshots, ProjectFibers, and LookupValueMaps
"""


from sqlalchemy.orm import Session

from migrations_engine.db.models import (
    Feed,
    MappingSnapshot,
    ProjectFiber,
    LookupValueMap,
)
from migrations_engine.management.feeds import discard_feed

from sqlite_test_support import SessionLocal
from dataclasses import dataclass
from migrations_engine.db.models import User

@dataclass
class MockActor:
    user: User
    token: str

import pytest
import uuid

@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session

from migrations_engine.db.models import ProjectRegistry, ProjectDefinition

@pytest.fixture
def project_id(db):
    pid = f"proj_{uuid.uuid4().hex}"
    def_id = f"def_{uuid.uuid4().hex}"
    db.add(ProjectDefinition(definition_id=def_id, project_id=pid, name="Test Project"))
    db.add(ProjectRegistry(project_id=pid, name="Test Project", definition_id=def_id, status="active"))
    db.commit()
    return pid

@pytest.fixture
def actor():
    return MockActor(user=User(user_id=f"user_{uuid.uuid4().hex}", email="test@example.com"), token="fake")

@pytest.fixture
def feed_definition_id(db, project_id):
    feed_id = f"feed_{uuid.uuid4().hex}"
    feed = Feed(
        source_definition_id=feed_id,
        project_id=project_id,
        source_type="test_type",
        source_contract_version="v1",
        status="active"
    )
    db.add(feed)
    db.commit()
    return feed_id

def test_discard_feed_cascades_to_mapping_snapshots_and_fibers(
    db: Session,
    project_id: str,
    actor: MockActor,
    feed_definition_id: str,
) -> None:
    # Create a test mapping snapshot
    mapping_snapshot = MappingSnapshot(
        mapping_snapshot_id=f"snap_{uuid.uuid4().hex}",
        project_id=project_id,
        source_definition_id=feed_definition_id,
        destination_object_name="test_table",
        mapping_snapshot_version="v1",
        field_bindings=[],
        status="active",
    )
    db.add(mapping_snapshot)
    
    # Create a test fiber
    fiber = ProjectFiber(
        project_id=project_id,
        feed_id=feed_definition_id,
        fiber_id=f"fib_{uuid.uuid4().hex}",
        fiber_type="test_type",
        fiber_key="test_key",
        status="active",
    )
    db.add(fiber)
    
    db.commit()
    
    # Verify initial state
    # Check mapping snapshot status
    db.refresh(mapping_snapshot)
    assert mapping_snapshot.status == "active"
    
    # Check fiber status
    db.refresh(fiber)
    assert fiber.status == "active"
    
    # Discard feed
    discard_feed(
        db,
        actor=actor.user,
        project_id=project_id,
        source_definition_id=feed_definition_id,
    )
    
    # Verify cascade behavior
    # Check mapping snapshot is discarded
    db.refresh(mapping_snapshot)
    assert mapping_snapshot.status == "discarded"
    
    # Check fiber is discarded
    db.refresh(fiber)
    assert fiber.status == "discarded"
    
    # Check feed is discarded
    feed = db.get(Feed, feed_definition_id)
    assert feed.status == "discarded"


def test_discard_feed_cascades_to_lookup_value_maps(
    db: Session,
    project_id: str,
    actor: MockActor,
    feed_definition_id: str,
) -> None:
    # Create a test lookup value map
    lookup_map = LookupValueMap(
        lookup_value_map_id=f"lvm_{uuid.uuid4().hex}",
        project_id=project_id,
        lookup_name="test_lookup_name",
        destination_table=[],
        status="active",
    )
    db.add(lookup_map)
    
    # Create a mapping snapshot with lookup binding
    mapping_snapshot = MappingSnapshot(
        mapping_snapshot_id=f"snap_{uuid.uuid4().hex}",
        project_id=project_id,
        source_definition_id=feed_definition_id,
        destination_object_name="test_table",
        mapping_snapshot_version="v1",
        field_bindings=[
            {
                "binding_type": "lookup_fk",
                "lookup_name": "test_lookup_name",
            }
        ],
        status="active",
    )
    db.add(mapping_snapshot)
    
    db.commit()
    
    # Verify initial state
    db.refresh(lookup_map)
    assert lookup_map.status == "active"
    
    # Discard feed
    discard_feed(
        db,
        actor=actor.user,
        project_id=project_id,
        source_definition_id=feed_definition_id,
    )
    
    # Verify lookup map is discarded (because it's exclusive)
    db.refresh(lookup_map)
    assert lookup_map.status == "discarded"


def test_discard_feed_cascade_lookup_shared(
    db: Session,
    project_id: str,
    actor: MockActor,
    feed_definition_id: str,
) -> None:
    # Create a lookup value map
    lookup_map = LookupValueMap(
        lookup_value_map_id=f"lvm_{uuid.uuid4().hex}",
        project_id=project_id,
        lookup_name="shared_lookup",
        destination_table=[],
        status="active",
    )
    db.add(lookup_map)
    other_feed_id = f"feed_{uuid.uuid4().hex}"
    
    # Create another feed that also uses the lookup
    other_feed = Feed(
        source_definition_id=other_feed_id,
        project_id=project_id,
        source_type="test_type",
        source_contract_version="v1",
        status="active",
    )
    db.add(other_feed)
    
    # Create a mapping snapshot for the other feed that uses the same lookup
    mapping_snapshot = MappingSnapshot(
        mapping_snapshot_id=f"snap_{uuid.uuid4().hex}",
        project_id=project_id,
        source_definition_id=other_feed_id,
        destination_object_name="test_table",
        mapping_snapshot_version="v1",
        field_bindings=[
            {
                "binding_type": "lookup_fk",
                "lookup_name": "shared_lookup",
            }
        ],
        status="active",
    )
    db.add(mapping_snapshot)
    
    db.commit()
    
    # Verify initial state
    db.refresh(lookup_map)
    assert lookup_map.status == "active"
    
    # Discard the first feed
    discard_feed(
        db,
        actor=actor.user,
        project_id=project_id,
        source_definition_id=feed_definition_id,
    )
    
    # Verify the shared lookup map is NOT discarded because it's shared
    db.refresh(lookup_map)
    # It should still be active because it's shared
    assert lookup_map.status == "active"


def test_discard_feed_cascade_with_existing_discarded_mappings(
    db: Session,
    project_id: str,
    actor: MockActor,
    feed_definition_id: str,
) -> None:
    # Create a mapping snapshot in discarded status
    mapping_snapshot = MappingSnapshot(
        mapping_snapshot_id=f"snap_{uuid.uuid4().hex}",
        project_id=project_id,
        source_definition_id=feed_definition_id,
        destination_object_name="test_table",
        mapping_snapshot_version="v1",
        field_bindings=[],
        status="discarded",
    )
    db.add(mapping_snapshot)
    
    # Create a fiber
    fiber = ProjectFiber(
        project_id=project_id,
        feed_id=feed_definition_id,
        fiber_id="test_fiber_1",
        fiber_type="test_type",
        fiber_key="test_key",
        status="active",
    )
    db.add(fiber)
    
    db.commit()
    
    # Verify initial state
    db.refresh(mapping_snapshot)
    assert mapping_snapshot.status == "discarded"
    
    # Discard feed
    discard_feed(
        db,
        actor=actor.user,
        project_id=project_id,
        source_definition_id=feed_definition_id,
    )
    
    # Verify cascade behavior
    db.refresh(mapping_snapshot)
    assert mapping_snapshot.status == "discarded"
    
    # Fiber should still be active (but it gets cascaded in the cascade code)
    db.refresh(fiber)
    assert fiber.status == "discarded"  # This should be discarded