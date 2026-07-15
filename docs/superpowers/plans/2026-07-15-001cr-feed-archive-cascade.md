# Feed Archive Cascade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a feed is discarded, cascade that status to its owned mapping snapshots and fibers; protect lookups shared across feeds; and prevent re-upload of a feed from duplicating mapping snapshots that already exist project-wide for the same destination tables.

**Architecture:** Three self-contained changes to `management/feeds.py` and `mapping/review.py`. No new models or migrations needed — all objects already carry a `status` column. Lookup sharing is detected at discard time by scanning active `MappingSnapshot.field_bindings` project-wide.

**Tech Stack:** Python 3.14, SQLAlchemy 2.x (ORM), FastAPI, pytest, SQLite (tests).

## Global Constraints

- Do not add new DB columns or migrations — use existing `status` fields only.
- All status strings are short lowercase with underscores, max 32 chars.
- Existing tests must remain green after every task.
- Test file for feeds: `engine/tests/test_mapping_review_api.py` and a new `engine/tests/test_feed_discard_cascade.py`.
- Run tests from `engine/` directory: `python -m pytest tests/ -v`.

---

## Object Status Reference

| Model | Table | Discard status to set |
|---|---|---|
| `Feed` | `source_definitions` | `"discarded"` (already set by `discard_feed`) |
| `MappingSnapshot` | `mapping_snapshots` | `"discarded"` |
| `ProjectFiber` | `project_fibers` | `"discarded"` |
| `LookupValueMap` | `lookup_value_maps` | skip if another active feed's snapshot references the same `lookup_name` |

`LookupSnapshot` is project-scoped with no feed link — leave untouched.

## Shared-Lookup Detection

A lookup is **shared** if any `MappingSnapshot` belonging to a *different, non-discarded* feed in the same project has a `field_binding` entry with `binding_type == "lookup_fk"` and `lookup_name == <name>`. Detection logic:

```python
def _lookup_names_for_feed(snapshots: list[MappingSnapshot]) -> set[str]:
    names: set[str] = set()
    for snap in snapshots:
        for b in (snap.field_bindings or []):
            if b.get("binding_type") == "lookup_fk" and b.get("lookup_name"):
                names.add(b["lookup_name"])
    return names

def _shared_lookup_names(
    db: Session, *, project_id: str, excluding_feed_id: str, candidate_names: set[str]
) -> set[str]:
    """Return lookup names from candidate_names that are also used by other active feeds."""
    if not candidate_names:
        return set()
    other_snapshots = db.scalars(
        select(MappingSnapshot).where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id != excluding_feed_id,
            MappingSnapshot.source_definition_id.isnot(None),
        )
    ).all()
    # Filter: only snapshots whose feed is not discarded
    active_other: list[MappingSnapshot] = []
    feed_ids = {s.source_definition_id for s in other_snapshots}
    if feed_ids:
        active_feeds = set(db.scalars(
            select(Feed.source_definition_id).where(
                Feed.source_definition_id.in_(feed_ids),
                Feed.status != "discarded",
            )
        ).all())
        active_other = [s for s in other_snapshots if s.source_definition_id in active_feeds]
    return candidate_names & _lookup_names_for_feed(active_other)
```

---

### Task 1: Cascade discard to mapping snapshots and fibers

**Files:**
- Modify: `engine/src/migrations_engine/management/feeds.py:74-108`
- Modify: `engine/src/migrations_engine/db/models.py` — add `MappingSnapshot`, `ProjectFiber`, `LookupValueMap` to imports
- Create: `engine/tests/test_feed_discard_cascade.py`

**Interfaces:**
- Consumes: `discard_feed(db, actor, project_id, source_definition_id) -> FeedResponse` (existing)
- Produces: same signature — extended to cascade status; callers unchanged

- [ ] **Step 1: Write the failing tests**

Create `engine/tests/test_feed_discard_cascade.py`:

