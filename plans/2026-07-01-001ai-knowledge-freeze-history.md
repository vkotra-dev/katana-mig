Task: tasks/001ai-knowledge-freeze-history.md
Domain: docs/domain/ui.md (authoritative), docs/domain/api.md

## Source of truth

`docs/domain/ui.md` and `docs/domain/api.md` define what to build.
Mockmigration is styling reference only.

## Current state

| File | What exists |
|---|---|
| `engine/src/migrations_engine/db/models.py` | `RunRecord` has `knowledge_freeze_version: str | None` — set at baton_4 by the execution engine |
| `engine/src/migrations_engine/execution/engine.py` | `list_runs_for_project` — returns all runs; no freeze-only filter |
| `engine/src/migrations_engine/routes/runs.py` | `GET /projects/{project_id}/runs` — returns all runs via `list_runs_for_project` |
| `web/components/projects/ProjectDetailView.tsx` | Overview tab content — no freeze history panel |
| `web/app/projects/[id]/page.tsx` | Overview tab renders `<ProjectDetailView project={project} />` only |

## Blast radius

| File | Action |
|---|---|
| `engine/src/migrations_engine/api/schemas.py` | modify — add `KnowledgeFreezeRecord` |
| `engine/src/migrations_engine/routes/runs.py` | modify — add `GET /projects/{project_id}/knowledge-freezes` route |
| `engine/src/migrations_engine/execution/engine.py` | modify — add `list_knowledge_freezes` function |
| `engine/tests/test_freeze_history_api.py` | create — service + route tests |
| `web/lib/runs-api.ts` | modify — add `KnowledgeFreezeRecord` type and `listKnowledgeFreezes` helper |
| `web/components/projects/KnowledgeFreezePanel.tsx` | create — self-contained panel fetches and renders freeze list |
| `web/components/projects/KnowledgeFreezePanel.test.tsx` | create — panel tests |
| `web/app/projects/[id]/page.tsx` | modify — render `KnowledgeFreezePanel` alongside `ProjectDetailView` in Overview tab |

---

# Knowledge-Freeze History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only knowledge-freeze history panel to the project detail Overview tab, listing runs where a freeze was recorded, newest first.

**Architecture:** New `list_knowledge_freezes` function queries `RunRecord WHERE knowledge_freeze_version IS NOT NULL`. New route on the existing `runs.py` router. New `KnowledgeFreezePanel` component handles its own fetch; rendered by `page.tsx` alongside `ProjectDetailView` in the Overview tab.

**Tech Stack:** FastAPI, SQLAlchemy 2, pytest; Next.js App Router, React, TypeScript, Vitest + Testing Library

## Global Constraints

- Auth: `require_project_access(db, user=actor, project_id=project_id)` — all roles read
- Styling follows mockmigration patterns; `docs/domain/ui.md` is content authority
- No new DB model or migration — reads existing `RunRecord` data

---

### Task 1: Backend — service, schema, route

**Files:**
- Modify: `engine/src/migrations_engine/api/schemas.py`
- Modify: `engine/src/migrations_engine/execution/engine.py`
- Modify: `engine/src/migrations_engine/routes/runs.py`
- Create: `engine/tests/test_freeze_history_api.py`

**Interfaces:**
- Produces:
  - `KnowledgeFreezeRecord` Pydantic schema
  - `list_knowledge_freezes(db, project_id=str) -> list[dict]`
  - `GET /projects/{project_id}/knowledge-freezes` → `list[KnowledgeFreezeRecord]`

- [ ] **Step 1: Write the failing tests**

