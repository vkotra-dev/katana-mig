# Dry-Run Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `DryRunArtifact` DB model + migration, three read/approve/push-back API endpoints, and a review screen at `/projects/[id]/runs/[run_id]/dry-run` so central team operators can inspect engine-produced dry-run results and either approve (resume the run) or push back (pause with a comment).

**Architecture:** A single new `DryRunArtifact` row is created per run by the execution engine (that logic is out of scope here — this plan just creates the surface the engine writes to and the UI reads from). Three endpoints live in a new `routes/dry_run.py` router, service logic in `management/dry_run.py`. The frontend adds three helpers to the existing `web/lib/runs-api.ts` file and a new review page at `web/app/projects/[id]/runs/[run_id]/dry-run/page.tsx`.

**Tech Stack:** FastAPI, SQLAlchemy 2 (Mapped columns), Alembic, Pydantic v2, pytest, SQLite for tests; Next.js 15 App Router, TypeScript, Vitest, React Testing Library.

## Global Constraints

- Migration number: **check the actual highest-numbered file in `engine/migrations/versions/` before creating the migration.** The spec originally referenced 0020 and 0019_fiber_models, but other in-flight tasks may claim those numbers. Use `<next_number>_dry_run_artifact` and set `down_revision` to the actual latest revision ID in that directory. Do not guess — read the files.
- `DryRunArtifact.status` allowed values: `"pending"` | `"approved"` | `"pushed_back"`
- Approve sets `RunRecord.status = "queued"` (resumes the engine pickup loop).
- Push-back leaves `RunRecord.status` as `"dry_run_review"` (already set by engine).
- The GET endpoint returns 404 with code `"dry_run_artifact_not_found"` when no artifact exists for the given `(project_id, run_id)`.
- Approve and push-back return a `RunResponse` (the updated run record), not the artifact — this matches the gates pattern.
- Auth: GET = any project member (`get_current_user` + `require_project_access`); POST approve/push-back = `get_central_team_user`.
- Python test imports follow the module-level SQLite override pattern (copy the preamble from `tests/test_gates_api.py` — override `db_session.engine` and `db_session.SessionLocal` before importing `app`).
- Frontend API helpers go in `web/lib/runs-api.ts` (extend existing file, do not create a new module).
- Frontend test imports/mocks follow the pattern in `web/app/projects/[id]/codegen/page.test.tsx`.

## Objective

Add dry-run artifact storage, project-scoped review routes, and the dry-run review screen for approve and push-back actions.

## Out of Scope

- No codegen generation changes
- No new artifact lifecycle stages beyond the dry-run review states
- No unrelated gate or run UI updates

## File Changes

- See the blast radius table above for the exact backend and web files.

## Verification

- Run the new dry-run API tests
- Run the new review page tests
- Run the touched backend and web suites

## Pitfalls

- Keep approve/push-back actions idempotent where possible
- Enforce project access on every route
- Preserve the existing review-state model instead of inventing a new one

## Commit

- `feat(001ar): add dry run review flow`


---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `engine/src/migrations_engine/db/models.py` | Modify | Add `DryRunArtifact` model class |
| `engine/migrations/versions/<N>_dry_run_artifact.py` | Create | Alembic migration — create `dry_run_artifacts` table |
| `engine/src/migrations_engine/api/schemas.py` | Modify | Add `DryRunArtifactResponse`, `PushBackRequest` |
| `engine/src/migrations_engine/management/dry_run.py` | Create | Service: `get_dry_run_artifact`, `approve_dry_run`, `push_back_dry_run` |
| `engine/src/migrations_engine/routes/dry_run.py` | Create | 3 API routes wired to service functions |
| `engine/src/migrations_engine/app.py` | Modify | Import and include `dry_run_router` |
| `engine/tests/test_dry_run_api.py` | Create | Pytest tests for all 3 endpoints |
| `web/lib/runs-api.ts` | Modify | Add `DryRunArtifactRecord`, `getDryRunArtifact`, `approveDryRun`, `pushBackDryRun` |
| `web/lib/runs-api.test.ts` | Modify | Add describe blocks for the 3 new helpers |
| `web/app/projects/[id]/runs/[run_id]/dry-run/page.tsx` | Create | Dry-run review page component |
| `web/app/projects/[id]/runs/[run_id]/dry-run/page.test.tsx` | Create | Vitest + RTL tests for the page |

---

## Task 1: Backend — Model, Migration, Schemas, Service, Routes, Tests

**Files:**
- Modify: `engine/src/migrations_engine/db/models.py`
- Create: `engine/migrations/versions/<N>_dry_run_artifact.py`
- Modify: `engine/src/migrations_engine/api/schemas.py`
- Create: `engine/src/migrations_engine/management/dry_run.py`
- Create: `engine/src/migrations_engine/routes/dry_run.py`
- Modify: `engine/src/migrations_engine/app.py`
- Create: `engine/tests/test_dry_run_api.py`

**Interfaces:**
- Produces (for Task 2 / future engine work):
  - `DryRunArtifact` ORM model accessible as `from migrations_engine.db.models import DryRunArtifact`
  - `GET /projects/{project_id}/runs/{run_id}/dry-run` → `DryRunArtifactResponse`
  - `POST /projects/{project_id}/runs/{run_id}/dry-run/approve` → `RunResponse`
  - `POST /projects/{project_id}/runs/{run_id}/dry-run/push-back` → `RunResponse`

---

- [ ] **Step 1.1: Determine the correct migration number**

  Read the files in `engine/migrations/versions/` and identify the highest revision number (e.g. `0015_reconciliation_tables.py` → next is `0016`). The migration file you create must be `<N>_dry_run_artifact.py` where N is that next number zero-padded to four digits. The `down_revision` value must be the `revision` string from the current highest file (e.g. `"0015_reconciliation_tables"`). Do not proceed until you have confirmed both values.