```python
from __future__ import annotations

import uuid
from sqlalchemy import select
from fastapi.testclient import TestClient

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import (
    Feed, ProjectDefinition, ProjectRegistry, ProjectMembership,
    MappingSnapshot, ProjectFiber, LookupValueMap, User, new_id,
)
from migrations_engine.roles import CENTRAL_TEAM_ROLE

client = TestClient(app)


def _make_id() -> str:
    return str(uuid.uuid4())


def setup_module() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)


def _seed_user_and_project(db) -> tuple[User, str]:
    settings = get_settings()
    user = db.scalar(select(User).where(User.email == settings.bootstrap_admin_email.strip().lower()))
    if user is None:
        user = User(
            user_id=_make_id(),
            email=settings.bootstrap_admin_email.strip().lower(),
            display_name="Admin",
            password_hash=hash_password(settings.bootstrap_admin_password),
            role=CENTRAL_TEAM_ROLE,
            status="active",
        )
        db.add(user)
        db.flush()

    project_id = _make_id()
    reg = ProjectRegistry(project_id=project_id, status="active")
    defn = ProjectDefinition(definition_id=_make_id(), project_id=project_id)
    mem = ProjectMembership(project_id=project_id, user_id=user.user_id, role=CENTRAL_TEAM_ROLE)
    db.add_all([reg, defn, mem])
    db.flush()
    return user, project_id


def _seed_feed(db, project_id: str) -> Feed:
    feed = Feed(
        source_definition_id=new_id(),
        project_id=project_id,
        source_type="csv",
        source_contract_version="v1",
        status="active",
        source_details={"label": "test"},
    )
    db.add(feed)
    db.flush()
    return feed


def _seed_snapshot(db, project_id: str, feed_id: str, table: str, bindings=None) -> MappingSnapshot:
    snap = MappingSnapshot(
        mapping_snapshot_id=new_id(),
        project_id=project_id,
        source_definition_id=feed_id,
        destination_object_name=table,
        mapping_snapshot_version="v1",
        field_bindings=bindings or [],
        status="approved",
    )
    db.add(snap)
    db.flush()
    return snap


def _seed_fiber(db, project_id: str, feed_id: str, fiber_type: str, key: str) -> ProjectFiber:
    fiber = ProjectFiber(
        fiber_id=new_id(),
        project_id=project_id,
        feed_id=feed_id,
        fiber_type=fiber_type,
        fiber_key=key,
        status="mapped",
        source="auto",
    )
    db.add(fiber)
    db.flush()
    return fiber


def _seed_lookup_value_map(db, project_id: str, lookup_name: str) -> LookupValueMap:
    lvm = LookupValueMap(
        lookup_value_map_id=new_id(),
        project_id=project_id,
        lookup_name=lookup_name,
        destination_table=[],
        source_value_map={},
        status="draft",
    )
    db.add(lvm)
    db.flush()
    return lvm


def _admin_token() -> str:
    settings = get_settings()
    resp = client.post("/auth/login", json={
        "email": settings.bootstrap_admin_email,
        "password": settings.bootstrap_admin_password,
    })
    return resp.json()["access_token"]


def test_discard_cascades_to_mapping_snapshot() -> None:
    token = _admin_token()
    with SessionLocal() as db:
        _, project_id = _seed_user_and_project(db)
        feed = _seed_feed(db, project_id)
        snap = _seed_snapshot(db, project_id, feed.source_definition_id, "orders")
        db.commit()
        feed_id = feed.source_definition_id
        snap_id = snap.mapping_snapshot_id

    client.delete(
        f"/projects/{project_id}/sources/{feed_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    with SessionLocal() as db:
        snap = db.get(MappingSnapshot, snap_id)
        assert snap.status == "discarded"


def test_discard_cascades_to_fibers() -> None:
    token = _admin_token()
    with SessionLocal() as db:
        _, project_id = _seed_user_and_project(db)
        feed = _seed_feed(db, project_id)
        fiber = _seed_fiber(db, project_id, feed.source_definition_id, "domain_object", "orders")
        db.commit()
        feed_id = feed.source_definition_id
        fiber_id = fiber.fiber_id

    client.delete(
        f"/projects/{project_id}/sources/{feed_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    with SessionLocal() as db:
        fiber = db.get(ProjectFiber, fiber_id)
        assert fiber.status == "discarded"


def test_discard_cascades_to_unshared_lookup_value_map() -> None:
    token = _admin_token()
    with SessionLocal() as db:
        _, project_id = _seed_user_and_project(db)
        feed = _seed_feed(db, project_id)
        bindings = [{"binding_type": "lookup_fk", "lookup_name": "status_lkp",
                     "source_field": "status", "destination_field": "status_id"}]
        _seed_snapshot(db, project_id, feed.source_definition_id, "orders", bindings)
        lvm = _seed_lookup_value_map(db, project_id, "status_lkp")
        db.commit()
        feed_id = feed.source_definition_id
        lvm_id = lvm.lookup_value_map_id

    client.delete(
        f"/projects/{project_id}/sources/{feed_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    with SessionLocal() as db:
        lvm = db.get(LookupValueMap, lvm_id)
        assert lvm.status == "discarded"


def test_discard_preserves_shared_lookup_value_map() -> None:
    token = _admin_token()
    with SessionLocal() as db:
        _, project_id = _seed_user_and_project(db)
        feed1 = _seed_feed(db, project_id)
        feed2 = _seed_feed(db, project_id)
        shared_bindings = [{"binding_type": "lookup_fk", "lookup_name": "status_lkp",
                            "source_field": "status", "destination_field": "status_id"}]
        _seed_snapshot(db, project_id, feed1.source_definition_id, "orders", shared_bindings)
        _seed_snapshot(db, project_id, feed2.source_definition_id, "claims", shared_bindings)
        lvm = _seed_lookup_value_map(db, project_id, "status_lkp")
        db.commit()
        feed1_id = feed1.source_definition_id
        lvm_id = lvm.lookup_value_map_id

    client.delete(
        f"/projects/{project_id}/sources/{feed1_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    with SessionLocal() as db:
        lvm = db.get(LookupValueMap, lvm_id)
        assert lvm.status == "draft"  # preserved — feed2 still active
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd engine && python -m pytest tests/test_feed_discard_cascade.py -v
```

