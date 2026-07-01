# Task 001ai — Knowledge-Freeze History Panel

**Plan:** `plans/2026-07-01-001ai-knowledge-freeze-history.md`

## Domain

- `docs/domain/ui.md` — authoritative screen contract
- `docs/domain/api.md` — endpoint reference
- Mockmigration is styling reference only

## Scope

Add a read-only knowledge-freeze history panel to the project detail Overview
tab. Lists all runs for the project where `knowledge_freeze_version IS NOT NULL`,
newest first.

No new DB model or migration — reads existing `RunRecord` data.

## Tasks (2)

1. **Backend** — `list_knowledge_freezes` service function, `KnowledgeFreezeRecord`
   schema, `GET /projects/{project_id}/knowledge-freezes` route on `runs.py` router.
   **Critical:** register the new route before `GET /{run_id}` in the file to
   avoid FastAPI matching `"knowledge-freezes"` as a run_id.

2. **Frontend** — `KnowledgeFreezeRecord` type + `listKnowledgeFreezes` helper in
   `runs-api.ts`; `KnowledgeFreezePanel` component (self-contained fetch); wire
   into `page.tsx` Overview tab alongside `ProjectDetailView`.

## Success criteria

- `GET /projects/{id}/knowledge-freezes` returns only runs with a freeze version set
- Panel renders freeze list with date, destination, environment, artifact ID, status
- Empty state shown when no freezes exist
- Error state shown on fetch failure
- All engine and web tests pass
