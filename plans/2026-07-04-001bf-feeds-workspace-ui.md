# Feeds Workspace UI — Implementation Plan

Task: [tasks/001bf-feeds-workspace-ui.md](/Users/vjkotra/projects/katana/tasks/001bf-feeds-workspace-ui.md)
Domain: [docs/domain/source-model.md](/Users/vjkotra/projects/katana/docs/domain/source-model.md)
Depends on: 001bd, 001be

**Goal:** Rename Sources → Feeds and build a per-feed workspace with role-gated routing. Central_team lands on Feed Detail (slice status, multi-table mapping, lookup fibers, reviews). Business_user lands on the combined review grid (read-only + approve/reject).

---

## Blast Radius

- `web/components/projects/ProjectNavigationTabs.tsx`
- `web/components/projects/SourceList.tsx`
- `web/app/projects/[id]/page.tsx`
- `web/app/projects/[id]/feeds/[feedId]/page.tsx` (new)
- `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` (new)
- `web/components/projects/ReviewGrid.tsx` (new)
- `web/components/projects/__tests__/SourceList.test.tsx`
- `web/components/projects/__tests__/ProjectNavigationTabs.test.tsx`
- `web/app/projects/[id]/page.test.tsx`

---

## File Changes

### 1. Rename Sources → Feeds (3 files)

**`ProjectNavigationTabs.tsx`**

Change the tab entry from `{ key: "sources", label: "Sources" }` to `{ key: "feeds", label: "Feeds" }`.
Update the `ProjectTabKey` type: replace `"sources"` with `"feeds"`.

**`SourceList.tsx`**

- Heading: `"Sources"` → `"Feeds"`
- Sub-heading: `"Declared source contracts and uploaded slices."` → `"Declared feed contracts and uploaded slices."`
- Button: `"Add Source"` → `"Add Feed"`
- Replace the two `<a>` action links per row with a single `<button>` that calls an `onFeedClick(sourceDefinitionId: string)` prop. This makes SourceList presentational — the parent controls routing.

Add to `SourceListProps`:
```typescript
onFeedClick: (sourceDefinitionId: string) => void;
```

Row actions column becomes:
```tsx
<td className="px-4 py-3">
  <button
    className="inline-flex rounded-md border border-outline-variant px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-outline-variant/40"
    onClick={() => props.onFeedClick(source.sourceDefinitionId)}
    type="button"
  >
    Open feed
  </button>
</td>
```

**`page.tsx`** (project detail)

- `activeTab` state type: `"overview" | "sources" | "artifacts"` → `"overview" | "feeds" | "artifacts"`
- `initialTab` parse: check `initialTab === "feeds"` — also accept `initialTab === "sources"` and map to `"feeds"` for backwards compat with existing bookmarks.
- Conditional render: `activeTab === "sources"` → `activeTab === "feeds"`
- Pass `onFeedClick` into `<SourceList>`:

```typescript
const handleFeedClick = (sourceDefinitionId: string) => {
  if (role === "business_user") {
    router.push(`/projects/${id}/feeds/${sourceDefinitionId}/review`);
  } else {
    router.push(`/projects/${id}/feeds/${sourceDefinitionId}`);
  }
};
```

---

### 2. New: `ReviewGrid` component

Location: `web/components/projects/ReviewGrid.tsx`

Pure display component — no API calls. Data passed as props.

```typescript
export interface MappingTableRecord {
  destinationTableName: string;
  bindings: Array<{
    sourceField: string;
    destinationField: string;
    bindingType: "direct" | "detail_fk" | "lookup_fk";
    referenceTableName?: string | null;
  }>;
}

export interface LookupValueGroup {
  lookupName: string;
  referenceTableName: string;
  pairs: Array<{
    sourceValue: string;
    destinationRow: Record<string, unknown>;
    confidenceScore: number;
    status: "confirmed" | "pending" | "rejected";
  }>;
}

interface ReviewGridProps {
  mappingTables: MappingTableRecord[];
  lookupGroups: LookupValueGroup[];
  onApprove?: () => void;           // present for business_user only
  onRequestRevision?: (comment: string) => void;
}
```

Renders two sections:

**Table mapping grid** — expandable accordion per destination table. Columns: Source field | Destination field | Binding type badge.

Binding type badge styles:
- `direct`: grey `bg-slate-100 text-slate-600`
- `detail_fk`: blue `bg-blue-100 text-blue-700`
- `lookup_fk`: amber `bg-amber-500/10 text-amber-700`

**Lookup value mapping grids** — one section per `LookupValueGroup`. Header shows `lookupName` + `referenceTableName` chip. Table: Source value | Destination row (JSON summary) | Confidence % | Status chip.