Expected: 4 failures — `AssertionError` because cascade doesn't happen yet.

- [ ] **Step 3: Implement cascade in `discard_feed`**

Open `engine/src/migrations_engine/management/feeds.py`. Replace the import line and extend `discard_feed`:

```python
# At top of file, extend the models import:
from ..db.models import (
    ProjectMembership, ProjectRegistry, Feed, FeedSlice, FeedSliceRow,
    RunRecord, User, MappingSnapshot, ProjectFiber, LookupValueMap, new_id,
)
```

Replace the body of `discard_feed` (keep the existing active-run guard):

```python
def discard_feed(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
) -> FeedResponse:
    feed = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    if feed.status == "discarded":
        raise AuthApiError("already_discarded", "Feed is already discarded.", 409)

    active_run = db.scalars(
        select(RunRecord).where(
            RunRecord.source_definition_reference == source_definition_id,
            RunRecord.status.in_(["running", "awaiting_approval"]),
        ).limit(1)
    ).first()
    if active_run is not None:
        raise AuthApiError(
            "run_in_progress",
            "Cannot discard a feed while a run is active or awaiting approval.",
            409,
        )

    # Cascade to mapping snapshots
    snapshots = db.scalars(
        select(MappingSnapshot).where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id == source_definition_id,
        )
    ).all()
    for snap in snapshots:
        snap.status = "discarded"

    # Cascade to fibers
    fibers = db.scalars(
        select(ProjectFiber).where(
            ProjectFiber.project_id == project_id,
            ProjectFiber.feed_id == source_definition_id,
        )
    ).all()
    for fiber in fibers:
        fiber.status = "discarded"

    # Cascade to lookup value maps — only if not shared with another active feed
    feed_lookup_names = _lookup_names_for_feed(list(snapshots))
    shared = _shared_lookup_names(
        db, project_id=project_id,
        excluding_feed_id=source_definition_id,
        candidate_names=feed_lookup_names,
    )
    exclusive_lookups = feed_lookup_names - shared
    if exclusive_lookups:
        lvms = db.scalars(
            select(LookupValueMap).where(
                LookupValueMap.project_id == project_id,
                LookupValueMap.lookup_name.in_(exclusive_lookups),
            )
        ).all()
        for lvm in lvms:
            lvm.status = "discarded"

    feed.status = "discarded"
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="source.feed.discarded",
        payload={"source_definition_id": source_definition_id},
    )
    db.commit()
    db.refresh(feed)
    return _source_contract_response(feed)


def _lookup_names_for_feed(snapshots: list[MappingSnapshot]) -> set[str]:
    names: set[str] = set()
    for snap in snapshots:
        for b in (snap.field_bindings or []):
            if b.get("binding_type") == "lookup_fk" and b.get("lookup_name"):
                names.add(b["lookup_name"])
    return names


def _shared_lookup_names(
    db: Session,
    *,
    project_id: str,
    excluding_feed_id: str,
    candidate_names: set[str],
) -> set[str]:
    if not candidate_names:
        return set()
    other_snapshots = db.scalars(
        select(MappingSnapshot).where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id != excluding_feed_id,
            MappingSnapshot.source_definition_id.isnot(None),
        )
    ).all()
    feed_ids = {s.source_definition_id for s in other_snapshots}
    if not feed_ids:
        return set()
    active_feed_ids = set(db.scalars(
        select(Feed.source_definition_id).where(
            Feed.source_definition_id.in_(feed_ids),
            Feed.status != "discarded",
        )
    ).all())
    active_other = [s for s in other_snapshots if s.source_definition_id in active_feed_ids]
    return candidate_names & _lookup_names_for_feed(active_other)
```

- [ ] **Step 4: Run cascade tests**

```bash
cd engine && python -m pytest tests/test_feed_discard_cascade.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
cd engine && python -m pytest tests/ -v
```

Expected: all existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/management/feeds.py \
        engine/tests/test_feed_discard_cascade.py