Create `engine/tests/test_freeze_history_api.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import ProjectRegistry, RunRecord, User
from migrations_engine.roles import CENTRAL_TEAM_ROLE

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _setup_db() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == settings.bootstrap_admin_email.strip().lower())) is None:
            db.add(User(
                user_id=str(uuid.uuid4()),
                email=settings.bootstrap_admin_email.strip().lower(),
                display_name="Admin",
                password_hash=hash_password(settings.bootstrap_admin_password),
                role=CENTRAL_TEAM_ROLE,
                status="active",
            ))
        db.commit()


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    get_settings.cache_clear()


def _login() -> str:
    settings = get_settings()
    r = client.post("/auth/login", json={
        "email": settings.bootstrap_admin_email,
        "password": settings.bootstrap_admin_password,
    })
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture
def project_with_freezes() -> str:
    pid = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(ProjectRegistry(project_id=pid, status="active"))
        # run with freeze
        db.add(RunRecord(
            run_id=str(uuid.uuid4()),
            project_id=pid,
            destination_object_name="Customer",
            environment="UAT",
            status="completed",
            knowledge_freeze_version="artifact-001",
            start_metadata={"started_at": "2026-07-01T10:00:00+00:00"},
        ))
        # run WITHOUT freeze — must not appear
        db.add(RunRecord(
            run_id=str(uuid.uuid4()),
            project_id=pid,
            destination_object_name="Order",
            status="running",
            knowledge_freeze_version=None,
        ))
        db.commit()
    return pid


def test_list_knowledge_freezes_service(project_with_freezes: str) -> None:
    from migrations_engine.execution.engine import list_knowledge_freezes
    with SessionLocal() as db:
        results = list_knowledge_freezes(db, project_id=project_with_freezes)
    assert len(results) == 1
    assert results[0]["knowledge_freeze_version"] == "artifact-001"
    assert results[0]["destination_object_name"] == "Customer"


def test_list_knowledge_freezes_excludes_non_freeze_runs(project_with_freezes: str) -> None:
    from migrations_engine.execution.engine import list_knowledge_freezes
    with SessionLocal() as db:
        results = list_knowledge_freezes(db, project_id=project_with_freezes)
    names = [r["destination_object_name"] for r in results]
    assert "Order" not in names


def test_get_knowledge_freezes_route(project_with_freezes: str) -> None:
    token = _login()
    r = client.get(
        f"/projects/{project_with_freezes}/knowledge-freezes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["knowledge_freeze_version"] == "artifact-001"
    assert "run_id" in body[0]
    assert "started_at" in body[0]


def test_get_knowledge_freezes_returns_empty_list_when_none() -> None:
    pid = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(ProjectRegistry(project_id=pid, status="active"))
        db.commit()
    token = _login()
    r = client.get(
        f"/projects/{pid}/knowledge-freezes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() == []


def test_get_knowledge_freezes_requires_auth() -> None:
    r = client.get("/projects/any-id/knowledge-freezes")
    assert r.status_code == 401
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_freeze_history_api.py -v
```

Expected: FAIL — route not found (404).

- [ ] **Step 3: Add `KnowledgeFreezeRecord` to `engine/src/migrations_engine/api/schemas.py`**

Open `engine/src/migrations_engine/api/schemas.py`. Add after `RunCheckpointResponse`:

```python
class KnowledgeFreezeRecord(BaseModel):
    run_id: str
    knowledge_freeze_version: str
    destination_object_name: str
    environment: str | None
    status: str
    started_at: datetime | None
    created_at: datetime
```

- [ ] **Step 4: Add `list_knowledge_freezes` to `engine/src/migrations_engine/execution/engine.py`**

Open `engine/src/migrations_engine/execution/engine.py`. Add after `list_runs_for_project`:

```python
def list_knowledge_freezes(db: Session, *, project_id: str) -> list[dict[str, Any]]:
    runs = list(
        db.scalars(
            select(RunRecord)
            .where(
                RunRecord.project_id == project_id,
                RunRecord.knowledge_freeze_version.is_not(None),
            )
            .order_by(RunRecord.created_at.desc())
        )
    )
    result = []
    for run in runs:
        started_at = None
        if run.start_metadata and run.start_metadata.get("started_at"):
            started_at = datetime.fromisoformat(str(run.start_metadata["started_at"]))
        result.append({
            "run_id": run.run_id,
            "knowledge_freeze_version": run.knowledge_freeze_version,
            "destination_object_name": run.destination_object_name,
            "environment": run.environment,
            "status": run.status,
            "started_at": started_at,
            "created_at": run.created_at,
        })
    return result
```

- [ ] **Step 5: Add route to `engine/src/migrations_engine/routes/runs.py`**

Open `engine/src/migrations_engine/routes/runs.py`. Add this import alongside the existing engine imports:

```python
from ..execution.engine import execute_run, get_run, list_knowledge_freezes, list_run_checkpoints, list_runs_for_project, pause_run
```

Add this import to the schemas import:

