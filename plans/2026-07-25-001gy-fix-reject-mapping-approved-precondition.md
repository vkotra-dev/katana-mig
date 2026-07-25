Task: tasks/001gy-fix-reject-mapping-approved-precondition.md
Domain: docs/domain/source-model.md

## Current State

- `reject_mapping()` (`engine/src/migrations_engine/mapping/review.py`, lines 435-483) filters on `MappingSnapshot.status == "draft"` in both branches (scoped, line 452; bulk, line 463). Confirmed by direct read, not assumed.
- `review/page.tsx`'s "Reject" button (search `onClick={handleReject}`) only renders when `(role === "pm" || role === "admin") && aggregateStatus === "approved"` — confirmed via `grep -n "handleReject\|aggregateStatus ===" "web/app/projects/[id]/feeds/[feedId]/review/page.tsx"`, which shows `handleReject` appears at exactly one render site, gated on that condition.
- `.venv/bin/python -m pytest engine/tests -q` currently shows **2 failed, 400 passed**. `cd web && npm test -- --run` currently shows **2 test files failed, 68 passed (70); 1 test failed, 321 passed (322)** — note the file-count drop (337→322 total individual tests) is from `review/page.test.tsx` failing to load at all, not from a single assertion failure.
- No DB schema/model change anywhere in this task — invariant I18 (hand-written migration for every DDL change) does not apply.
- `engine/tests/test_mapping_review_api.py` has fixtures `admin_token` (role is actually `CENTRAL_TEAM_ROLE`, despite the name — confirmed by reading the fixture) and `stakeholder_token`. Neither is PM/Admin. `test_unapprove_mapping_by_pm` (lines 457-516) is the only existing test in this file that seeds a PM-role user inline and logs in as them — use `ADMIN_ROLE` instead for this task's new test, since `ADMIN_ROLE` bypasses the `pm_user_id`/`ProjectRegistry` wiring PM role needs (`engine/src/migrations_engine/management/access.py:61-68`), so no `registry.pm_user_id` update step is required.

## Objective

Change `reject_mapping()` to operate on `approved` snapshots (matching the only state its UI trigger is ever reachable from), repair the two backend tests that broke as a side effect of the `492684f` split (by giving one of them to its correct new home — `request_revision` — rather than patching it to fit the wrong endpoint), add the missing test coverage for both new functions, and fix the two purely mechanical frontend test breakages (a missing destructured variable, a stale mock response body).

## Out of Scope

- Do NOT touch `request_revision()`'s logic — it's correct as-is (confirmed by direct read); this task only repurposes an existing test to point at it.
- Do NOT add a "resolve"/reassign UI for rejected snapshots, or any new workflow state beyond what already exists (`draft`/`approved`/`rejected`) — not asked for, out of scope.
- Do NOT touch `unapprove_mapping()` or its route — unrelated to this task, verified working (`test_unapprove_mapping_by_pm` is not in the failing set).
- Do NOT modify `LookupValueMapResponse.status`'s `"discarded"` literal or anything in the lookup-value-map domain — this task is entirely about table/field mapping (`MappingSnapshot`), same scope boundary as tasks 001gw/001gx.
- Do NOT change the two small, unrelated commits that landed alongside this work (`f8ad624` sign-off guard, `731ad19` button styling) — verified real and correct during review, nothing to do here.

## Blast Radius

| File | Action | What changes |
|------|--------|-------------|
| `engine/src/migrations_engine/mapping/review.py` | modify | `reject_mapping()`'s two `status == "draft"` filters → `status == "approved"`; error message text |
| `engine/tests/test_mapping_review_api.py` | modify | repurpose `test_reject_marks_snapshot_rejected` → tests `request_revision`; add new `reject_mapping` test; fix `test_bulk_approve_and_reject_multiple_snapshots`'s auth + remove DB-mutation hack |
| `web/app/projects/[id]/feeds/[feedId]/review/page.test.tsx` | modify | add missing `rejectMappingSnapshotMock,` to destructuring list; add one new test for the approved-state Reject click |
| `web/lib/mapping-api.test.ts` | modify | fix stale `status: "rejected"` → `status: "draft"` in the chained mock response body |

