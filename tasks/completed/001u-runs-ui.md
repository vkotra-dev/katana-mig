# Task 001u — Runs UI

**Plan:** `plans/2026-06-29-001u-runs-ui.md`

## Domain

- `docs/domain/runs.md` — run statuses, stages, baton chain
- `docs/domain/ui.md` — design system tokens
- `docs/design/stitch/03-launch-run.md` — launch run dialog mockup
- `docs/design/stitch/04-run-detail.md` — run detail screen mockup
- `docs/design/stitch/05-runs-list.md` — runs list screen mockup

## Depends on

- 001t (runs backend — API endpoints must exist)
- 001p (project CRUD UI — project detail page pattern to follow)

## Scope

Three surfaces: runs list page, run detail page, launch run dialog. All follow the
stitch design prompts exactly — no invented columns, widgets, or vocabulary.

## API client (`web/lib/runs-api.ts`)

```ts
export type RunStatus = "queued" | "running" | "paused" | "completed" | "failed" | "awaiting_approval";

export interface RunRecord {
  run_id: string;
  project_id: string;
  destination_object_name: string;
  environment: string | null;
  status: RunStatus;
  current_stage: string | null;
  source_slice_version: string | null;
  mapping_snapshot_version: string | null;
  lookup_snapshot_version: string | null;
  codegen_artifact_id: string | null;
  knowledge_freeze_version: string | null;
  started_at: string | null;
  last_checkpoint_at: string | null;
  created_at: string;
}

export interface RunCheckpoint {
  checkpoint_id: string;
  run_id: string;
  stage: string;
  last_completed_row: number | null;
  approved_snapshots: Record<string, string>;
  pause_reason: string | null;
  created_at: string;
}
```

Functions: `listRuns`, `getRun`, `createRun`, `launchRun`, `resumeRun`, `listCheckpoints`.

## Pages

### `/runs` — Runs list (`web/app/runs/page.tsx`)

Per stitch `05-runs-list.md`:
- Dense table: `run_id` (monospace + copy), Project link, Destination object,
  Environment tag, Status chip, Current stage, Started (monospace), Last checkpoint
  (monospace), Reconciliation status (green/red/gray)
- Filter bar: project, environment, status, object
- "Launch run" button (top-right, `central_team` only)
- Row hover: "Open" quick action; paused rows also show role-gated "Resume"
- Empty state and loading skeleton

### `/runs/[id]` — Run detail (`web/app/runs/[id]/page.tsx`)

Per stitch `04-run-detail.md`:

**Header:** monospace `run_id` + copy, project link, destination object, environment
tag, status chip (color-coded), started / last-checkpoint timestamps, role-gated
Resume button when paused.

**Progress strip:** horizontal stepper showing current stage.

**State banners (below header, above tabs):**
- Paused: amber banner with pause reason + Resume button
- Failed: red banner with failure reason
- Budget-exhausted: gray banner

**Tabs:**
1. Overview — key-value grid of run metadata
2. Pinned snapshots — version pills: source slice, mapping, lookup, codegen artifact
   (`cga_…`), knowledge-freeze; each copyable
3. Checkpoints — table of checkpoint boundaries; highlight the resume point
4. Timeline — ordered event log with monospace timestamps
5. Reconciliation & lineage — status + link

Polling: 10-second interval when `status` is `running`; show "last updated" timestamp
and manual refresh button.

### Launch run dialog

Per stitch `03-launch-run.md`: modal triggered from Runs list or project Sources tab.
Fields: destination object name (text), source contract selector, environment (optional).
Submit calls `createRun` then `launchRun`; on success navigates to the new run detail.

## Status chip colors

| Status | Color |
|---|---|
| `queued` | gray |
| `running` | blue |
| `paused` | amber |
| `awaiting_approval` | amber |
| `completed` | green |
| `failed` | red |

## Acceptance criteria

- [ ] Runs list renders with all columns; empty and loading states work
- [ ] Filter bar narrows by status and project
- [ ] Run detail shows all five tabs with correct data
- [ ] Pinned snapshots tab shows monospace version pills with copy icons
- [ ] Paused run shows amber banner and Resume button (central_team only)
- [ ] Auto-polling stops when run reaches terminal status (completed/failed)
- [ ] Launch run dialog creates and launches a run, then navigates to detail
- [ ] All component tests pass (Vitest + testing-library)

## Notes

- Use `getUiSession()` for role-gating Resume button — same pattern as other pages
- Monospace IDs use `font-mono` (JetBrains Mono already in design system)
- No reconciliation detail in this task — link only (YAGNI)
- Stitch vocabulary must be exact: "destination object", not "entity" or "table";
  "awaiting approval", not "pending"; stages from the `runs.md` baton chain only