- [ ] **Step 1.2: Write the failing model test**

  Create `engine/tests/test_dry_run_api.py`:

  ```python
  from __future__ import annotations

  import uuid

  import pytest
  from fastapi.testclient import TestClient
  from sqlalchemy import create_engine
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

  from migrations_engine.app import app  # noqa: E402
  from migrations_engine.auth.passwords import hash_password  # noqa: E402
  from migrations_engine.config import get_settings  # noqa: E402
  from migrations_engine.db.base import Base  # noqa: E402
  from migrations_engine.db.models import (  # noqa: E402
      DryRunArtifact,
      ProjectDefinition,
      ProjectRegistry,
      RunRecord,
      User,
  )
  from migrations_engine.db.session import SessionLocal  # noqa: E402
  from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE  # noqa: E402

  client = TestClient(app)


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
          db.add(
              User(
                  user_id=str(uuid.uuid4()),
                  email="stakeholder@example.com",
                  display_name="Stakeholder",
                  password_hash=hash_password("stakeholder-password"),
                  role=PROJECT_STAKEHOLDER_ROLE,
                  status="active",
              )
          )
          db.commit()


  @pytest.fixture(autouse=True)
  def _clear_settings_cache() -> None:
      get_settings.cache_clear()


  def _login(email: str, password: str) -> str:
      response = client.post("/auth/login", json={"email": email, "password": password})
      assert response.status_code == 200, response.text
      return response.json()["access_token"]


  @pytest.fixture
  def admin_token() -> str:
      settings = get_settings()
      if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
          pytest.skip("bootstrap credentials not configured")
      return _login(settings.bootstrap_admin_email, settings.bootstrap_admin_password)


  @pytest.fixture
  def stakeholder_token() -> str:
      return _login("stakeholder@example.com", "stakeholder-password")


  def _seed_dry_run_state() -> tuple[str, str]:
      """Create a project + run + DryRunArtifact, return (project_id, run_id)."""
      project_id = str(uuid.uuid4())
      definition_id = str(uuid.uuid4())
      run_id = str(uuid.uuid4())
      artifact_id = str(uuid.uuid4())

      with SessionLocal() as db:
          db.add(
              ProjectDefinition(
                  definition_id=definition_id,
                  project_id=project_id,
                  name="DryRun Project",
                  status="active",
              )
          )
          db.add(
              ProjectRegistry(
                  project_id=project_id,
                  name="DryRun Project",
                  definition_id=definition_id,
                  status="active",
              )
          )
          db.add(
              RunRecord(
                  run_id=run_id,
                  project_id=project_id,
                  destination_object_name="customers",
                  status="dry_run_review",
                  approvals=[],
              )
          )
          db.add(
              DryRunArtifact(
                  dry_run_artifact_id=artifact_id,
                  run_id=run_id,
                  project_id=project_id,
                  destination_object_name="customers",
                  success_count=1840,
                  failure_count=2,
                  field_coverage_pct=94.3,
                  pii_fields=[{"field": "SURNAME", "token": "EMAIL_XXXX"}],
                  sample_rows=[{"source": {"CUST_ID": "100042"}, "mapped": {"customer_id": "100042"}}],
                  failures=[{"row_index": 141, "reason": "unmapped_lookup", "field": "ACCT_TYPE", "value": "RETD"}],
                  push_back_comment=None,
                  status="pending",
              )
          )
          db.commit()

      return project_id, run_id


  def test_get_dry_run_artifact(admin_token: str) -> None:
      project_id, run_id = _seed_dry_run_state()

      response = client.get(
          f"/projects/{project_id}/runs/{run_id}/dry-run",
          headers={"Authorization": f"Bearer {admin_token}"},
      )
      assert response.status_code == 200, response.text
      body = response.json()
      assert body["destination_object_name"] == "customers"
      assert body["success_count"] == 1840
      assert body["failure_count"] == 2
      assert abs(body["field_coverage_pct"] - 94.3) < 0.01
      assert body["pii_fields"] == [{"field": "SURNAME", "token": "EMAIL_XXXX"}]
      assert len(body["sample_rows"]) == 1
      assert body["failures"][0]["row_index"] == 141
      assert body["status"] == "pending"
      assert body["push_back_comment"] is None


  def test_get_dry_run_artifact_404_when_none(admin_token: str) -> None:
      project_id = str(uuid.uuid4())
      definition_id = str(uuid.uuid4())
      run_id = str(uuid.uuid4())
      with SessionLocal() as db:
          db.add(ProjectDefinition(definition_id=definition_id, project_id=project_id, name="NoDR", status="active"))
          db.add(ProjectRegistry(project_id=project_id, name="NoDR", definition_id=definition_id, status="active"))
          db.add(RunRecord(run_id=run_id, project_id=project_id, destination_object_name="x", status="queued", approvals=[]))
          db.commit()

      response = client.get(
          f"/projects/{project_id}/runs/{run_id}/dry-run",
          headers={"Authorization": f"Bearer {admin_token}"},
      )
      assert response.status_code == 404
      assert response.json()["error"]["code"] == "dry_run_artifact_not_found"


  def test_approve_dry_run(admin_token: str) -> None:
      project_id, run_id = _seed_dry_run_state()

      response = client.post(
          f"/projects/{project_id}/runs/{run_id}/dry-run/approve",
          headers={"Authorization": f"Bearer {admin_token}"},
      )
      assert response.status_code == 200, response.text
      body = response.json()
      # Returns RunResponse
      assert body["run_id"] == run_id
      assert body["status"] == "queued"

      with SessionLocal() as db:
          artifact = db.scalar(
              __import__("sqlalchemy", fromlist=["select"]).select(DryRunArtifact).where(
                  DryRunArtifact.run_id == run_id
              )
          )
          assert artifact is not None
          assert artifact.status == "approved"


  def test_push_back_dry_run(admin_token: str) -> None:
      project_id, run_id = _seed_dry_run_state()

      response = client.post(
          f"/projects/{project_id}/runs/{run_id}/dry-run/push-back",
          headers={"Authorization": f"Bearer {admin_token}"},
          json={"comment": "Row 142 maps RETD to wrong destination."},
      )
      assert response.status_code == 200, response.text
      body = response.json()
      # Returns RunResponse; run status stays dry_run_review
      assert body["run_id"] == run_id
      assert body["status"] == "dry_run_review"

      with SessionLocal() as db:
          artifact = db.scalar(
              __import__("sqlalchemy", fromlist=["select"]).select(DryRunArtifact).where(
                  DryRunArtifact.run_id == run_id
              )
          )
          assert artifact is not None
          assert artifact.status == "pushed_back"
          assert artifact.push_back_comment == "Row 142 maps RETD to wrong destination."


  def test_approve_requires_central_team(stakeholder_token: str) -> None:
      project_id, run_id = _seed_dry_run_state()

      response = client.post(
          f"/projects/{project_id}/runs/{run_id}/dry-run/approve",
          headers={"Authorization": f"Bearer {stakeholder_token}"},
      )
      assert response.status_code == 403


  def test_push_back_requires_central_team(stakeholder_token: str) -> None:
      project_id, run_id = _seed_dry_run_state()

      response = client.post(
          f"/projects/{project_id}/runs/{run_id}/dry-run/push-back",
          headers={"Authorization": f"Bearer {stakeholder_token}"},
          json={"comment": "Fix this."},
      )
      assert response.status_code == 403


  def test_get_requires_project_access(admin_token: str) -> None:
      # A project with no membership — stakeholder cannot access
      project_id = str(uuid.uuid4())
      definition_id = str(uuid.uuid4())
      run_id = str(uuid.uuid4())
      with SessionLocal() as db:
          db.add(ProjectDefinition(definition_id=definition_id, project_id=project_id, name="Private", status="active"))
          db.add(ProjectRegistry(project_id=project_id, name="Private", definition_id=definition_id, status="active"))
          db.add(RunRecord(run_id=run_id, project_id=project_id, destination_object_name="x", status="dry_run_review", approvals=[]))
          db.commit()

      stakeholder_tok = _login("stakeholder@example.com", "stakeholder-password")
      response = client.get(
          f"/projects/{project_id}/runs/{run_id}/dry-run",
          headers={"Authorization": f"Bearer {stakeholder_tok}"},
      )
      assert response.status_code == 403
  ```