## File Changes

### `engine/src/migrations_engine/mapping/review.py`

Search for `def reject_mapping`:

```diff
     if destination_object_name:
         snapshots = db.scalars(
             select(MappingSnapshot)
             .where(
                 MappingSnapshot.project_id == project_id,
                 MappingSnapshot.source_definition_id == source_definition_id,
                 MappingSnapshot.destination_object_name == destination_object_name,
-                MappingSnapshot.status == "draft",
+                MappingSnapshot.status == "approved",
             )
             .order_by(MappingSnapshot.created_at.desc(), MappingSnapshot.mapping_snapshot_id.desc())
             .limit(1)
         ).all()
     else:
         snapshots = db.scalars(
             select(MappingSnapshot)
             .where(
                 MappingSnapshot.project_id == project_id,
                 MappingSnapshot.source_definition_id == source_definition_id,
-                MappingSnapshot.status == "draft",
+                MappingSnapshot.status == "approved",
             )
             .order_by(MappingSnapshot.destination_object_name.asc())
         ).all()
 
     if not snapshots:
-        msg = "No draft mapping snapshots exist to reject."
+        msg = "No approved mapping snapshots exist to reject."
         raise AuthApiError("mapping_not_found", msg, 404)
```

Do not touch anything below this point in the function (the `for snapshot in snapshots:` loop that sets `status = "rejected"` and `current_ball_role = None` is already correct).

### `engine/tests/test_mapping_review_api.py`

**Repurpose** `test_reject_marks_snapshot_rejected` (search for that exact function name — it currently spans lines 518-537):

```diff
-def test_reject_marks_snapshot_rejected(monkeypatch: pytest.MonkeyPatch, admin_token: str, stakeholder_token: str) -> None:
+def test_request_revision_marks_snapshot_draft_and_returns_ball_to_operator(
+    monkeypatch: pytest.MonkeyPatch, admin_token: str, stakeholder_token: str
+) -> None:
     project_id, source_id = _seed_project()
     fake = FakeAdapter([
         {"source_field": "customer_id", "destination_field": "customer_id"},
     ])
     monkeypatch.setattr(mapping_proposal_module, "get_adapter", lambda task: fake)
 
     client.post(
         f"/projects/{project_id}/sources/{source_id}/mapping/propose",
         headers={"Authorization": f"Bearer {admin_token}"},
     )
 
     response = client.post(
-        f"/projects/{project_id}/sources/{source_id}/mapping/reject",
+        f"/projects/{project_id}/sources/{source_id}/mapping/revision",
         headers={"Authorization": f"Bearer {stakeholder_token}"},
         json={"reason": "Needs another source field mapped."},
     )
 
     assert response.status_code == 200, response.text
-    assert response.json()["status"] == "rejected"
+    assert response.json()["status"] == "draft"
+    assert response.json()["current_ball_role"] == "central_team"
```

**Add** a genuinely new test for `reject_mapping()` right after the repurposed test above. Follow this exact pattern (uses `ADMIN_ROLE`, imported already at the top of the file per `from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE, PM_ROLE` — add `ADMIN_ROLE` to that import line too):