```python
from ..api.schemas import KnowledgeFreezeRecord, RunCheckpointResponse, RunResponse
```

Add the route after the existing `GET /` list route:

```python
@router.get("/knowledge-freezes", response_model=list[KnowledgeFreezeRecord])
def get_knowledge_freezes(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[KnowledgeFreezeRecord]:
    require_project_access(db, user=actor, project_id=project_id)
    return [KnowledgeFreezeRecord.model_validate(item) for item in list_knowledge_freezes(db, project_id=project_id)]
```

**Important:** This route must be registered **before** `GET /{run_id}` in the file, otherwise FastAPI will try to match `"knowledge-freezes"` as a `run_id` parameter and return 404. Verify the route order after adding.

- [ ] **Step 6: Run all tests**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_freeze_history_api.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 7: Run full engine suite**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add engine/src/migrations_engine/api/schemas.py \
        engine/src/migrations_engine/execution/engine.py \
        engine/src/migrations_engine/routes/runs.py \
        engine/tests/test_freeze_history_api.py
git commit -m "feat(001ai): add knowledge-freeze history endpoint"
```

---

### Task 2: Frontend — API helper, panel component, page wiring

**Files:**
- Modify: `web/lib/runs-api.ts`
- Create: `web/components/projects/KnowledgeFreezePanel.tsx`
- Create: `web/components/projects/KnowledgeFreezePanel.test.tsx`
- Modify: `web/app/projects/[id]/page.tsx`

**Interfaces:**
- Consumes: `KnowledgeFreezeRecord`, `listKnowledgeFreezes` from `../../lib/runs-api`
- Produces: `<KnowledgeFreezePanel projectId token />` — self-contained, handles its own fetch

- [ ] **Step 1: Write the failing tests**

Create `web/components/projects/KnowledgeFreezePanel.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { KnowledgeFreezePanel } from "./KnowledgeFreezePanel";

const { listKnowledgeFreezesMock } = vi.hoisted(() => ({
  listKnowledgeFreezesMock: vi.fn(),
}));

vi.mock("../../lib/runs-api", () => ({
  listKnowledgeFreezes: listKnowledgeFreezesMock,
}));

const FREEZE = {
  runId: "run-1",
  knowledgeFreezeVersion: "artifact-001",
  destinationObjectName: "Customer",
  environment: "UAT",
  status: "completed",
  startedAt: "2026-07-01T10:00:00Z",
  createdAt: "2026-07-01T09:58:00Z",
};

