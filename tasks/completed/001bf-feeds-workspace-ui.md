# Task 001bf — Feeds Workspace UI

**Plan:** `plans/2026-07-04-001bf-feeds-workspace-ui.md`

**Depends on:** 001bd (multi-table mapping snapshot API + `lookup_table_references`), 001be (AI-detected lookup fields in existing mapping/lookup pages)

## Domain

- [source-model.md](/Users/vjkotra/projects/katana/docs/domain/source-model.md)
- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)

## Current State

- Project detail page has a "Sources" tab (`SourceList.tsx`) showing a flat list with "Open mapping" and "Open lookup" action links per source row.
- Mapping and lookup are separate standalone pages at `/sources/[sourceId]/mapping` and `/sources/[sourceId]/lookup`.
- No per-feed workspace. No role-gated routing. No combined review grid.
- "Sources" terminology throughout: tab label, heading, button text, internal tab state key.

## Problem

All feed-related work is fragmented across separate pages with no unified workspace. There is no single place for an operator to see slice status, field mappings, lookup fibers, and reviews for a feed. Business users have no role-appropriate entry point that shows only the AI-produced grids. Approvals have no per-feed surface.

## Objective

Restructure the project detail into a per-feed workspace:

1. **Rename Sources → Feeds** everywhere (tab label, heading, button text, internal state key).
2. **Feed list** — replace the flat "Open mapping" / "Open lookup" action links with a single row click that routes based on role.
3. **Operator (central_team)** — click routes to Feed Detail workspace (`/feeds/[feedId]`) with sections: slice status, field mapping (multi-table AI results), lookup fibers (one card per lookup FK), Reviews.
4. **Business user (business_user)** — click routes to Grid view (`/feeds/[feedId]/review`) showing read-only table mapping + lookup value mapping grids with Approve / Request revision controls.
5. **ReviewGrid** — shared component used in the operator's Reviews section and as the full view for business users.

## Scope

- Rename "Sources" → "Feeds" in:
  - `web/components/projects/ProjectNavigationTabs.tsx` — tab label
  - `web/components/projects/SourceList.tsx` — heading, sub-heading, "Add Source" button
  - `web/app/projects/[id]/page.tsx` — `activeTab` state type and conditional render
- Replace "Open mapping" + "Open lookup" action links in the feed list row with a single click handler prop (`onFeedClick`) so the parent page controls routing by role.
- Create `web/app/projects/[id]/feeds/[feedId]/page.tsx` — Feed Detail workspace (central_team):
  - Slice status panel: status chip, upload action, approve/reject for central_team; hard-gate banner locks downstream sections when slice is pending.
  - Field mapping section: AI-assigned destination tables (from 001bd multi-table response), each expandable with field bindings and binding type badges (direct / detail_fk / lookup_fk).
  - Lookup fibers section: one card per `lookup_fk` binding — source field, reference table name chip, in-place source value list editing, "Run AI mapping" button.
  - Reviews section: renders `<ReviewGrid>` component.
- Create `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` — Grid view (business_user default; operator navigable):
  - Renders `<ReviewGrid>` with Approve / Request revision controls for business_user.
- Create `web/components/projects/ReviewGrid.tsx` — shared pure display component:
  - Table mapping grid: expandable accordion per destination table; columns: Source field | Destination field | Binding type badge.
  - Lookup value mapping grids: one section per lookup field; columns: Source value | Destination row | Confidence | Status.
  - Approval strip (conditional on role): Approve button + Request revision button (inline comment textarea).
- Update relevant tests.

## Out of Scope

- Implementing the MappingReview entity or approval status machine — follow-on task.
- Moving or removing the existing `/sources/[sourceId]/mapping` and `/sources/[sourceId]/lookup` pages — they remain for 001be and backwards compat.
- Backend API changes beyond consuming what 001bd and 001be deliver.

## Acceptance Criteria

- "Sources" tab is labelled "Feeds" throughout the UI; no visible "Sources" label remains.
- Feed list row click routes `central_team` to Feed Detail and `business_user` to Grid view.
- Feed Detail shows AI-assigned destination tables with field bindings and binding type badges.
- Feed Detail shows one lookup fiber card per `lookup_fk` binding from the mapping snapshot.
- Feed Detail downstream sections show a hard-gate banner when slice status is pending.
- Grid view shows read-only table mapping accordion + lookup value mapping grids.
- Grid view shows Approve / Request revision controls for `business_user`.
- ReviewGrid is a shared component with no API calls inside it — data passed as props.
- All updated files pass their existing tests; new pages have tests covering the routing split and grid rendering.

## Pitfalls

- `SourceList.tsx` has no direct access to session role — pass `onFeedClick` from the page (which has session). Do not fetch session inside SourceList.
- `?tab=sources` URL param is used for deep-linking — map `"sources"` → `"feeds"` in the `initialTab` parse for backwards compat; do not break existing bookmarks.
- The existing `/sources/[sourceId]/mapping` and `/sources/[sourceId]/lookup` routes must not be deleted.
- ReviewGrid must be a pure display component — no fetching inside it.
- The `activeTab` state in `page.tsx` uses the string `"sources"` — rename consistently to avoid state drift between the URL param and the conditional render.

## Commit

- `feat(001bf): per-feed workspace with role-gated routing and shared review grid`