- [ ] **Step 1.3: Run the failing test to confirm ImportError on DryRunArtifact**

  ```bash
  cd /Users/vjkotra/projects/katana/engine
  python -m pytest tests/test_dry_run_api.py -v 2>&1 | head -30
  ```

  Expected: `ImportError` or `cannot import name 'DryRunArtifact'`.

- [ ] **Step 1.4: Add the DryRunArtifact model to models.py**

  In `engine/src/migrations_engine/db/models.py`, add after the `ReconciliationLineageRow` class (before `CodeGenerationArtifact`):

  ```python
  class DryRunArtifact(Base):
      __tablename__ = "dry_run_artifacts"

      dry_run_artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
      run_id: Mapped[str] = mapped_column(String(36), ForeignKey("run_records.run_id"), nullable=False, index=True)
      project_id: Mapped[str] = mapped_column(
          String(36), ForeignKey("project_registry.project_id"), nullable=False
      )
      destination_object_name: Mapped[str] = mapped_column(String(255), nullable=False)
      success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
      failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
      field_coverage_pct: Mapped[float | None] = mapped_column(nullable=True)
      pii_fields: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
      sample_rows: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
      failures: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
      push_back_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
      status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
      created_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True), nullable=False, server_default=func.now()
      )
  ```

  Note: `Float` is already importable from SQLAlchemy because the existing imports include generic types. If a `Float` column type is needed explicitly, add `Float` to the existing `from sqlalchemy import ...` line. The `Mapped[float | None]` annotation without an explicit column type will use SQLAlchemy's default float column — verify this works in the test run; if not, use `mapped_column(sa.Float(), nullable=True)` explicitly.

- [ ] **Step 1.5: Create the Alembic migration**

  Substitute `<N>` and `<PREV_REVISION_ID>` with the values determined in Step 1.1.

  Create `engine/migrations/versions/<N>_dry_run_artifact.py`:

  ```python
  """add dry_run_artifacts table

  Revision ID: <N>_dry_run_artifact
  Revises: <PREV_REVISION_ID>
  Create Date: 2026-07-01
  """

  from __future__ import annotations

  from alembic import op
  import sqlalchemy as sa


  revision = "<N>_dry_run_artifact"
  down_revision = "<PREV_REVISION_ID>"
  branch_labels = None
  depends_on = None


  def upgrade() -> None:
      op.create_table(
          "dry_run_artifacts",
          sa.Column("dry_run_artifact_id", sa.String(36), primary_key=True),
          sa.Column("run_id", sa.String(36), sa.ForeignKey("run_records.run_id"), nullable=False),
          sa.Column("project_id", sa.String(36), sa.ForeignKey("project_registry.project_id"), nullable=False),
          sa.Column("destination_object_name", sa.String(255), nullable=False),
          sa.Column("success_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
          sa.Column("failure_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
          sa.Column("field_coverage_pct", sa.Float(), nullable=True),
          sa.Column("pii_fields", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
          sa.Column("sample_rows", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
          sa.Column("failures", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
          sa.Column("push_back_comment", sa.Text(), nullable=True),
          sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'pending'")),
          sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
      )
      op.create_index("ix_dry_run_artifacts_run_id", "dry_run_artifacts", ["run_id"])


  def downgrade() -> None:
      op.drop_index("ix_dry_run_artifacts_run_id", table_name="dry_run_artifacts")
      op.drop_table("dry_run_artifacts")
  ```

- [ ] **Step 1.6: Add DryRunArtifactResponse and PushBackRequest schemas to schemas.py**

  In `engine/src/migrations_engine/api/schemas.py`, add at the end of the file:

  ```python
  class DryRunArtifactResponse(BaseModel):
      dry_run_artifact_id: str
      run_id: str
      project_id: str
      destination_object_name: str
      success_count: int
      failure_count: int
      field_coverage_pct: float | None
      pii_fields: list[dict[str, Any]]
      sample_rows: list[dict[str, Any]]
      failures: list[dict[str, Any]]
      push_back_comment: str | None
      status: str
      created_at: datetime


  class PushBackRequest(BaseModel):
      comment: str = Field(min_length=1, max_length=2000)
  ```