```python
def test_reject_marks_approved_snapshot_rejected_and_clears_ball(
    monkeypatch: pytest.MonkeyPatch, admin_token: str, stakeholder_token: str
) -> None:
    project_id, source_id = _seed_project()
    fake = FakeAdapter([
        {"source_field": "customer_id", "destination_field": "customer_id"},
    ])
    monkeypatch.setattr(mapping_proposal_module, "get_adapter", lambda task: fake)

    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    approve = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/approve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"

    with SessionLocal() as db:
        admin_user = db.scalar(select(User).where(User.email == "admin_role_test@example.com"))
        if not admin_user:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email="admin_role_test@example.com",
                    display_name="Admin Role Test",
                    password_hash=hash_password("admin-password"),
                    role=ADMIN_ROLE,
                    status="active",
                )
            )
            db.commit()
    admin_role_token = _login("admin_role_test@example.com", "admin-password")

    reject = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/reject",
        headers={"Authorization": f"Bearer {admin_role_token}"},
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["status"] == "rejected"
    assert reject.json()["current_ball_role"] is None

    # A stakeholder can no longer request revision or approve a rejected snapshot,
    # and reject_mapping should find nothing left to reject a second time.
    reject_again = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/reject",
        headers={"Authorization": f"Bearer {admin_role_token}"},
    )
    assert reject_again.status_code == 404
```

Verify `_login` and `hash_password` are already imported/available in this file (they are — used throughout, e.g. in `test_unapprove_mapping_by_pm`) before assuming this compiles as-is.

**Fix** `test_bulk_approve_and_reject_multiple_snapshots` (search for that function name). Remove the manual draft-revert hack and switch to an admin-role token for the reject call:

```diff
     with SessionLocal() as db:
         snapshots = db.scalars(
             select(mapping_review_module.MappingSnapshot)
             .where(
                 mapping_review_module.MappingSnapshot.project_id == project_id,
                 mapping_review_module.MappingSnapshot.source_definition_id == source_id,
             )
         ).all()
         assert len(snapshots) == 2
         for s in snapshots:
             assert s.status == "approved"
-            # Revert to draft for testing reject
-            s.status = "draft"
-        db.commit()
+        # No DB mutation needed — reject_mapping operates on approved snapshots directly.
 
     # 3. Reject all (bulk reject)
+    with SessionLocal() as db:
+        admin_user = db.scalar(select(User).where(User.email == "bulk_admin_test@example.com"))
+        if not admin_user:
+            db.add(
+                User(
+                    user_id=str(uuid.uuid4()),
+                    email="bulk_admin_test@example.com",
+                    display_name="Bulk Admin Test",
+                    password_hash=hash_password("bulk-admin-password"),
+                    role=ADMIN_ROLE,
+                    status="active",
+                )
+            )
+            db.commit()
+    bulk_admin_token = _login("bulk_admin_test@example.com", "bulk-admin-password")
+
     resp_reject = client.post(
         f"/projects/{project_id}/sources/{source_id}/mapping/reject",
-        headers={"Authorization": f"Bearer {stakeholder_token}"},
-        json={"reason": "Bulk rejection test"}
+        headers={"Authorization": f"Bearer {bulk_admin_token}"},
     )
     assert resp_reject.status_code == 200
```

Note this test's `db.commit()` was removed from inside the first `with SessionLocal()` block since nothing is mutated there anymore (only assertions) — double check no other code after that block depended on that commit having happened; skim the rest of the test to confirm before finalizing this edit.

### `web/app/projects/[id]/feeds/[feedId]/review/page.test.tsx`

Search for the destructuring assignment starting `const {` near the top of the file (lines 5-25):

```diff
 const {
   loadUiSessionMock,
   getAllApprovedMappingSnapshotsMock,
   listLookupValueMapsMock,
   approveMappingSnapshotMock,
   requestRevisionMock,
+  rejectMappingSnapshotMock,
   unapproveMappingSnapshotMock,
   patchMappingSnapshotMock,
   listFeedSlicesMock,
   getFeedContractMock,
   listFeedFibersMock,
   listFeedCommentsMock,
   createFeedCommentMock,
   getSignOffStatusMock,
   signBindingMock,
   unsignBindingMock,
   signLookupMock,
   unsignLookupMock,
   pushForReviewMock,
   pokeReviewerMock,
   routerPushMock,
 } = vi.hoisted(() => ({
```

