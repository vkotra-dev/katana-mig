# Lookup Snapshot Route Rehome Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move lookup snapshot approval to a project-scoped route while keeping lookup drafts source-scoped, and update the docs and UI client to match.

**Architecture:** Keep the snapshot model project-scoped. The route shape is the thing that changes. Draft lookup maps remain source-scoped because they are created from a specific source contract, but snapshot approval is a project-level action because the resulting artifact is consumed project-wide.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.x ORM, Pytest, TypeScript, Next.js.

## Global Constraints

- Do not add `source_definition_id` to `LookupSnapshot`.
- Keep lookup draft routes source-scoped.
- Keep lookup snapshot ownership project-scoped.
- Update the API documentation alongside the route change.
- Update the frontend helper and page call site to use the new route.

---

### Task 1: Move lookup snapshot approval to project scope

**Files:**
- Modify: `engine/src/migrations_engine/routes/lookup.py`
- Modify: `engine/src/migrations_engine/management/lookup_mapping.py`
- Modify: `engine/tests/test_lookup_mapping_api.py`

**Interfaces:**
- Consumes: lookup snapshot approval behavior, `LookupSnapshot` project ownership
- Produces: a project-scoped approval route that no longer needs `source_definition_id`

- [ ] **Step 1: Add the regression test**

Add or adjust a test so the approval route is exercised as:

```http
POST /projects/{project_id}/lookup-snapshots/{lookup_snapshot_id}/approve
```

The test should assert the approval succeeds without using `source_definition_id` in the path.

- [ ] **Step 2: Update the route and service**

Change the route prefix/path to project scope and remove the source-scoped requirement from approval.

- [ ] **Step 3: Run the engine test**

Run:

```bash
cd engine && PYTHONPATH=src pytest tests/test_lookup_mapping_api.py -q
```

- [ ] **Step 4: Commit**

```bash
git add engine/src/migrations_engine/routes/lookup.py engine/src/migrations_engine/management/lookup_mapping.py engine/tests/test_lookup_mapping_api.py
git commit -m "feat(lookup): rehome snapshot approval to project scope"
```

### Task 2: Update the UI lookup client and page

**Files:**
- Modify: `web/lib/lookup-api.ts`
- Modify: `web/app/projects/[id]/sources/[sourceId]/lookup/page.tsx`
- Modify: `web/lib/lookup-api.test.ts`
- Modify: `web/app/projects/[id]/sources/[sourceId]/lookup/page.test.tsx`

**Interfaces:**
- Consumes: project-scoped lookup snapshot approval route
- Produces: frontend helper calls and page actions wired to the project-scoped path

- [ ] **Step 1: Update the client and tests**

Switch `approveLookupSnapshot()` to call the project-level snapshot route and adjust unit tests accordingly.

- [ ] **Step 2: Update the page if needed**

Ensure the lookup page passes the parameters the new client shape needs.

- [ ] **Step 3: Run the web tests**

Run:

```bash
cd web && npm test -- --run 'lib/lookup-api.test.ts' 'app/projects/[id]/sources/[sourceId]/lookup/page.test.tsx'
```

- [ ] **Step 4: Commit**

```bash
git add web/lib/lookup-api.ts web/app/projects/[id]/sources/[sourceId]/lookup/page.tsx web/lib/lookup-api.test.ts web/app/projects/[id]/sources/[sourceId]/lookup/page.test.tsx
git commit -m "feat(lookup): switch approval UI to project-scoped route"
```

### Task 3: Update the API docs

**Files:**
- Modify: `docs/domain/api.md`

**Interfaces:**
- Consumes: the new lookup snapshot route shape
- Produces: documented project-scoped snapshot approval endpoint

- [ ] **Step 1: Add the API contract update**

Document the project-scoped lookup snapshot approval route and keep the draft
lookup map route under the source path.

- [ ] **Step 2: Verify docs remain aligned**

Make sure the docs reflect the actual backend route shape and do not reintroduce
`source_definition_id` into the snapshot path.

- [ ] **Step 3: Commit**

```bash
git add docs/domain/api.md
git commit -m "docs(api): document project-scoped lookup snapshot approval"
```
