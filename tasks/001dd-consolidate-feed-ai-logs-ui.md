# Plan: 001dd — Consolidated UI AI Log Viewer for Feeds

## Background
Following the backend changes in `001dc` that aligned all feed-related AI logs (source analysis, mapping, and lookups) to use the `feedId` as their `artifact_id`, the UI needs to be updated. Currently, the Feed Detail page has three separate, nested `<AiLogViewer />` components scattered throughout the page.

The goal is to simplify the UI by placing a single `<AiLogViewer />` at the bottom of the Feed Detail page that shows all AI traces for the feed in one paginated list.

## Objective
Remove the nested `AiLogViewer` instances from the Feed Detail page and place a single, consolidated viewer at the bottom of the page, ensuring pagination is working.

## Implementation Steps
1. **Remove Nested Viewers (`web/app/projects/[id]/feeds/[feedId]/page.tsx`):**
   - Delete the `<details>` wrapper and `<AiLogViewer />` for **Source Analysis** (Feed Analysis section).
   - Delete the `<details>` wrapper and `<AiLogViewer />` for **Mapping** (expanded mapping table rows).
   - Delete the `<details>` wrapper and `<AiLogViewer />` for **Lookups** (expanded lookup fiber rows).

2. **Add Consolidated Viewer:**
   - At the very bottom of the `FeedDetailPage` layout (below the Fibers table but inside the main container), add a new section:
     ```tsx
     {(role === "central_team" || role === "admin") && (
       <div className="mt-8 space-y-4">
         <h2 className="text-lg font-bold text-slate-800 border-b border-outline-variant pb-2">
           Project AI Trace & Reasoning
         </h2>
         <AiLogViewer
           token={session?.accessToken}
           projectId={projectId}
           feature="feed_mapping"
           artifactId={feedId}
           canViewLogs={true}
         />
       </div>
     )}
     ```
   - Notice that `callType` is omitted, so the viewer will fetch ALL call types for this `feedId`.

3. **Verify Pagination (`web/components/ai-logs/AiLogViewer.tsx`):**
   - The `AiLogViewer` component and `useAiCallLogs` hook already support offset-based pagination via a "Load More" button. Ensure this works properly out of the box when rendering larger consolidated lists.

## Blast Radius
- `web/app/projects/[id]/feeds/[feedId]/page.tsx`

## Verification
- Navigate to the Feed Detail page.
- There should be no nested AI log accordion buttons inside the mapping or lookup tables.
- At the bottom of the page, a unified "Project AI Trace & Reasoning" section should display all AI logs (Source Analysis, Mapping, Lookup Mapping) in reverse chronological order.
- The "Load More" button should correctly paginate if logs exceed the limit of 50.
