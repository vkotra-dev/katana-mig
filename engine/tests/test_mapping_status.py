"""Tests for mapping_status computation and 409 error detail."""

from __future__ import annotations

from datetime import datetime
import pytest
import uuid

from sqlalchemy.orm import Session

from migrations_engine.db.models import (
    Feed,
    MappingSnapshot,
    ProjectRegistry,
    ProjectDefinition,
    User,
)
from migrations_engine.management.feeds import (
    _dedup_snapshots,
    _compute_status_from_snapshots,
    _compute_mapping_status,
    _batch_mapping_status,
)
from sqlite_test_support import SessionLocal


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def project_id(db):
    pid = f"proj_{uuid.uuid4().hex}"
    def_id = f"def_{uuid.uuid4().hex}"
    db.add(ProjectDefinition(definition_id=def_id, project_id=pid, name="Test Project"))
    db.add(ProjectRegistry(project_id=pid, name="Test Project", definition_id=def_id, status="active"))
    db.commit()
    return pid


@pytest.fixture
def feed(db, project_id):
    feed_id = f"feed_{uuid.uuid4().hex}"
    f = Feed(
        source_definition_id=feed_id,
        project_id=project_id,
        source_type="csv",
        source_contract_version="v1",
        status="active",
    )
    db.add(f)
    db.commit()
    return f


@pytest.fixture
def another_feed(db, project_id):
    feed_id = f"feed_{uuid.uuid4().hex}"
    f = Feed(
        source_definition_id=feed_id,
        project_id= project_id,
        source_type="csv",
        source_contract_version="v1",
        status="active",
    )
    db.add(f)
    db.commit()
    return f


# --- _dedup_snapshots ---

class TestDedupSnapshots:
    def _make(self, sid, feed_id, table, status, created=datetime(2024, 1, 1)):
        return MappingSnapshot(
            mapping_snapshot_id=sid,
            project_id="p1",
            source_definition_id=feed_id,
            destination_object_name=table,
            field_bindings=[],
            destination_fields=[],
            destination_columns=[],
            status=status,
            current_ball_role=None,
            approved_at=None,
            approved_by_user_id=None,
            mapping_snapshot_version="1",
            created_at=created,
        )

    def test_returns_latest_per_table(self, db):
        snap1 = self._make(f"td_{uuid.uuid4().hex[:8]}", "feed1", "orders", "draft", datetime(2024, 1, 1))
        snap2 = self._make(f"td_{uuid.uuid4().hex[:8]}", "feed1", "orders", "approved", datetime(2024, 1, 2))
        # Caller must ORDER BY created_at DESC, so latest comes first.
        result = _dedup_snapshots([snap2, snap1])
        assert len(result) == 1
        assert result[0].destination_object_name == "orders"
        assert result[0].status == "approved"

    def test_keeps_multiple_tables(self, db):
        snap1 = self._make(f"td_{uuid.uuid4().hex[:8]}", "feed1", "orders", "draft")
        snap2 = self._make(f"td_{uuid.uuid4().hex[:8]}", "feed1", "users", "approved")
        result = _dedup_snapshots([snap1, snap2])
        assert len(result) == 2

    def test_keys_on_source_definition_id_for_batch(self, db):
        """Different feeds with same table name should NOT dedup together."""
        snap1 = self._make(f"td_{uuid.uuid4().hex[:8]}", "feed1", "orders", "draft")
        snap2 = self._make(f"td_{uuid.uuid4().hex[:8]}", "feed2", "orders", "approved")
        result = _dedup_snapshots([snap1, snap2])
        assert len(result) == 2, "Snapshots from different feeds should not dedup against each other"


# --- _compute_status_from_snapshots ---