- [ ] **Step 1.7: Create the service module**

  Create `engine/src/migrations_engine/management/dry_run.py`:

  ```python
  from __future__ import annotations

  from sqlalchemy import select
  from sqlalchemy.orm import Session

  from ..api.deps import AuthApiError
  from ..api.schemas import DryRunArtifactResponse, PushBackRequest, RunResponse
  from ..db.models import DryRunArtifact, RunRecord
  from ..management.platform import record_management_audit


  def _get_run_or_404(db: Session, *, project_id: str, run_id: str) -> RunRecord:
      run = db.scalar(
          select(RunRecord).where(
              RunRecord.run_id == run_id,
              RunRecord.project_id == project_id,
          )
      )
      if run is None:
          raise AuthApiError("run_not_found", "Run not found.", 404)
      return run


  def _get_artifact_or_404(db: Session, *, project_id: str, run_id: str) -> DryRunArtifact:
      artifact = db.scalar(
          select(DryRunArtifact).where(
              DryRunArtifact.run_id == run_id,
              DryRunArtifact.project_id == project_id,
          )
      )
      if artifact is None:
          raise AuthApiError("dry_run_artifact_not_found", "No dry-run artifact found for this run.", 404)
      return artifact


  def get_dry_run_artifact(db: Session, *, project_id: str, run_id: str) -> DryRunArtifactResponse:
      _get_run_or_404(db, project_id=project_id, run_id=run_id)
      artifact = _get_artifact_or_404(db, project_id=project_id, run_id=run_id)
      return DryRunArtifactResponse(
          dry_run_artifact_id=artifact.dry_run_artifact_id,
          run_id=artifact.run_id,
          project_id=artifact.project_id,
          destination_object_name=artifact.destination_object_name,
          success_count=artifact.success_count,
          failure_count=artifact.failure_count,
          field_coverage_pct=artifact.field_coverage_pct,
          pii_fields=artifact.pii_fields,
          sample_rows=artifact.sample_rows,
          failures=artifact.failures,
          push_back_comment=artifact.push_back_comment,
          status=artifact.status,
          created_at=artifact.created_at,
      )


  def _run_to_response(run: RunRecord) -> RunResponse:
      return RunResponse(
          run_id=run.run_id,
          project_id=run.project_id,
          destination_object_name=run.destination_object_name,
          source_definition_reference=run.source_definition_reference,
          environment=run.environment,
          status=run.status,
          current_stage=run.current_stage,
          source_slice_version=run.source_slice_version,
          mapping_snapshot_version=run.mapping_snapshot_version,
          lookup_snapshot_version=run.lookup_snapshot_version,
          lookup_snapshot_versions=run.lookup_snapshot_versions,
          code_generation_input_snapshot_version=run.code_generation_input_snapshot_version,
          codegen_artifact_id=run.codegen_artifact_id,
          knowledge_freeze_version=run.knowledge_freeze_version,
          start_metadata=run.start_metadata,
          pause_metadata=run.pause_metadata,
          resume_metadata=run.resume_metadata,
          completion_metadata=run.completion_metadata,
          started_at=None,
          last_checkpoint_at=None,
          created_at=run.created_at,
          updated_at=run.updated_at,
      )


  def approve_dry_run(
      db: Session,
      *,
      project_id: str,
      run_id: str,
      actor_user_id: str,
  ) -> RunResponse:
      run = _get_run_or_404(db, project_id=project_id, run_id=run_id)
      artifact = _get_artifact_or_404(db, project_id=project_id, run_id=run_id)

      artifact.status = "approved"
      run.status = "queued"

      record_management_audit(
          db,
          project_id=project_id,
          actor_user_id=actor_user_id,
          event_type="dry_run_approved",
          payload={"run_id": run_id, "dry_run_artifact_id": artifact.dry_run_artifact_id},
      )
      db.commit()
      db.refresh(run)
      return _run_to_response(run)


  def push_back_dry_run(
      db: Session,
      *,
      project_id: str,
      run_id: str,
      actor_user_id: str,
      body: PushBackRequest,
  ) -> RunResponse:
      run = _get_run_or_404(db, project_id=project_id, run_id=run_id)
      artifact = _get_artifact_or_404(db, project_id=project_id, run_id=run_id)

      artifact.status = "pushed_back"
      artifact.push_back_comment = body.comment
      # run.status stays "dry_run_review" — do not change it

      record_management_audit(
          db,
          project_id=project_id,
          actor_user_id=actor_user_id,
          event_type="dry_run_pushed_back",
          payload={
              "run_id": run_id,
              "dry_run_artifact_id": artifact.dry_run_artifact_id,
              "comment": body.comment,
          },
      )
      db.commit()
      db.refresh(run)
      return _run_to_response(run)
  ```

- [ ] **Step 1.8: Create the routes module**

  Create `engine/src/migrations_engine/routes/dry_run.py`:

  ```python
  from __future__ import annotations

  from fastapi import APIRouter, Depends
  from sqlalchemy.orm import Session

  from ..api.deps import get_central_team_user, get_current_user, get_db
  from ..api.schemas import DryRunArtifactResponse, PushBackRequest, RunResponse
  from ..db.models import User
  from ..management.access import require_project_access
  from ..management.dry_run import approve_dry_run, get_dry_run_artifact, push_back_dry_run

  router = APIRouter(prefix="/projects/{project_id}/runs/{run_id}/dry-run", tags=["dry-run"])


  @router.get("", response_model=DryRunArtifactResponse)
  def read_dry_run_artifact(
      project_id: str,
      run_id: str,
      actor: User = Depends(get_current_user),
      db: Session = Depends(get_db),
  ) -> DryRunArtifactResponse:
      require_project_access(db, user=actor, project_id=project_id)
      return get_dry_run_artifact(db, project_id=project_id, run_id=run_id)


  @router.post("/approve", response_model=RunResponse)
  def post_approve_dry_run(
      project_id: str,
      run_id: str,
      actor: User = Depends(get_central_team_user),
      db: Session = Depends(get_db),
  ) -> RunResponse:
      return approve_dry_run(db, project_id=project_id, run_id=run_id, actor_user_id=actor.user_id)


  @router.post("/push-back", response_model=RunResponse)
  def post_push_back_dry_run(
      project_id: str,
      run_id: str,
      body: PushBackRequest,
      actor: User = Depends(get_central_team_user),
      db: Session = Depends(get_db),
  ) -> RunResponse:
      return push_back_dry_run(
          db,
          project_id=project_id,
          run_id=run_id,
          actor_user_id=actor.user_id,
          body=body,
      )
  ```

- [ ] **Step 1.9: Register the router in app.py**

  In `engine/src/migrations_engine/app.py`, add the import alongside the other router imports:

  ```python
  from .routes.dry_run import router as dry_run_router
  ```

  Then add the `include_router` call after the existing ones (e.g., after `slice_approval_router`):

  ```python
  app.include_router(dry_run_router)
  ```

- [ ] **Step 1.10: Run all the dry-run tests and confirm they pass**

  ```bash
  cd /Users/vjkotra/projects/katana/engine
  python -m pytest tests/test_dry_run_api.py -v
  ```

  Expected: all 8 tests PASS.

- [ ] **Step 1.11: Run the full backend test suite to confirm no regressions**

  ```bash
  cd /Users/vjkotra/projects/katana/engine
  python -m pytest tests/ -v 2>&1 | tail -20
  ```

  Expected: no new failures.

- [ ] **Step 1.12: Commit**

  ```bash
  git add \
    engine/src/migrations_engine/db/models.py \
    engine/migrations/versions/ \
    engine/src/migrations_engine/api/schemas.py \
    engine/src/migrations_engine/management/dry_run.py \
    engine/src/migrations_engine/routes/dry_run.py \
    engine/src/migrations_engine/app.py \
    engine/tests/test_dry_run_api.py
  git commit -m "feat(001ar): add DryRunArtifact model, migration, and 3 dry-run API endpoints"
  ```

---

## Task 2: Frontend API Helpers

**Files:**
- Modify: `web/lib/runs-api.ts`
- Modify: `web/lib/runs-api.test.ts`

**Interfaces:**
- Consumes: Task 1's endpoints at `/projects/{project_id}/runs/{run_id}/dry-run` (GET, POST /approve, POST /push-back)
- Produces (for Task 3):
  - `DryRunArtifactRecord` interface
  - `getDryRunArtifact(token, projectId, runId): Promise<DryRunArtifactRecord>`
  - `approveDryRun(token, projectId, runId): Promise<RunRecord>`
  - `pushBackDryRun(token, projectId, runId, comment): Promise<RunRecord>`

---

