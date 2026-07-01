# Delivery Bundle Tab — Design Spec

**Status:** Approved  
**Date:** 2026-07-01

## Problem

The codegen/delivery page (`/projects/[id]/codegen`) is fully implemented but unreachable from the project detail page. Users who want to review or download the SQL delivery bundle have no navigation path to it.

## Solution

Add a fourth "SQL Bundle" tab to the project detail page that navigates to `/projects/[id]/codegen`. No new panel content is needed — the codegen page is the full destination.

## Scope

Single file change: `web/app/projects/[id]/page.tsx`.

## Design

### Tab addition

The existing tab strip has three pills: Overview, Sources, Artifacts. Add a fourth:

```tsx
<button
  className={`rounded-full px-4 py-2 text-sm font-semibold ${
    activeTab === "sql-bundle"
      ? "bg-primary text-white"
      : "border border-outline-variant bg-surface-container text-slate-700"
  }`}
  onClick={() => router.push(`/projects/${id}/codegen`)}
  type="button"
>
  SQL Bundle
</button>
```

### Behavior

Clicking "SQL Bundle" calls `router.push(`/projects/${id}/codegen`)` — it navigates away rather than rendering a panel. `activeTab` does not need a `"sql-bundle"` value because the tab never renders inline content; it is purely a navigation affordance.

### Roles

All authenticated roles see the tab (`central_team`, `project_stakeholder`, `read_only_auditor`). The api.md spec states "any authenticated user with project access" may download the bundle.

## What this is NOT

This spec does not cover:
- Dependency-ordered sequencing of SQL scripts (separate spec: AI-assisted delivery bundle sequencing)
- Sequence number prefixes in the bundle output
- Any changes to the codegen page itself

## Test

Add one test to the project detail page test suite:

- Renders "SQL Bundle" tab button
- Clicking it calls `router.push` with `/projects/${id}/codegen`