class TestComputeStatusFromSnapshots:
    def test_all_approved(self, db):
        snaps = [MappingSnapshot(
            mapping_snapshot_id=f"cs_{uuid.uuid4().hex[:8]}",
            project_id="p1", source_definition_id="feed1",
            destination_object_name="orders",
            field_bindings=[], destination_fields=[], destination_columns=[],
            status="approved", current_ball_role=None,
            approved_at=None, approved_by_user_id=None,
            mapping_snapshot_version="1", created_at=datetime(2024, 1, 1),
        )]
        assert _compute_status_from_snapshots(snaps) == "approved"

    def test_all_draft(self, db):
        snaps = [MappingSnapshot(
            mapping_snapshot_id=f"cs_{uuid.uuid4().hex[:8]}",
            project_id="p1", source_definition_id="feed1",
            destination_object_name="orders",
            field_bindings=[], destination_fields=[], destination_columns=[],
            status="draft", current_ball_role=None,
            approved_at=None, approved_by_user_id=None,
            mapping_snapshot_version="1", created_at=datetime(2024, 1, 1),
        )]
        assert _compute_status_from_snapshots(snaps) == "draft"

    def test_only_rejected(self, db):
        snaps = [MappingSnapshot(
            mapping_snapshot_id=f"cs_{uuid.uuid4().hex[:8]}",
            project_id="p1", source_definition_id="feed1",
            destination_object_name="orders",
            field_bindings=[], destination_fields=[], destination_columns=[],
            status="rejected", current_ball_role=None,
            approved_at=None, approved_by_user_id=None,
            mapping_snapshot_version="1", created_at=datetime(2024, 1, 1),
        )]
        assert _compute_status_from_snapshots(snaps) == "draft"

    def test_approved_and_draft(self, db):
        snaps = [
            MappingSnapshot(mapping_snapshot_id=f"cs_{uuid.uuid4().hex[:8]}", project_id="p1", source_definition_id="feed1", destination_object_name="a", field_bindings=[], destination_fields=[], destination_columns=[], status="approved", current_ball_role=None, approved_at=None, approved_by_user_id=None, mapping_snapshot_version="1", created_at=datetime(2024, 1, 1)),
            MappingSnapshot(mapping_snapshot_id=f"cs_{uuid.uuid4().hex[:8]}", project_id="p1", source_definition_id="feed1", destination_object_name="b", field_bindings=[], destination_fields=[], destination_columns=[], status="draft", current_ball_role=None, approved_at=None, approved_by_user_id=None, mapping_snapshot_version="1", created_at=datetime(2024, 1, 1)),
        ]
        assert _compute_status_from_snapshots(snaps) == "partial"

    def test_approved_and_rejected(self, db):
        snaps = [
            MappingSnapshot(mapping_snapshot_id=f"cs_{uuid.uuid4().hex[:8]}", project_id="p1", source_definition_id="feed1", destination_object_name="a", field_bindings=[], destination_fields=[], destination_columns=[], status="approved", current_ball_role=None, approved_at=None, approved_by_user_id=None, mapping_snapshot_version="1", created_at=datetime(2024, 1, 1)),
            MappingSnapshot(mapping_snapshot_id=f"cs_{uuid.uuid4().hex[:8]}", project_id="p1", source_definition_id="feed1", destination_object_name="b", field_bindings=[], destination_fields=[], destination_columns=[], status="rejected", current_ball_role=None, approved_at=None, approved_by_user_id=None, mapping_snapshot_version="1", created_at=datetime(2024, 1, 1)),
        ]
        assert _compute_status_from_snapshots(snaps) == "partial"

    def test_rejected_and_draft(self, db):
        snaps = [
            MappingSnapshot(mapping_snapshot_id=f"cs_{uuid.uuid4().hex[:8]}", project_id="p1", source_definition_id="feed1", destination_object_name="a", field_bindings=[], destination_fields=[], destination_columns=[], status="rejected", current_ball_role=None, approved_at=None, approved_by_user_id=None, mapping_snapshot_version="1", created_at=datetime(2024, 1, 1)),
            MappingSnapshot(mapping_snapshot_id=f"cs_{uuid.uuid4().hex[:8]}", project_id="p1", source_definition_id="feed1", destination_object_name="b", field_bindings=[], destination_fields=[], destination_columns=[], status="draft", current_ball_role=None, approved_at=None, approved_by_user_id=None, mapping_snapshot_version="1", created_at=datetime(2024, 1, 1)),
        ]
        assert _compute_status_from_snapshots(snaps) == "partial"

    def test_empty_list(self, db):
        assert _compute_status_from_snapshots([]) is None

    def _make_snapshot(self, status):
        sid = f"snap_{uuid.uuid4().hex[:8]}"
        return MappingSnapshot(
            mapping_snapshot_id=sid,
            project_id="p1",
            source_definition_id="feed1",
            destination_object_name="orders",
            field_bindings=[],
            destination_fields=[],
            destination_columns=[],
            status=status,
            current_ball_role=None,
            approved_at=None,
            approved_by_user_id=None,
            mapping_snapshot_version="1",
            created_at=datetime(2024, 1, 1),
        )