- [ ] **Step 2.1: Write the failing tests for the new helpers**

  In `web/lib/runs-api.test.ts`, add the following after the existing `describe("listCheckpoints", ...)` block:

  ```typescript
  const DRY_RUN_ARTIFACT_RESPONSE = {
    dry_run_artifact_id: "dra-1",
    run_id: RUN_ID,
    project_id: PROJECT_ID,
    destination_object_name: "customers",
    success_count: 1840,
    failure_count: 2,
    field_coverage_pct: 94.3,
    pii_fields: [{ field: "SURNAME", token: "EMAIL_XXXX" }],
    sample_rows: [{ source: { CUST_ID: "100042" }, mapped: { customer_id: "100042" } }],
    failures: [{ row_index: 141, reason: "unmapped_lookup", field: "ACCT_TYPE", value: "RETD" }],
    push_back_comment: null,
    status: "pending",
    created_at: "2026-07-01T00:00:00Z",
  };

  describe("getDryRunArtifact", () => {
    it("GETs /projects/{id}/runs/{run_id}/dry-run", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => DRY_RUN_ARTIFACT_RESPONSE,
      });
      vi.stubGlobal("fetch", fetchMock);

      const result = await getDryRunArtifact(TOKEN, PROJECT_ID, RUN_ID);

      expect(fetchMock).toHaveBeenCalledWith(
        `${BASE}/projects/${PROJECT_ID}/runs/${RUN_ID}/dry-run`,
        expect.objectContaining({
          method: "GET",
          headers: expect.objectContaining({ Authorization: `Bearer ${TOKEN}` }),
        }),
      );
      expect(result.dryRunArtifactId).toBe("dra-1");
      expect(result.successCount).toBe(1840);
      expect(result.failureCount).toBe(2);
      expect(result.fieldCoveragePct).toBeCloseTo(94.3);
      expect(result.piiFields).toEqual([{ field: "SURNAME", token: "EMAIL_XXXX" }]);
      expect(result.sampleRows).toHaveLength(1);
      expect(result.failures[0]).toMatchObject({ rowIndex: 141, reason: "unmapped_lookup" });
      expect(result.status).toBe("pending");
      expect(result.pushBackComment).toBeNull();
    });

    it("throws RunApiError on 404", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ error: { code: "dry_run_artifact_not_found", message: "Not found." } }),
      });
      vi.stubGlobal("fetch", fetchMock);

      await expect(getDryRunArtifact(TOKEN, PROJECT_ID, RUN_ID)).rejects.toMatchObject({
        code: "dry_run_artifact_not_found",
        status: 404,
      });
    });
  });

  describe("approveDryRun", () => {
    it("POSTs to /dry-run/approve and returns RunRecord", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ ...stub, status: "queued" }),
      });
      vi.stubGlobal("fetch", fetchMock);

      const result = await approveDryRun(TOKEN, PROJECT_ID, RUN_ID);

      expect(fetchMock).toHaveBeenCalledWith(
        `${BASE}/projects/${PROJECT_ID}/runs/${RUN_ID}/dry-run/approve`,
        expect.objectContaining({ method: "POST" }),
      );
      expect(result.status).toBe("queued");
    });
  });

  describe("pushBackDryRun", () => {
    it("POSTs to /dry-run/push-back with comment body", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ ...stub, status: "dry_run_review" }),
      });
      vi.stubGlobal("fetch", fetchMock);

      const result = await pushBackDryRun(TOKEN, PROJECT_ID, RUN_ID, "Row 142 is wrong.");

      expect(fetchMock).toHaveBeenCalledWith(
        `${BASE}/projects/${PROJECT_ID}/runs/${RUN_ID}/dry-run/push-back`,
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({ Authorization: `Bearer ${TOKEN}` }),
        }),
      );
      const body = JSON.parse(String((fetchMock.mock.calls[0] as unknown[][])[0]?.[1]?.body ?? "{}")) as { comment: string };
      expect(body.comment).toBe("Row 142 is wrong.");
      expect(result.status).toBe("dry_run_review");
    });
  });
  ```

  Also add the new exports to the import line at the top of the test file:

  ```typescript
  import {
    approveDryRun,
    createRun,
    getDryRunArtifact,
    getRun,
    launchRun,
    listCheckpoints,
    listRuns,
    pushBackDryRun,
    resumeRun,
    type DryRunArtifactRecord,
    type RunCheckpoint,
    type RunRecord,
  } from "./runs-api";
  ```

- [ ] **Step 2.2: Run the failing tests**

  ```bash
  cd /Users/vjkotra/projects/katana/web
  npm test -- runs-api 2>&1 | tail -20
  ```

  Expected: failures like `getDryRunArtifact is not a function`.

- [ ] **Step 2.3: Add the types and functions to runs-api.ts**

  In `web/lib/runs-api.ts`, add the following after the existing `RunStatus` type and `RunRecord` interface:

  ```typescript
  export interface DryRunFailure {
    rowIndex: number;
    reason: string;
    field: string;
    value: string;
  }

  export interface DryRunSampleRow {
    source: Record<string, unknown>;
    mapped: Record<string, unknown>;
  }

  export interface DryRunPiiField {
    field: string;
    token: string;
  }

  export interface DryRunArtifactRecord {
    dryRunArtifactId: string;
    runId: string;
    projectId: string;
    destinationObjectName: string;
    successCount: number;
    failureCount: number;
    fieldCoveragePct: number | null;
    piiFields: DryRunPiiField[];
    sampleRows: DryRunSampleRow[];
    failures: DryRunFailure[];
    pushBackComment: string | null;
    status: "pending" | "approved" | "pushed_back";
    createdAt: string;
  }
  ```

  Then add these three functions at the end of the file (after `listCheckpoints`):

  ```typescript
  function mapDryRunFailure(raw: {
    row_index: number;
    reason: string;
    field: string;
    value: string;
  }): DryRunFailure {
    return {
      rowIndex: raw.row_index,
      reason: raw.reason,
      field: raw.field,
      value: raw.value,
    };
  }

  function mapDryRunArtifact(raw: {
    dry_run_artifact_id: string;
    run_id: string;
    project_id: string;
    destination_object_name: string;
    success_count: number;
    failure_count: number;
    field_coverage_pct: number | null;
    pii_fields: DryRunPiiField[];
    sample_rows: DryRunSampleRow[];
    failures: Array<{ row_index: number; reason: string; field: string; value: string }>;
    push_back_comment: string | null;
    status: "pending" | "approved" | "pushed_back";
    created_at: string;
  }): DryRunArtifactRecord {
    return {
      dryRunArtifactId: raw.dry_run_artifact_id,
      runId: raw.run_id,
      projectId: raw.project_id,
      destinationObjectName: raw.destination_object_name,
      successCount: raw.success_count,
      failureCount: raw.failure_count,
      fieldCoveragePct: raw.field_coverage_pct,
      piiFields: raw.pii_fields,
      sampleRows: raw.sample_rows,
      failures: raw.failures.map(mapDryRunFailure),
      pushBackComment: raw.push_back_comment,
      status: raw.status,
      createdAt: raw.created_at,
    };
  }

  export async function getDryRunArtifact(
    token: string,
    projectId: string,
    runId: string,
  ): Promise<DryRunArtifactRecord> {
    const response = await requestJson<Parameters<typeof mapDryRunArtifact>[0]>(
      `/projects/${projectId}/runs/${runId}/dry-run`,
      { method: "GET", token },
    );
    return mapDryRunArtifact(response);
  }

  export async function approveDryRun(
    token: string,
    projectId: string,
    runId: string,
  ): Promise<RunRecord> {
    const response = await requestJson<Parameters<typeof mapRunRecord>[0]>(
      `/projects/${projectId}/runs/${runId}/dry-run/approve`,
      { method: "POST", token },
    );
    return mapRunRecord(response);
  }

  export async function pushBackDryRun(
    token: string,
    projectId: string,
    runId: string,
    comment: string,
  ): Promise<RunRecord> {
    const response = await requestJson<Parameters<typeof mapRunRecord>[0]>(
      `/projects/${projectId}/runs/${runId}/dry-run/push-back`,
      {
        method: "POST",
        token,
        body: JSON.stringify({ comment }),
      },
    );
    return mapRunRecord(response);
  }
  ```

  Also update `RunStatus` to include `"dry_run_review"`:

  ```typescript
  export type RunStatus = "queued" | "running" | "paused" | "completed" | "failed" | "awaiting_approval" | "dry_run_review";
  ```

