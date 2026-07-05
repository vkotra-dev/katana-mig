# Remove Global Approvals Inbox — Implementation Plan

Task: [tasks/001bg-remove-global-approvals-inbox.md](/Users/vjkotra/projects/katana/tasks/001bg-remove-global-approvals-inbox.md)

**Goal:** Delete the global approvals inbox page, nav link, and badge count while preserving the per-slice approve/reject/resubmit backend routes for use by the 001bf per-feed workspace.

---

## Blast Radius

**Delete entirely:**
- `web/app/approvals/page.tsx`
- `web/components/approvals/ApprovalsInbox.tsx`
- `web/components/approvals/__tests__/ApprovalsInbox.test.tsx`

**Modify:**
- `web/lib/ui-model.ts`
- `web/lib/feed-slice-approval-api.ts`
- `web/components/Topbar.tsx`
- `web/components/__tests__/Topbar.test.tsx`
- `engine/src/migrations_engine/routes/feed_slice_approval.py`
- `engine/src/migrations_engine/management/feeds.py`
- `engine/src/migrations_engine/api/schemas.py`

---

## File Changes

### 1. Delete frontend pages and components

```
web/app/approvals/page.tsx                              → delete
web/components/approvals/ApprovalsInbox.tsx             → delete
web/components/approvals/__tests__/ApprovalsInbox.test.tsx → delete
```

### 2. `web/lib/ui-model.ts`

Remove the `{ label: "Approvals", href: "/approvals" }` entry from both role branches:

```typescript
// Before
if (role === "central_team") {
  return [...common, { label: "Approvals", href: "/approvals" }, { label: "Admin", href: "/admin" }];
}
if (role === "project_stakeholder") {
  return [...common, { label: "Approvals", href: "/approvals" }];
}

// After
if (role === "central_team") {
  return [...common, { label: "Admin", href: "/admin" }];
}
if (role === "project_stakeholder") {
  return common;
}
```

### 3. `web/lib/feed-slice-approval-api.ts`

Remove these exports and all code that exists only for them:
- `FeedSliceApprovalItem` interface
- `FeedSliceApprovalCount` interface
- `listPendingApprovals` function
- `getPendingApprovalCount` function

Keep:
- `FeedSliceApprovalApiError` class
- `approveFeedSlice` function
- `rejectFeedSlice` function
- `resubmitFeedSlice` function
- `requestJson`, `parseApiError`, `authHeaders` internal helpers (still used by the kept functions)

### 4. `web/components/Topbar.tsx`

Remove:
- `import { getPendingApprovalCount } from "../lib/feed-slice-approval-api";`
- `const [approvalCount, setApprovalCount] = useState<number | null>(null);`
- The `useEffect` block that calls `getPendingApprovalCount`
- The `.map()` call that adds the badge to the Approvals item (it now does nothing useful — simplify `items` back to `navItemsForRole(role)` directly)

Result: `items` becomes `navItemsForRole(role)` with no badge logic needed. The Approvals item is gone from `navItemsForRole`, so the badge code has nothing to attach to.

### 5. `web/components/__tests__/Topbar.test.tsx`

Remove tests that:
- Assert the "Approvals" link is present in the nav
- Assert the approval count badge renders when `getPendingApprovalCount` resolves with a count
- Mock `getPendingApprovalCount`

Keep tests that cover logout, nav structure for other items, role-based visibility.

---

### 6. `engine/src/migrations_engine/routes/feed_slice_approval.py`

Remove the two global GET route handlers:

```python
# Remove these two handlers entirely:

@router.get("/approvals", response_model=list[FeedSliceApprovalItemResponse])
def get_approvals(...): ...

@router.get("/approvals/count", response_model=FeedSliceApprovalCountResponse)
def get_approvals_count(...): ...
```

Remove the now-unused imports:
- `FeedSliceApprovalCountResponse`
- `FeedSliceApprovalItemResponse`
- `count_pending_approvals`
- `list_pending_approvals`

The file stays; the router stays registered. The three POST handlers (approve, reject, resubmit) are unchanged.

### 7. `engine/src/migrations_engine/management/feeds.py`

Remove:
- `list_pending_approvals()` function (lines ~175–237)
- `count_pending_approvals()` function (lines ~240–249)
- The two schema imports at the top: `FeedSliceApprovalCountResponse`, `FeedSliceApprovalItemResponse`

Keep all other functions unchanged.

### 8. `engine/src/migrations_engine/api/schemas.py`

Remove:
- `FeedSliceApprovalItemResponse` class (lines ~264–285)
- `FeedSliceApprovalCountResponse` class (lines ~287–290)

---

## Tests

- [ ] Run full test suite after each frontend file deletion to catch any remaining import references.
- [ ] `Topbar.test.tsx`: no approval-related assertions remain; all kept tests pass.
- [ ] `ui-model.ts` tests (if any): no "Approvals" link expected for any role.
- [ ] Backend: `pytest engine/tests/` — all pass. Confirm no test imports `list_pending_approvals` or `count_pending_approvals`.

---

## Verification

- Navigate to `/approvals` → 404.
- Load any project page → Topbar has no "Approvals" link for any role.
- Topbar makes no request to `/approvals/count`.
- Call `POST .../slices/{id}/approve` via curl/Postman → still returns 200.
- Call `GET /approvals` → 404 (route removed).

---

## Pitfalls

- `feed_slice_approval.py` stays as a file — only two routes are removed, not the file. Deleting the file would also remove the approve/reject/resubmit routes.
- Check if `ApprovalsInbox.tsx` is imported anywhere beyond `approvals/page.tsx` before deleting.
- The `approvals/` directory under `web/app` should be fully deleted (the page is the only file in it).
- `FeedSliceApprovalItemResponse` and `FeedSliceApprovalCountResponse` are imported in both `feeds.py` and `feed_slice_approval.py` — remove from both.

---

## Commit

- `chore(001bg): remove global approvals inbox and top-nav badge`
