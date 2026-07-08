# Plan: 001ci — Remove Project GUID ID from UI Views

- **Task Link:** [tasks/001ci-remove-project-id-display.md](../tasks/001ci-remove-project-id-display.md)
- **Domain:** [docs/domain/ui.md](../docs/domain/ui.md)

## Current State

Project IDs are rendered as small `mono-id` tags in three files:
- `web/components/portfolio/PortfolioTable.tsx` (L312)
- `web/components/projects/ProjectDetailView.tsx` (L119)
- `web/components/projects/ProjectTable.tsx` (L185)

## Objective

Remove the project ID elements from the layout of all three files, and update the associated test.

## File Changes

### Step 1 — Update `web/components/portfolio/PortfolioTable.tsx`

Remove:
```tsx
                      <div className="mono-id">{project.projectId}</div>
```

### Step 2 — Update `web/components/projects/ProjectDetailView.tsx`

Remove:
```tsx
          <span className="mono-id">{project.projectId}</span>
```

### Step 3 — Update `web/components/projects/ProjectTable.tsx`

Remove:
```tsx
                      <div className="mono-id text-xs">{project.projectId}</div>
```

### Step 4 — Update `web/components/projects/__tests__/ProjectDetailView.test.tsx`

Remove the test assertion:
```typescript
    expect(screen.getByText("project-abc")).toBeInTheDocument();
```

## Verification

1. Verify TypeScript compilation (`tsc`).
2. Run Vitest tests (`vitest run`).
3. Manually confirm project GUIDs are gone from dashboard, projects list, and details pages.

## Commit

```
feat: remove project UUID/GUID display from dashboard and project views
```