This is the entire fix for the "file fails to load" problem — `rejectMappingSnapshotMock` is already correctly present in the `vi.hoisted()` factory body and in the later `vi.mock(...)` factory; it was only ever missing from this one destructuring list.

**Add** a new test exercising the Reject button from the approved state. Find an existing test that renders the page with `aggregateStatus` effectively `"approved"` (search for `status: "approved"` in this file to find the right mock-data shape to copy) and add a sibling test:

```tsx
it("calls rejectMappingSnapshot when PM/Admin clicks Reject on an approved mapping", async () => {
  // Use the same session/role and approved-snapshot mock shape as the existing
  // "Revert to Draft" test in this file — search for it and copy its setup
  // exactly, since aggregateStatus === "approved" must be true for the Reject
  // button to render at all.
  // ... render page, find the "Reject" button, fireEvent.click it ...
  await waitFor(() => {
    expect(rejectMappingSnapshotMock).toHaveBeenCalled();
  });
});
```

Do not guess the exact session/role mock shape — find the existing "Revert to Draft" test in this same file (search `handleRevertToDraft` or `"Revert to Draft"`) and copy its render setup precisely, since it already establishes the exact conditions (`role === "pm" || "admin"`, `aggregateStatus === "approved"`) needed for the Reject button to exist in the DOM at all.

### `web/lib/mapping-api.test.ts`

Search for `status: "rejected",` (there should be exactly one match, inside the 4th chained `mockResolvedValueOnce` body, around line 180):

```diff
           field_bindings: [
             {
               source_field: "cust_id",
               destination_field: "customer_id",
               lookup_name: null,
             },
           ],
-          status: "rejected",
+          status: "draft",
           approved_at: null,
           approved_by_user_id: null,
```

## Tests

Covered inline above — three backend test changes (one repurposed, one new, one repaired) and two frontend test changes (one destructuring fix + one new test, one stale-value fix). No additional test files needed.

## Verification

```bash
# Confirm current broken baseline before making any change
.venv/bin/python -m pytest engine/tests -q
cd web && npm test -- --run
cd ..

# After changes
.venv/bin/python -m pytest engine/tests -q
cd web && npm test -- --run
```

Expected after changes: zero failures in both. Backend count should be 400 (current passing) + 1 new test = 401, with the 2 previously-failing tests now passing (one repurposed, one fixed) — net effect is 401 passed, 0 failed, not a simple "+1" from the prior *passing* count since 2 previously-failing tests are being fixed in place, not removed. Frontend: 322 (current, with the broken file not loading) → 337 (prior full baseline, file loads again) + 1 new test = 338 passed, 0 failed. Do not report either number without having actually run the command in the same turn — this exact class of unverified claim is what this task exists to fix.

## Pitfalls

- Do NOT "fix" the two failing backend tests by just changing their token to a PM/Admin one while leaving the reject precondition on `"draft"` — that would hide the real bug (the button's unreachable precondition) behind tests that no longer represent the actual UI flow. The backend filter change (draft→approved) is the primary fix; the tests must reflect the corrected behavior, not paper over the old one.
- Do NOT reuse `admin_token`/`stakeholder_token` for the new `reject_mapping` tests — neither has PM/Admin role (confirmed: `admin_token`'s underlying user has `role=CENTRAL_TEAM_ROLE`, a naming trap already present in this file). Seed a dedicated user with `ADMIN_ROLE` per the pattern shown above.
- Do NOT skip verifying `rejectMappingSnapshotMock`'s destructuring fix in isolation before moving on — run just that one test file first (`npm test -- --run app/projects/[id]/feeds/[feedId]/review/page.test.tsx`) to confirm the file loads before assuming the rest of the suite is unaffected.
- Do NOT report pass/fail counts from memory or from a previous run in this task. Every verification claim in this task's completion summary must come from a command executed in that same turn.

## Commit

```
fix(mapping): reject approved snapshots, not draft; repair tests broken by the request-revision/reject split
```