git commit -m "feat: cascade discard to mapping snapshots, fibers, and unshared lookups"
```

---

### Task 2: Block re-upload from duplicating project-wide approved mapping snapshots

**Files:**
- Modify: `engine/src/migrations_engine/mapping/review.py:317-327`
- Modify: `engine/tests/test_mapping_review_api.py` — add one new test

**Interfaces:**
- Consumes: `propose_mapping(db, project_id, source_definition_id, actor_user_id) -> MappingReviewResponse` (existing)
- Produces: same signature — now raises `mapping_already_proposed` (409) for destination tables that have an approved snapshot anywhere in the project, not just under the same feed

- [ ] **Step 1: Write the failing test**

Add to `engine/tests/test_mapping_review_api.py` (after the existing imports — `MappingSnapshot` is already imported via models, add it if missing):

```python
def test_propose_skips_tables_already_approved_project_wide(
    monkeypatch: pytest.MonkeyPatch, admin_token: str
) -> None:
    """Re-uploading a feed must not create a new snapshot for a destination
    table that already has an approved snapshot from a different feed."""
    from migrations_engine.db.models import MappingSnapshot, new_id
    from sqlite_test_support import SessionLocal

    # Seed an approved snapshot for "Customer" under a *different* active feed
    project_id, source_id = _seed_project()

    with SessionLocal() as db:
        from migrations_engine.db.models import Feed as FeedModel
        other_feed = FeedModel(
            source_definition_id=new_id(),
            project_id=project_id,
            source_type="csv",
            source_contract_version="v1",
            status="active",
            source_details={"label": "other"},
        )
        db.add(other_feed)
        db.flush()
        existing = MappingSnapshot(
            mapping_snapshot_id=new_id(),
            project_id=project_id,
            source_definition_id=other_feed.source_definition_id,
            destination_object_name="Customer",
            mapping_snapshot_version="v1",
            field_bindings=[],
            status="approved",
        )
        db.add(existing)
        db.commit()

    fake = FakeAdapter([
        {"source_field": "customer_id", "destination_field": "customer_id"},
    ])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)

    response = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "mapping_already_proposed"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd engine && python -m pytest tests/test_mapping_review_api.py::test_propose_skips_tables_already_approved_project_wide -v
```

Expected: FAIL — currently returns 200 and creates a duplicate snapshot.

- [ ] **Step 3: Extend `already_mapped_tables` to be project-wide for approved snapshots**

In `engine/src/migrations_engine/mapping/review.py`, replace lines 317-327:

```python
    # Tables already mapped under this feed
    feed_mapped = set(
        db.scalars(
            select(MappingSnapshot.destination_object_name).where(
                MappingSnapshot.project_id == project_id,
                MappingSnapshot.source_definition_id == source_definition_id,
            )
        ).all()
    )
    # Tables with an approved snapshot anywhere in this project (any active feed).
    # Uses outerjoin so project-scoped snapshots (source_definition_id=NULL) are included,
    # and discarded-feed snapshots are excluded even for historical data pre-Task-1.
    project_approved = set(
        db.scalars(
            select(MappingSnapshot.destination_object_name)
            .outerjoin(Feed, Feed.source_definition_id == MappingSnapshot.source_definition_id)
            .where(
                MappingSnapshot.project_id == project_id,
                MappingSnapshot.status == "approved",
                or_(
                    MappingSnapshot.source_definition_id.is_(None),
                    Feed.status != "discarded",
                ),
            )
        ).all()
    )
    already_mapped_tables = feed_mapped | project_approved

    expected_table_names = set(ddl_tables.keys())
    if already_mapped_tables >= expected_table_names:
        raise AuthApiError("mapping_already_proposed", "Mapping has already been proposed for this feed.", 409)
```

- [ ] **Step 4: Run the new test**

```bash
cd engine && python -m pytest tests/test_mapping_review_api.py::test_propose_skips_tables_already_approved_project_wide -v
```

Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
cd engine && python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/mapping/review.py \
        engine/tests/test_mapping_review_api.py
git commit -m "feat: block mapping re-proposal for project-wide approved destination tables"
```

---

## Self-Review

**Spec coverage:**
1. ✅ Cascade discard → mapping snapshots — Task 1
2. ✅ Cascade discard → fibers — Task 1
3. ✅ Shared lookup protection — Task 1 (`_shared_lookup_names`)
4. ✅ Re-upload precondition fix — Task 2
5. ✅ Archive vs discard semantics — resolved: using `"discarded"` uniformly (existing convention); no new status added per constraint

**Placeholder scan:** None found.

**Type consistency:** `_lookup_names_for_feed` and `_shared_lookup_names` defined and used within Task 1 only. `already_mapped_tables` variable renamed to split across two sets in Task 2 — downstream usage at line 420 (`if tbl_name in already_mapped_tables`) is unchanged and still correct since the variable is reassigned before that loop.