- [ ] **Step 2.4: Run the tests and confirm they pass**

  ```bash
  cd /Users/vjkotra/projects/katana/web
  npm test -- runs-api 2>&1 | tail -20
  ```

  Expected: all tests PASS (including the 3 new describe blocks).

- [ ] **Step 2.5: Run the full frontend test suite to confirm no regressions**

  ```bash
  cd /Users/vjkotra/projects/katana/web
  npm test 2>&1 | tail -10
  ```

  Expected: no new failures.

- [ ] **Step 2.6: Commit**

  ```bash
  git add web/lib/runs-api.ts web/lib/runs-api.test.ts
  git commit -m "feat(001ar): add getDryRunArtifact, approveDryRun, pushBackDryRun helpers to runs-api"
  ```

---

## Task 3: Dry-Run Review Page

**Files:**
- Create: `web/app/projects/[id]/runs/[run_id]/dry-run/page.tsx`
- Create: `web/app/projects/[id]/runs/[run_id]/dry-run/page.test.tsx`

**Interfaces:**
- Consumes (from Task 2):
  - `getDryRunArtifact(token, projectId, runId): Promise<DryRunArtifactRecord>`
  - `approveDryRun(token, projectId, runId): Promise<RunRecord>`
  - `pushBackDryRun(token, projectId, runId, comment): Promise<RunRecord>`
  - `DryRunArtifactRecord`
- Consumes:
  - `loadUiSession()` from `web/lib/session`
  - `useRouter()` from `next/navigation` — for redirect after action
  - `useParams()` from `next/navigation` — to read `id` and `run_id`
  - `Topbar` from `web/components/Topbar`

---

- [ ] **Step 3.1: Write the failing page tests**

  Create `web/app/projects/[id]/runs/[run_id]/dry-run/page.test.tsx`:

  ```tsx
  import { fireEvent, render, screen, waitFor } from "@testing-library/react";
  import { beforeEach, describe, expect, it, vi } from "vitest";
  import DryRunPage from "./page";

  const {
    loadUiSessionMock,
    getDryRunArtifactMock,
    approveDryRunMock,
    pushBackDryRunMock,
    pushMock,
  } = vi.hoisted(() => ({
    loadUiSessionMock: vi.fn(),
    getDryRunArtifactMock: vi.fn(),
    approveDryRunMock: vi.fn(),
    pushBackDryRunMock: vi.fn(),
    pushMock: vi.fn(),
  }));

  vi.mock("../../../../../components/Topbar", () => ({
    Topbar: () => <div>Topbar</div>,
  }));

  vi.mock("../../../../../lib/session", () => ({
    loadUiSession: loadUiSessionMock,
  }));

  vi.mock("../../../../../lib/runs-api", () => ({
    getDryRunArtifact: getDryRunArtifactMock,
    approveDryRun: approveDryRunMock,
    pushBackDryRun: pushBackDryRunMock,
  }));

  vi.mock("next/navigation", () => ({
    useParams: () => ({ id: "project-1", run_id: "run-1" }),
    useRouter: () => ({ push: pushMock }),
  }));

  const SESSION = {
    accessToken: "token-1",
    expiresAt: "2026-07-02T12:00:00Z",
    role: "central_team" as const,
    sessionVersion: 1,
    userId: "user-1",
  };

  const ARTIFACT = {
    dryRunArtifactId: "dra-1",
    runId: "run-1",
    projectId: "project-1",
    destinationObjectName: "customers",
    successCount: 1840,
    failureCount: 2,
    fieldCoveragePct: 94.3,
    piiFields: [{ field: "SURNAME", token: "EMAIL_XXXX" }],
    sampleRows: [
      {
        source: { CUST_ID: "100042", SURNAME: "EMAIL_XXXX" },
        mapped: { customer_id: "100042", last_name: "EMAIL_XXXX" },
      },
    ],
    failures: [
      { rowIndex: 141, reason: "unmapped_lookup", field: "ACCT_TYPE", value: "RETD" },
    ],
    pushBackComment: null,
    status: "pending" as const,
    createdAt: "2026-07-01T10:00:00Z",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    loadUiSessionMock.mockReturnValue(SESSION);
    getDryRunArtifactMock.mockResolvedValue(ARTIFACT);
    approveDryRunMock.mockResolvedValue({
      run_id: "run-1",
      project_id: "project-1",
      status: "queued",
    });
    pushBackDryRunMock.mockResolvedValue({
      run_id: "run-1",
      project_id: "project-1",
      status: "dry_run_review",
    });
  });

  describe("DryRunPage", () => {
    it("renders the summary panel with counts and coverage", async () => {
      render(<DryRunPage />);

      expect(await screen.findByText("1,840")).toBeInTheDocument();
      expect(screen.getByText("2")).toBeInTheDocument();
      expect(screen.getByText(/94\.3/)).toBeInTheDocument();
    });

    it("renders the PII masking status panel", async () => {
      render(<DryRunPage />);

      expect(await screen.findByText("SURNAME")).toBeInTheDocument();
      expect(screen.getByText("EMAIL_XXXX")).toBeInTheDocument();
    });

    it("renders sample rows table with source and mapped values", async () => {
      render(<DryRunPage />);

      expect(await screen.findByText("100042")).toBeInTheDocument();
    });

    it("renders the failures list", async () => {
      render(<DryRunPage />);

      expect(await screen.findByText(/Row 141/i)).toBeInTheDocument();
      expect(screen.getByText("unmapped_lookup")).toBeInTheDocument();
      expect(screen.getByText("ACCT_TYPE")).toBeInTheDocument();
      expect(screen.getByText("RETD")).toBeInTheDocument();
    });

    it("approves and redirects to project overview", async () => {
      render(<DryRunPage />);

      const approveButton = await screen.findByRole("button", { name: /approve/i });
      fireEvent.click(approveButton);

      await waitFor(() => {
        expect(approveDryRunMock).toHaveBeenCalledWith("token-1", "project-1", "run-1");
      });
      expect(pushMock).toHaveBeenCalledWith("/projects/project-1");
    });

    it("submits push-back comment and redirects to project overview", async () => {
      render(<DryRunPage />);

      await screen.findByRole("button", { name: /approve/i });

      const textarea = screen.getByPlaceholderText(/explain what needs to change/i);
      fireEvent.change(textarea, { target: { value: "Row 142 maps RETD to wrong destination." } });
      fireEvent.click(screen.getByRole("button", { name: /push back/i }));

      await waitFor(() => {
        expect(pushBackDryRunMock).toHaveBeenCalledWith(
          "token-1",
          "project-1",
          "run-1",
          "Row 142 maps RETD to wrong destination.",
        );
      });
      expect(pushMock).toHaveBeenCalledWith("/projects/project-1");
    });

    it("disables push-back button when comment is empty", async () => {
      render(<DryRunPage />);

      await screen.findByRole("button", { name: /approve/i });
      const pushBackButton = screen.getByRole("button", { name: /push back/i });
      expect(pushBackButton).toBeDisabled();
    });

    it("shows error when approve fails", async () => {
      approveDryRunMock.mockRejectedValue(new Error("Network error"));
      render(<DryRunPage />);

      const approveButton = await screen.findByRole("button", { name: /approve/i });
      fireEvent.click(approveButton);

      expect(await screen.findByRole("alert")).toBeInTheDocument();
    });

    it("shows loading state before artifact loads", async () => {
      getDryRunArtifactMock.mockImplementation(
        () => new Promise<never>(() => undefined),
      );
      render(<DryRunPage />);

      expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });
  });
  ```