**Approval strip** (only when `onApprove` or `onRequestRevision` is provided):
- "Approve" primary button → calls `onApprove()`
- "Request revision" outline button → expands inline textarea → "Send" confirms → calls `onRequestRevision(comment)`

---

### 3. New: Feed Detail workspace

Location: `web/app/projects/[id]/feeds/[feedId]/page.tsx`

Fetches:
1. Feed contract: `getFeedContract(token, projectId, feedId)`
2. All mapping snapshots for this feed: `listMappingSnapshots(token, projectId, feedId)` — returns the multi-table response from 001bd.
3. Lookup mapping data per lookup group: `listLookupMappings(token, projectId, feedId)`

**Slice status panel** (always visible):
- Status chip: `pending` (amber) or `approved` (green) from feed contract.
- If `pending`: show hard-gate banner `"Slice approval required before mapping and lookups can proceed."` Downstream sections rendered but overlaid with a disabled state.
- If `central_team`: show approve / reject buttons.

**Field mapping section** (locked when slice pending):
- One expandable card per `MappingTableRecord` in the snapshot response.
- Card header: destination table name.
- Table inside: source field → destination field, binding type badge.

**Lookup fibers section** (locked when slice pending):
- One card per `lookup_fk` binding across all mapping tables (derived from `lookup_table_references` in the snapshot response).
- Card header: source field name + reference table chip.
- Source value list: in-place editable list (`discovery_type="operator"`).
- "Run AI mapping" button: calls `POST /projects/{id}/feeds/{feedId}/lookup/submit`.

**Reviews section**:
```tsx
<ReviewGrid
  mappingTables={mappingTables}
  lookupGroups={lookupGroups}
/>
```
(No `onApprove`/`onRequestRevision` — operator adjusts but does not formally approve here.)

---

### 4. New: Grid view

Location: `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`

Fetches the same mapping snapshot and lookup mapping data as Feed Detail. All roles can access this route; operator is linked here from Feed Detail "View review" link.

```tsx
<ReviewGrid
  mappingTables={mappingTables}
  lookupGroups={lookupGroups}
  onApprove={role === "business_user" ? handleApprove : undefined}
  onRequestRevision={role === "business_user" ? handleRequestRevision : undefined}
/>
```

`handleApprove` calls the approve endpoint (to be wired to the MappingReview approval workflow in a follow-on task — for now, calls the existing snapshot approval endpoint).

---

## Tests

- [ ] `ProjectNavigationTabs.test.tsx`: tab label reads "Feeds", not "Sources".
- [ ] `SourceList.test.tsx`: heading reads "Feeds"; "Open feed" button calls `onFeedClick` prop with `sourceDefinitionId`.
- [ ] `page.test.tsx` (project detail): `handleFeedClick` routes `business_user` → `/review`, `central_team` → detail; `?tab=sources` param maps to feeds tab.
- [ ] `feeds/[feedId]/page.test.tsx`: pending slice shows hard-gate banner; approved slice renders mapping section; lookup fiber cards render one per lookup_fk binding.
- [ ] `feeds/[feedId]/review/page.test.tsx`: ReviewGrid receives correct props; approve button present for `business_user`; absent for `central_team`.
- [ ] `ReviewGrid.test.tsx`: binding type badges render correctly; approval strip conditional on props.

---

## Verification

- Load project detail → tab label reads "Feeds".
- Click a feed row as `central_team` → Feed Detail workspace.
- Click a feed row as `business_user` → Grid view.
- Feed Detail with pending slice: downstream sections show disabled banner.
- Feed Detail with approved slice: mapping tables expand; lookup fiber cards present; Reviews section shows ReviewGrid.
- Grid view: table mapping accordion + lookup grids visible; Approve / Request revision strip visible for `business_user` only.
- Navigate to `?tab=sources` (old bookmark) → redirects to feeds tab without error.

---

## Pitfalls

- SourceList has no session access — pass `onFeedClick` from the page. Do not import session inside SourceList.
- `?tab=sources` URL param must map to `"feeds"` tab for backwards compat — handle in the `initialTab` parse block, not with a redirect.
- The existing `/sources/[sourceId]/mapping` and `/sources/[sourceId]/lookup` routes must not be deleted or broken.
- ReviewGrid is a pure display component — no API calls, no `useEffect` inside it.
- The feeds workspace at `/feeds/[feedId]` is a new route in addition to — not a replacement for — the existing `/sources/[sourceId]/mapping` and `/sources/[sourceId]/lookup` routes.

---

## Commit

- `feat(001bf): per-feed workspace with role-gated routing and shared review grid`