describe("KnowledgeFreezePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders freeze rows when freezes exist", async () => {
    listKnowledgeFreezesMock.mockResolvedValue([FREEZE]);
    render(<KnowledgeFreezePanel projectId="p-1" token="tok" />);
    expect(await screen.findByText("Customer")).toBeInTheDocument();
    expect(screen.getByText("UAT")).toBeInTheDocument();
    expect(screen.getByText("artifact-001")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("renders empty state when no freezes", async () => {
    listKnowledgeFreezesMock.mockResolvedValue([]);
    render(<KnowledgeFreezePanel projectId="p-1" token="tok" />);
    expect(await screen.findByText(/No knowledge freezes recorded/i)).toBeInTheDocument();
  });

  it("renders error state on fetch failure", async () => {
    listKnowledgeFreezesMock.mockRejectedValue(new Error("Network error"));
    render(<KnowledgeFreezePanel projectId="p-1" token="tok" />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- components/projects/KnowledgeFreezePanel.test.tsx
```

Expected: FAIL — module not found.

- [ ] **Step 3: Add `KnowledgeFreezeRecord` type and `listKnowledgeFreezes` to `web/lib/runs-api.ts`**

Open `web/lib/runs-api.ts`. Add after the existing interfaces at the top:

```typescript
export interface KnowledgeFreezeRecord {
  runId: string;
  knowledgeFreezeVersion: string;
  destinationObjectName: string;
  environment: string | null;
  status: string;
  startedAt: string | null;
  createdAt: string;
}
```

Add the helper function at the end of the file:

```typescript
export async function listKnowledgeFreezes(
  token: string,
  projectId: string,
): Promise<KnowledgeFreezeRecord[]> {
  const response = await requestJson<Array<{
    run_id: string;
    knowledge_freeze_version: string;
    destination_object_name: string;
    environment: string | null;
    status: string;
    started_at: string | null;
    created_at: string;
  }>>(`/projects/${projectId}/knowledge-freezes`, { method: "GET", token });
  return response.map((r) => ({
    runId: r.run_id,
    knowledgeFreezeVersion: r.knowledge_freeze_version,
    destinationObjectName: r.destination_object_name,
    environment: r.environment,
    status: r.status,
    startedAt: r.started_at,
    createdAt: r.created_at,
  }));
}
```

The `requestJson` helper is already defined in `runs-api.ts` (private, not exported). The new function must live in the same file to use it.

- [ ] **Step 4: Create `web/components/projects/KnowledgeFreezePanel.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { listKnowledgeFreezes, type KnowledgeFreezeRecord } from "../../lib/runs-api";

export interface KnowledgeFreezePanelProps {
  projectId: string;
  token: string;
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  return value.slice(0, 16).replace("T", " ");
}

export function KnowledgeFreezePanel({ projectId, token }: KnowledgeFreezePanelProps) {
  const [freezes, setFreezes] = useState<KnowledgeFreezeRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setErrorMessage(null);
    void listKnowledgeFreezes(token, projectId)
      .then((data) => {
        if (active) setFreezes(data);
      })
      .catch((error: unknown) => {
        if (active) setErrorMessage(error instanceof Error ? error.message : "Unable to load freeze history.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [projectId, token]);

  return (
    <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
      <div>
        <h2 className="text-xl font-semibold text-slate-900">Knowledge-freeze history</h2>
        <p className="text-sm text-slate-600">Runs where a knowledge freeze was recorded.</p>
      </div>

      {loading ? (
        <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3 text-sm text-slate-600">
          Loading freeze history...
        </div>
      ) : errorMessage ? (
        <div role="alert" className="rounded-xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
          {errorMessage}
        </div>
      ) : freezes.length === 0 ? (
        <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
          No knowledge freezes recorded yet.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-outline-variant">
          <table className="w-full border-collapse text-left">
            <thead className="bg-surface">
              <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Destination</th>
                <th className="px-4 py-3">Environment</th>
                <th className="px-4 py-3">Frozen artifact</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {freezes.map((freeze) => (
                <tr key={freeze.runId} className="border-t border-outline-variant">
                  <td className="px-4 py-3 text-sm text-slate-700">{formatDate(freeze.startedAt ?? freeze.createdAt)}</td>
                  <td className="px-4 py-3 text-sm font-semibold text-slate-900">{freeze.destinationObjectName}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{freeze.environment ?? "—"}</td>
                  <td className="px-4 py-3">
                    <span className="mono-id">{freeze.knowledgeFreezeVersion}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                      freeze.status === "completed"
                        ? "bg-emerald-100 text-emerald-900"
                        : freeze.status === "failed"
                        ? "bg-rose-100 text-rose-900"
                        : "bg-amber-100 text-amber-900"
                    }`}>
                      {freeze.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 5: Run the panel tests**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- components/projects/KnowledgeFreezePanel.test.tsx
```

Expected: all 3 tests PASS.

- [ ] **Step 6: Wire `KnowledgeFreezePanel` into the Overview tab in `web/app/projects/[id]/page.tsx`**

Open `web/app/projects/[id]/page.tsx`. Add the import at the top:

```tsx
import { KnowledgeFreezePanel } from "../../../components/projects/KnowledgeFreezePanel";
```

Find the `activeTab === "overview"` branch. Change it from:

```tsx
activeTab === "overview" ? (
  <ProjectDetailView project={project} />
) :
```

To:

```tsx
activeTab === "overview" ? (
  <>
    <ProjectDetailView project={project} />
    <KnowledgeFreezePanel projectId={id} token={session.accessToken} />
  </>
) :
```

- [ ] **Step 8: Run full web test suite**

```bash
cd /Users/vjkotra/projects/katana/web
npm test
```

Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add web/lib/runs-api.ts \
        web/components/projects/KnowledgeFreezePanel.tsx \
        web/components/projects/KnowledgeFreezePanel.test.tsx \
        web/app/projects/\[id\]/page.tsx
git commit -m "feat(001ai): add knowledge-freeze history panel to project detail overview"
```