- [ ] **Step 3.2: Run the failing tests**

  ```bash
  cd /Users/vjkotra/projects/katana/web
  npm test -- dry-run/page 2>&1 | tail -20
  ```

  Expected: test collection error — module not found for `./page`.

- [ ] **Step 3.3: Create the dry-run review page**

  First, ensure the directory exists:
  ```
  web/app/projects/[id]/runs/[run_id]/dry-run/
  ```

  Create `web/app/projects/[id]/runs/[run_id]/dry-run/page.tsx`:

  ```tsx
  "use client";

  import { useEffect, useState } from "react";
  import { useParams, useRouter } from "next/navigation";
  import { Topbar } from "../../../../../components/Topbar";
  import {
    approveDryRun,
    getDryRunArtifact,
    pushBackDryRun,
    type DryRunArtifactRecord,
  } from "../../../../../lib/runs-api";
  import { loadUiSession, type SessionRole, type UiSession } from "../../../../../lib/session";

  function formatCount(n: number): string {
    return new Intl.NumberFormat("en-US").format(n);
  }

  function formatPct(pct: number | null): string {
    if (pct === null) {
      return "—";
    }
    return `${pct.toFixed(1)}%`;
  }

  export default function DryRunPage() {
    const router = useRouter();
    const params = useParams<{ id: string; run_id: string }>();
    const projectId = params.id;
    const runId = params.run_id;

    const [session, setSession] = useState<UiSession | null>(null);
    const [artifact, setArtifact] = useState<DryRunArtifactRecord | null>(null);
    const [loading, setLoading] = useState(true);
    const [pageError, setPageError] = useState<string | null>(null);
    const [actionLoading, setActionLoading] = useState(false);
    const [pushBackComment, setPushBackComment] = useState("");

    const role: SessionRole = session?.role ?? "read_only_auditor";

    useEffect(() => {
      setSession(loadUiSession());
    }, []);

    useEffect(() => {
      if (!session) {
        return;
      }

      let active = true;
      setLoading(true);
      setPageError(null);

      void getDryRunArtifact(session.accessToken, projectId, runId)
        .then((result) => {
          if (active) {
            setArtifact(result);
          }
        })
        .catch((error: unknown) => {
          if (active) {
            setPageError(error instanceof Error ? error.message : "Unable to load dry-run results.");
          }
        })
        .finally(() => {
          if (active) {
            setLoading(false);
          }
        });

      return () => {
        active = false;
      };
    }, [session, projectId, runId]);

    const handleApprove = async (): Promise<void> => {
      if (!session) {
        return;
      }
      setActionLoading(true);
      setPageError(null);
      try {
        await approveDryRun(session.accessToken, projectId, runId);
        router.push(`/projects/${projectId}`);
      } catch (error: unknown) {
        setPageError(error instanceof Error ? error.message : "Approve failed.");
        setActionLoading(false);
      }
    };

    const handlePushBack = async (): Promise<void> => {
      if (!session || !pushBackComment.trim()) {
        return;
      }
      setActionLoading(true);
      setPageError(null);
      try {
        await pushBackDryRun(session.accessToken, projectId, runId, pushBackComment.trim());
        router.push(`/projects/${projectId}`);
      } catch (error: unknown) {
        setPageError(error instanceof Error ? error.message : "Push-back failed.");
        setActionLoading(false);
      }
    };

    return (
      <main className="flex min-h-screen flex-col bg-surface text-slate-800">
        <Topbar role={role} />
        <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-6">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Dry-Run Review</p>
            <h1 className="text-3xl font-semibold text-slate-900">Dry-run results</h1>
            <p className="max-w-3xl text-sm text-slate-600">
              Review the mapping pass results before allowing the engine to write to the destination.
            </p>
          </div>

          {pageError ? (
            <div role="alert" className="rounded-2xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
              {pageError}
            </div>
          ) : null}

          {loading ? (
            <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
              Loading dry-run results...
            </div>
          ) : artifact ? (
            <>
              {/* Target object summary */}
              <section className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
                <h2 className="mb-4 text-xl font-semibold text-slate-900">
                  Target object summary — {artifact.destinationObjectName}
                </h2>
                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="rounded-xl border border-outline-variant bg-surface px-4 py-4">
                    <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Success rows</div>
                    <div className="mt-1 text-2xl font-semibold text-emerald-700">
                      {formatCount(artifact.successCount)}
                    </div>
                  </div>
                  <div className="rounded-xl border border-outline-variant bg-surface px-4 py-4">
                    <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Failure rows</div>
                    <div className="mt-1 text-2xl font-semibold text-red-700">
                      {formatCount(artifact.failureCount)}
                    </div>
                  </div>
                  <div className="rounded-xl border border-outline-variant bg-surface px-4 py-4">
                    <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Field coverage</div>
                    <div className="mt-1 text-2xl font-semibold text-slate-900">
                      {formatPct(artifact.fieldCoveragePct)}
                    </div>
                  </div>
                </div>
              </section>

              {/* Sample rows table */}
              <section className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
                <h2 className="mb-4 text-xl font-semibold text-slate-900">Sample rows</h2>
                {artifact.sampleRows.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
                    No sample rows available.
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-outline-variant">
                    <table className="w-full border-collapse text-left text-sm">
                      <thead className="bg-surface">
                        <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                          <th className="px-4 py-3">Source field</th>
                          <th className="px-4 py-3">Source value</th>
                          <th className="px-4 py-3">Mapped field</th>
                          <th className="px-4 py-3">Mapped value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {artifact.sampleRows.map((row, rowIndex) =>
                          Object.entries(row.source).map(([sourceField, sourceValue], fieldIndex) => (
                            <tr
                              key={`${rowIndex}-${fieldIndex}`}
                              className="border-t border-outline-variant"
                            >
                              <td className="px-4 py-2 font-mono text-xs text-slate-700">{sourceField}</td>
                              <td className="px-4 py-2 text-slate-900">{String(sourceValue)}</td>
                              <td className="px-4 py-2 font-mono text-xs text-slate-700">
                                {Object.keys(row.mapped)[fieldIndex] ?? "—"}
                              </td>
                              <td className="px-4 py-2 text-slate-900">
                                {String(Object.values(row.mapped)[fieldIndex] ?? "—")}
                              </td>
                            </tr>
                          )),
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              {/* PII masking status */}
              <section className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
                <h2 className="mb-4 text-xl font-semibold text-slate-900">PII masking status</h2>
                {artifact.piiFields.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
                    No PII fields detected.
                  </div>
                ) : (
                  <div className="overflow-hidden rounded-xl border border-outline-variant">
                    <table className="w-full border-collapse text-left text-sm">
                      <thead className="bg-surface">
                        <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                          <th className="px-4 py-3">Source field</th>
                          <th className="px-4 py-3">Token applied</th>
                        </tr>
                      </thead>
                      <tbody>
                        {artifact.piiFields.map((entry) => (
                          <tr key={entry.field} className="border-t border-outline-variant">
                            <td className="px-4 py-3 font-mono text-xs text-slate-900">{entry.field}</td>
                            <td className="px-4 py-3 font-mono text-xs text-slate-600">{entry.token}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              {/* Failures list */}
              <section className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
                <h2 className="mb-4 text-xl font-semibold text-slate-900">
                  Failures ({formatCount(artifact.failureCount)})
                </h2>
                {artifact.failures.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
                    No failures recorded.
                  </div>
                ) : (
                  <div className="overflow-hidden rounded-xl border border-outline-variant">
                    <table className="w-full border-collapse text-left text-sm">
                      <thead className="bg-surface">
                        <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                          <th className="px-4 py-3">Row</th>
                          <th className="px-4 py-3">Reason</th>
                          <th className="px-4 py-3">Field</th>
                          <th className="px-4 py-3">Value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {artifact.failures.map((failure, index) => (
                          <tr key={index} className="border-t border-outline-variant">
                            <td className="px-4 py-3 text-slate-900">Row {failure.rowIndex}</td>
                            <td className="px-4 py-3 font-mono text-xs text-red-700">{failure.reason}</td>
                            <td className="px-4 py-3 font-mono text-xs text-slate-700">{failure.field}</td>
                            <td className="px-4 py-3 text-slate-900">{failure.value}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              {/* Actions — central_team only */}
              {role === "central_team" ? (
                <section className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
                  <h2 className="mb-4 text-xl font-semibold text-slate-900">Decision</h2>

                  {artifact.status !== "pending" ? (
                    <div className="rounded-xl border border-outline-variant bg-surface px-4 py-4 text-sm text-slate-700">
                      This dry-run has already been <span className="font-semibold">{artifact.status}</span>.
                      {artifact.pushBackComment ? (
                        <p className="mt-2 text-slate-600">{artifact.pushBackComment}</p>
                      ) : null}
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <button
                        className="rounded-md bg-primary px-5 py-2 text-sm font-semibold text-white disabled:opacity-60"
                        disabled={actionLoading}
                        onClick={() => void handleApprove()}
                        type="button"
                      >
                        Approve
                      </button>

                      <div className="border-t border-outline-variant pt-4">
                        <label
                          className="mb-2 block text-sm font-semibold text-slate-700"
                          htmlFor="push-back-comment"
                        >
                          Push-back comment
                        </label>
                        <textarea
                          className="w-full rounded-xl border border-outline-variant bg-surface px-4 py-3 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary"
                          disabled={actionLoading}
                          id="push-back-comment"
                          onChange={(e) => { setPushBackComment(e.target.value); }}
                          placeholder="Explain what needs to change before the migration can proceed..."
                          rows={4}
                          value={pushBackComment}
                        />
                        <button
                          className="mt-3 rounded-md border border-red-300 bg-red-50 px-5 py-2 text-sm font-semibold text-red-700 disabled:opacity-60"
                          disabled={actionLoading || !pushBackComment.trim()}
                          onClick={() => void handlePushBack()}
                          type="button"
                        >
                          Push back
                        </button>
                      </div>
                    </div>
                  )}
                </section>
              ) : null}
            </>
          ) : null}
        </section>
      </main>
    );
  }
  ```

- [ ] **Step 3.4: Run the failing page tests**

  ```bash
  cd /Users/vjkotra/projects/katana/web
  npm test -- "dry-run/page" 2>&1 | tail -30
  ```

  Expected: all 8 tests PASS.

- [ ] **Step 3.5: Run the full frontend test suite**

  ```bash
  cd /Users/vjkotra/projects/katana/web
  npm test 2>&1 | tail -10
  ```

  Expected: no new failures.

- [ ] **Step 3.6: Commit**

  ```bash
  git add \
    web/app/projects/[id]/runs/[run_id]/dry-run/page.tsx \
    web/app/projects/[id]/runs/[run_id]/dry-run/page.test.tsx
  git commit -m "feat(001ar): add dry-run review page with approve and push-back actions"
  ```