# --- Integration: _compute_mapping_status ---

class TestComputeMappingStatus:
    def _snap(self, db, project_id, feed_id, table, status, version=1, created=datetime(2024, 1, 1)):
        return MappingSnapshot(
            mapping_snapshot_id=f"ms_{uuid.uuid4().hex[:8]}",
            project_id=project_id,
            source_definition_id=feed_id,
            destination_object_name=table,
            field_bindings=[],
            destination_fields=[],
            destination_columns=[],
            status=status,
            current_ball_role=None,
            approved_at=None,
            approved_by_user_id=None,
            mapping_snapshot_version=str(version),
            created_at=created,
        )

    def test_no_snapshots(self, db, project_id, feed):
        result = _compute_mapping_status(db, project_id=project_id, feed_id=feed.source_definition_id)
        assert result is None

    def test_draft_snapshot(self, db, project_id, feed):
        db.add(self._snap(db, project_id, feed.source_definition_id, "orders", "draft"))
        db.commit()
        result = _compute_mapping_status(db, project_id=project_id, feed_id=feed.source_definition_id)
        assert result == "draft"

    def test_approved_snapshot(self, db, project_id, feed):
        db.add(self._snap(db, project_id, feed.source_definition_id, "orders", "approved"))
        db.commit()
        result = _compute_mapping_status(db, project_id=project_id, feed_id=feed.source_definition_id)
        assert result == "approved"

    def test_rejected_then_draft_same_table(self, db, project_id, feed):
        """Rejected row is deduped away; latest row is draft → 'draft'."""
        db.add(self._snap(db, project_id, feed.source_definition_id, "orders", "rejected", created=datetime(2024, 1, 1)))
        db.add(self._snap(db, project_id, feed.source_definition_id, "orders", "draft", version=2, created=datetime(2024, 1, 2)))
        db.commit()
        result = _compute_mapping_status(db, project_id=project_id, feed_id=feed.source_definition_id)
        assert result == "draft", "Latest snapshot is 'draft', rejected should be deduped away"

    def test_approved_plus_rejected(self, db, project_id, feed):
        """Approved table + rejected table → 'partial', not 'approved'."""
        db.add(self._snap(db, project_id, feed.source_definition_id, "orders", "approved"))
        db.add(self._snap(db, project_id, feed.source_definition_id, "users", "rejected"))
        db.commit()
        result = _compute_mapping_status(db, project_id=project_id, feed_id=feed.source_definition_id)
        assert result == "partial", "Approved + rejected should be partial, not approved"


# --- Integration: _batch_mapping_status ---

class TestBatchMappingStatus:
    def _snap(self, db, project_id, feed_id, table, status, created=datetime(2024, 1, 1)):
        return MappingSnapshot(
            mapping_snapshot_id=f"bs_{uuid.uuid4().hex[:8]}",
            project_id=project_id,
            source_definition_id=feed_id,
            destination_object_name=table,
            field_bindings=[],
            destination_fields=[],
            destination_columns=[],
            status=status,
            current_ball_role=None,
            approved_at=None,
            approved_by_user_id=None,
            mapping_snapshot_version="1",
            created_at=created,
        )

    def test_batches_correctly(self, db, project_id, feed, another_feed):
        """Snapshots from different feeds should not interfere."""
        db.add(self._snap(db, project_id, feed.source_definition_id, "orders", "approved"))
        # Same table name, different feed — should NOT dedup together
        db.add(self._snap(db, project_id, another_feed.source_definition_id, "orders", "draft"))
        db.commit()
        status_map = _batch_mapping_status(
            db,
            project_id=project_id,
            feed_ids={feed.source_definition_id, another_feed.source_definition_id},
        )
        assert status_map[feed.source_definition_id] == "approved"
        assert status_map[another_feed.source_definition_id] == "draft"


# --- 409 error detail ---

class Test409ErrorDetail:
    def test_integrity_error_includes_detail(self):
        from migrations_engine.api.deps import AuthApiError

        try:
            raise AuthApiError(
                "mapping_already_proposed",
                "Mapping has already been proposed for this feed.",
                409,
                {"per_table_status": {"orders": ["approved"]}},
            )
        except AuthApiError as exc:
            assert exc.status_code == 409
            assert exc.detail == {"per_table_status": {"orders": ["approved"]}}
