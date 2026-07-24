# Plan: Task 001gq — Fix camelCase Inner-Key Bug in `add_source_value`/`remove_source_value`/`move_source_value` PATCH Actions

- **Task**: [001gq-lookup-patch-inner-key-casing-bug.md](file:///Users/vjkotra/projects/katana/tasks/001gq-lookup-patch-inner-key-casing-bug.md)

---

## Goal Description

`patchLookupValueMap` in `web/lib/lookup-api.ts` snake_cases the *outer* PATCH body key (`add_source_value`, `remove_source_value`, `move_source_value`) but forwards the *inner* action object unchanged, still keyed in camelCase (`destId`, `sourceValue`, `oldDestId`, `newDestId`). The backend reads snake_case keys off those inner dicts via plain `dict.get(...)` with `""` defaults and no schema validation, so the mismatch is swallowed silently: the PATCH returns `200 OK`, nothing changes in the DB, and the UI shows a false success toast. This is why "+ Add another source value" (and the `×` remove button) appear to do nothing.

Fix is frontend-only, one function, three call sites, plus fixing three tests that currently assert the buggy shape as correct.

---

## Step-by-Step Build Instructions (Agent Executable)

### Step 1 (TDD): Flip the three existing tests in `lookup-api.test.ts` to assert correct behavior first

**File**: [web/lib/lookup-api.test.ts](file:///Users/vjkotra/projects/katana/web/lib/lookup-api.test.ts)

These three tests currently assert the *buggy* camelCase inner-key shape. Update each to assert the snake_case shape the backend actually requires. Running the suite after this step (and before Step 2) should FAIL — that confirms the tests correctly detect the bug.

```diff
     it("sends addSourceValue as add_source_value in the request body", async () => {
       ...
       await patchLookupValueMap("token-1", "project-1", "map-1", {
         addSourceValue: { destId: "ACTIVE", sourceValue: "active_status" },
       });

       expect(fetchMock).toHaveBeenCalledWith(
         `${BASE}/projects/project-1/lookup-maps/map-1`,
         expect.objectContaining({
           method: "PATCH",
           body: JSON.stringify({
-            add_source_value: { destId: "ACTIVE", sourceValue: "active_status" },
+            add_source_value: { dest_id: "ACTIVE", source_value: "active_status" },
           }),
         }),
       );
     });
```

```diff
     it("sends removeSourceValue as remove_source_value (snake_case) in the request body", async () => {
       ...
       await patchLookupValueMap("token-1", "project-1", "map-1", {
         removeSourceValue: { destId: "ACTIVE", sourceValue: "old_alias" },
       });

       expect(fetchMock).toHaveBeenCalledWith(
         `${BASE}/projects/project-1/lookup-maps/map-1`,
         expect.objectContaining({
           method: "PATCH",
           body: JSON.stringify({
-            remove_source_value: { destId: "ACTIVE", sourceValue: "old_alias" },
+            remove_source_value: { dest_id: "ACTIVE", source_value: "old_alias" },
           }),
         }),
       );
     });
```

```diff
     it("sends moveSourceValue as move_source_value in the request body", async () => {
       ...
       await patchLookupValueMap("token-1", "project-1", "map-1", {
         moveSourceValue: { sourceValue: "A", oldDestId: "OLD", newDestId: "ACTIVE" },
       });

       expect(fetchMock).toHaveBeenCalledWith(
         `${BASE}/projects/project-1/lookup-maps/map-1`,
         expect.objectContaining({
           method: "PATCH",
           body: JSON.stringify({
-            move_source_value: { sourceValue: "A", oldDestId: "OLD", newDestId: "ACTIVE" },
+            move_source_value: { source_value: "A", old_dest_id: "OLD", new_dest_id: "ACTIVE" },
           }),
         }),
       );
     });
```

Run `cd web && npm test -- --run lookup-api.test.ts` now and confirm these three tests FAIL against the current implementation. This is the required failing-test checkpoint before touching implementation code.

---

### Step 2: Fix the inner-key serialization in `patchLookupValueMap`

**File**: [web/lib/lookup-api.ts](file:///Users/vjkotra/projects/katana/web/lib/lookup-api.ts)

```diff
   const body: Record<string, unknown> = {};
   if (input.sourceValueMap) body.source_value_map = input.sourceValueMap;
   if (input.destinationMappings) body.destination_mappings = input.destinationMappings;
-  if (input.addSourceValue) body.add_source_value = input.addSourceValue;
-  if (input.removeSourceValue) body.remove_source_value = input.removeSourceValue;
-  if (input.moveSourceValue) body.move_source_value = input.moveSourceValue;
+  if (input.addSourceValue) {
+    body.add_source_value = {
+      dest_id: input.addSourceValue.destId,
+      source_value: input.addSourceValue.sourceValue,
+    };
+  }
+  if (input.removeSourceValue) {
+    body.remove_source_value = {
+      dest_id: input.removeSourceValue.destId,
+      source_value: input.removeSourceValue.sourceValue,
+    };
+  }
+  if (input.moveSourceValue) {
+    body.move_source_value = {
+      source_value: input.moveSourceValue.sourceValue,
+      old_dest_id: input.moveSourceValue.oldDestId,
+      new_dest_id: input.moveSourceValue.newDestId,
+    };
+  }
```

Run `cd web && npm test -- --run lookup-api.test.ts` again — all three tests (and the rest of the file) should now pass.

---

### Step 3: Full frontend regression pass

```bash
cd web && npm test -- --run
```

All existing suites must remain green — in particular `LookupMappingTable.test.tsx` and `ReviewGrid.test.tsx`, since they exercise the same add/remove callback chain (they mock the callback prop directly, so they were never sensitive to this bug, but must not regress).

---

### Step 4: Manual end-to-end verification (cannot be substituted with unit tests alone — this bug specifically only manifests when a real request round-trips to the real backend)

1. Start the backend (`engine`) and frontend (`web`) dev servers.
2. As the role currently holding the ball on a draft lookup map, open the Review Page for a feed with at least one lookup binding.
3. Click "+ Add another source value" on a destination group, type a new alias (e.g. `"TESTVAL"`), submit.
4. Confirm the success toast appears, **then reload the page** and confirm `"TESTVAL"` is still listed under that destination group. (Before the fix: it would disappear on reload because it was never persisted — the toast was a false positive.)
5. Click the `×` next to a source value, confirm it disappears, **reload**, and confirm it's still gone.

---

## Verification Plan

```bash
cd web && npm test -- --run
```

Manual steps in Step 4 above are required — this bug's defining symptom (silent no-op, false success toast) is specifically about the real network round-trip and cannot be fully proven by mocked-fetch unit tests alone, though the corrected unit tests in Step 1 do lock in the wire-format contract going forward.
