Task: tasks/001gw-table-mapping-drop-toggle-backend.md
Domain: docs/domain/source-model.md

## Current State

- `MappingSnapshot.field_bindings` (`engine/src/migrations_engine/db/models.py`) is an existing `JSON` column — a list of dicts, each currently shaped `{source_field, destination_field, lookup_name, binding_type, reference_table_name, destination_data_type, nullable}`. **No new DB column or migration is needed for this task** — `dropped` is a new *key* inside the existing JSON blob, not a schema/DDL change, so invariant I18 (hand-written Alembic migration for every DDL change) does not apply here.
- `patch_mapping` (`engine/src/migrations_engine/mapping/review.py:59-152`) does a hard delete today: it fully overwrites `snapshot.field_bindings` with whatever the client sends (line 137, `snapshot.field_bindings = new_bindings`). Anything the client omits is permanently gone. `MappingBindingSignOff` rows for any pair no longer present in the new list are deleted (lines 110-135, via `changed_pairs` detection keyed on `(source_field, destination_field)`).
- The Review Page's × button (`ReviewGrid.tsx:526-535`) currently drives this hard-delete path via `handleRemoveSourceField` (`review/page.tsx:360-386`), which filters the dropped field out of the array before PATCHing. That frontend behavior is task 001gx's responsibility, not this task's — this task only needs to define and honor the *contract* 001gx will use (send the full bindings list with one field's flag flipped, never a filtered-down list).
- `mapping/proposal.py`'s re-propose/merge path (`propose_mapping`, merge block at lines 250-282) already has an *unrelated* concept also loosely called "dropped" — a comment at line 268, "Keep signed-off bindings that the AI dropped," refers to the AI's fresh re-proposal simply omitting a pair. That is not this task's `dropped` flag. Do not conflate the two.
- Codegen (`engine/src/migrations_engine/codegen/service.py` and `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2`) reads `mapping_snapshot.field_bindings` directly at 4 confirmed sites (traced by grep, not assumed) with zero awareness of any "excluded" concept, since none exists yet.
- Existing test coverage for `patch_mapping` lives in `engine/tests/test_mapping_review_api.py` (uses `_seed_project()`, `FakeAdapter`, direct `MappingBindingSignOff` DB manipulation). Existing test coverage for codegen generation lives in `engine/tests/test_codegen_service_api.py` (its `FakeAdapter.call(self, system, user, response_model)` captures the *rendered* `user_prompt.txt.j2` text as `self.calls[i].user` — this is how Step "Tests" below verifies the Jinja template fix without a separate rendering harness).
- **Scope note**: this is the table/field mapping domain (`MappingSnapshot`), not the lookup value mapping domain (`LookupValueMap`, already covered by tasks 001gq-001gu). Do not touch `LookupMappingTable.tsx` or any `lookup_mapping.py`/`LookupValueMap` code in this task.

## Objective

Add a `dropped: bool` flag to table-mapping field bindings so "drop source field" becomes a soft-delete toggle instead of a hard delete, and make every reader of `field_bindings` (4 codegen sites, most critically the Jinja prompt template the SQL-generation AI reads) correctly skip flagged-dropped bindings — so a toggled-off field is genuinely excluded from generated migration SQL, not just hidden from the UI.

## Out of Scope

- Do NOT touch `LookupMappingTable.tsx`, `lookup_mapping.py`, or any `LookupValueMap` model/schema/route code — that's the lookup-value-mapping domain, unrelated to table/field mapping, already handled by tasks 001gq-001gu.
- Do NOT modify the `# Keep signed-off bindings that the AI dropped` block in `mapping/proposal.py` (around line 268-274) — that is the unrelated AI-omission concept described in Current State; only the merge block a few lines above it (lines 258-266) needs a change.
- Do NOT write a database migration — this task adds a JSON key, not a schema column. If you find yourself writing an Alembic file for this task, stop — you've misread the task.
- Do NOT build any frontend UI in this task — that's 001gx, gated on this task's completion.
- Do NOT change `patch_mapping`'s `changed_pairs`/sign-off-deletion logic itself — it already works correctly for this task's purposes (keyed on `(source_field, destination_field)`, unaffected by a `dropped` flip on an existing pair). Only the `new_bindings` dict construction needs to carry the new field through.

## Blast Radius

| File | Action | What changes |
|------|--------|-------------|
| `engine/src/migrations_engine/api/schemas.py` | modify | `MappingFieldBindingResponse.dropped: bool = False` |
| `engine/src/migrations_engine/mapping/snapshots.py` | modify | `FieldBinding.dropped: bool = False`; serialization includes it |
| `engine/src/migrations_engine/mapping/review_repository.py` | modify | `snapshot_to_response`'s `MappingFieldBindingResponse(...)` construction includes `dropped` |
| `engine/src/migrations_engine/mapping/review.py` | modify | `patch_mapping`'s `new_bindings.append({...})` includes `"dropped": binding.dropped` |
| `engine/src/migrations_engine/mapping/proposal.py` | modify | merge logic carries `dropped` forward for surviving pairs, independent of sign-off status |
| `engine/src/migrations_engine/codegen/service.py` | modify | 3 read-sites gain a `not binding.get("dropped")` filter |
| `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2` | modify | field-bindings loop gains `if not binding.get('dropped')` |
| `engine/tests/test_mapping_review_api.py` | modify | 2 new tests (sign-off preservation, re-propose preservation) |
| `engine/tests/test_codegen_service_api.py` | modify | 2 new tests (required-field-drop 422, rendered-prompt exclusion) |
| `docs/domain/source-model.md` | modify | document the `dropped` flag under "Field mapping" per invariant I22, once this task and 001gx are both complete |

## File Changes

### `engine/src/migrations_engine/api/schemas.py`

Search for `class MappingFieldBindingResponse`:

```diff
 class MappingFieldBindingResponse(BaseModel):
     source_field: str
     destination_field: str
     lookup_name: str | None
     binding_type: str | None = None
     reference_table_name: str | None = None
     destination_table_name: str | None = None
     destination_data_type: str | None = None
     nullable: bool | None = None
+    dropped: bool = False
```

This single model is reused for both the PATCH request body (`MappingPatchRequest.field_bindings: list[MappingFieldBindingResponse]`) and every response — one change covers both directions.

### `engine/src/migrations_engine/mapping/snapshots.py`

```diff
 @dataclass(frozen=True)
 class FieldBinding:
     source_field: str
     destination_field: str
     lookup_name: str
+    dropped: bool = False
```

```diff
     serialized_bindings = [
         {
             "source_field": binding.source_field,
             "destination_field": binding.destination_field,
             "lookup_name": binding.lookup_name,
+            "dropped": binding.dropped,
         }
         for binding in field_bindings
     ]
```

(`create_approved_mapping_snapshot`, mostly used by test fixtures — the dataclass default means every existing call site keeps compiling unchanged.)

### `engine/src/migrations_engine/mapping/review_repository.py`

Search for `MappingFieldBindingResponse(` inside `snapshot_to_response`:

```diff
             MappingFieldBindingResponse(
                 source_field=str(binding.get("source_field", "")),
                 destination_field=str(binding.get("destination_field", "")),
                 lookup_name=binding.get("lookup_name"),
                 binding_type=binding.get("binding_type"),
                 reference_table_name=binding.get("reference_table_name"),
                 destination_table_name=binding.get("destination_table_name"),
                 destination_data_type=binding.get("destination_data_type"),
                 nullable=binding.get("nullable"),
+                dropped=bool(binding.get("dropped", False)),
             )
```

### `engine/src/migrations_engine/mapping/review.py`

Search for `new_bindings.append({`:

```diff
         new_bindings.append({
             "source_field": binding.source_field,
             "destination_field": binding.destination_field,
             "lookup_name": binding.lookup_name,
             "binding_type": existing.get("binding_type", "direct"),
             "reference_table_name": existing.get("reference_table_name"),
             "destination_data_type": existing.get("destination_data_type"),
             "nullable": existing.get("nullable"),
+            "dropped": binding.dropped,
         })
```

No other change needed in this function — confirm `existing_by_pair = {(b.get("source_field")` keys purely on the pair tuple before relying on this.

### `engine/src/migrations_engine/mapping/proposal.py`

Search for `# Keep old binding for core fields, but overlay new keys for forward compatibility`:

```diff
             merged_bindings = []
             for fresh_b in fresh_bindings:
                 pair = (fresh_b["source_field"], fresh_b["destination_field"])
                 is_signed_off = (existing_draft.mapping_snapshot_id, pair[0], pair[1]) in signed_off_pairs
                 if is_signed_off and pair in old_bindings_map:
                     # Keep old binding for core fields, but overlay new keys for forward compatibility
                     merged_bindings.append({**fresh_b, **old_bindings_map[pair]})
                 else:
+                    # Carry forward the dropped flag even when not signed off — dropped
+                    # (user soft-delete) and signed-off are independent state; a re-propose
+                    # must not silently un-drop a field the user excluded.
+                    if pair in old_bindings_map and "dropped" in old_bindings_map[pair]:
+                        fresh_b = {**fresh_b, "dropped": old_bindings_map[pair]["dropped"]}
                     merged_bindings.append(fresh_b)
```

Do not touch the `# Keep signed-off bindings that the AI dropped` block below this (~line 268-274) — unrelated concept, out of scope.

### `engine/src/migrations_engine/codegen/service.py`

Search for `mapped_dest_fields = {`:

```diff
     mapped_dest_fields = {
         binding.get("destination_field")
         for binding in mapping_snapshot.field_bindings
-        if binding.get("destination_field")
+        if binding.get("destination_field") and not binding.get("dropped")
     }
```

Search for `def _select_lookup_snapshot_version`, then its `lookup_names = sorted({...})` block:

```diff
     lookup_names = sorted(
         {
             str(binding.get("lookup_name"))
             for binding in mapping_snapshot.field_bindings
-            if binding.get("lookup_name")
+            if binding.get("lookup_name") and not binding.get("dropped")
         }
     )
```

Search for `def _build_lookup_tables`, then its own near-identical `lookup_names = sorted({...})` block (a *different* function from the one above — both need the edit, do not edit the same one twice):

```diff
     lookup_names = sorted(
         {
             str(binding.get("lookup_name"))
             for binding in mapping_snapshot.field_bindings
-            if binding.get("lookup_name")
+            if binding.get("lookup_name") and not binding.get("dropped")
         }
     )
```

### `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2`

```diff
 Field bindings:
-{% for binding in mapping_snapshot.field_bindings %}
+{% for binding in mapping_snapshot.field_bindings if not binding.get('dropped') %}
 - {{ binding.get('source_field') }} -> {{ binding.get('destination_field') }}{% if binding.get('destination_data_type') %} [{{ binding.get('destination_data_type') }}]{% endif %} (lookup: {{ binding.get('lookup_name') or 'none' }})
 {% endfor %}
```

This is the field-mapping list the SQL-generation AI actually reads. This is the single most important edit in this task — everything else is validation/plumbing, this is the one that actually keeps a dropped field out of generated SQL.

## Tests

### `engine/tests/test_mapping_review_api.py`

Add after `test_patch_removing_signed_off_binding_deletes_its_sign_off_row` (search for that function name):

```python
def test_patch_toggling_dropped_preserves_sign_off(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    project_id, source_id = _seed_project()
    fake = FakeAdapter([
        {"source_field": "customer_id", "destination_field": "customer_id"},
    ])
    monkeypatch.setattr(mapping_proposal_module, "get_adapter", lambda task: fake)

    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    from migrations_engine.db.models import MappingBindingSignOff, MappingSnapshot

    with SessionLocal() as db:
        snapshot = db.scalar(select(MappingSnapshot).where(MappingSnapshot.project_id == project_id))
        assert snapshot is not None
        snapshot_id = snapshot.mapping_snapshot_id
        admin_user = db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE))
        assert admin_user is not None
        db.add(
            MappingBindingSignOff(
                mapping_snapshot_id=snapshot_id,
                destination_object_name=snapshot.destination_object_name,
                source_field="customer_id",
                destination_field="customer_id",
                user_id=admin_user.user_id,
                role=CENTRAL_TEAM_ROLE,
            )
        )
        db.commit()

    response = client.patch(
        f"/projects/{project_id}/sources/{source_id}/mapping",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "field_bindings": [
                {"source_field": "customer_id", "destination_field": "customer_id", "lookup_name": None, "dropped": True},
            ]
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["field_bindings"][0]["dropped"] is True

    with SessionLocal() as db:
        remaining = db.scalars(
            select(MappingBindingSignOff).where(
                MappingBindingSignOff.mapping_snapshot_id == snapshot_id,
                MappingBindingSignOff.source_field == "customer_id",
                MappingBindingSignOff.destination_field == "customer_id",
            )
        ).all()
        assert len(remaining) == 1, "sign-off must survive a dropped=true toggle"

    response2 = client.patch(
        f"/projects/{project_id}/sources/{source_id}/mapping",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "field_bindings": [
                {"source_field": "customer_id", "destination_field": "customer_id", "lookup_name": None, "dropped": False},
            ]
        },
    )
    assert response2.status_code == 200, response2.text
    assert response2.json()["field_bindings"][0]["dropped"] is False

    with SessionLocal() as db:
        remaining2 = db.scalars(
            select(MappingBindingSignOff).where(
                MappingBindingSignOff.mapping_snapshot_id == snapshot_id,
                MappingBindingSignOff.source_field == "customer_id",
                MappingBindingSignOff.destination_field == "customer_id",
            )
        ).all()
        assert len(remaining2) == 1, "sign-off must survive toggling back to dropped=false"


def test_repropose_preserves_dropped_flag_for_unsigned_field(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    project_id, source_id = _seed_project()
    fake = FakeAdapter([
        {"source_field": "customer_id", "destination_field": "customer_id"},
        {"source_field": "full_name", "destination_field": "full_name"},
    ])
    monkeypatch.setattr(mapping_proposal_module, "get_adapter", lambda task: fake)

    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    patch = client.patch(
        f"/projects/{project_id}/sources/{source_id}/mapping",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "field_bindings": [
                {"source_field": "customer_id", "destination_field": "customer_id", "lookup_name": None, "dropped": False},
                {"source_field": "full_name", "destination_field": "full_name", "lookup_name": None, "dropped": True},
            ]
        },
    )
    assert patch.status_code == 200, patch.text

    repropose = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert repropose.status_code == 200, repropose.text
    bindings_by_pair = {
        (b["source_field"], b["destination_field"]): b
        for b in repropose.json()["field_bindings"]
    }
    assert bindings_by_pair[("full_name", "full_name")]["dropped"] is True
```

If a second `/mapping/propose` call doesn't naturally hit the `existing_draft` merge branch in `mapping/proposal.py` (e.g. requires a specific prior status), inspect `propose_mapping`'s entry condition before assuming this flow is right — do not guess.

### `engine/tests/test_codegen_service_api.py`

Add after `test_codegen_fails_loud_when_required_field_unmapped` (search for that function name):

```python
def test_codegen_fails_loud_when_required_field_dropped(
    monkeypatch: pytest.MonkeyPatch, admin_token: str
) -> None:
    project_id, source_definition_id = _seed_project()
    with SessionLocal() as db:
        snapshot = db.scalars(
            select(MappingSnapshot).where(
                MappingSnapshot.project_id == project_id,
            )
        ).first()
        assert snapshot is not None
        snapshot.field_bindings = [
            {"source_field": "customer_id", "destination_field": "customer_id", "lookup_name": None, "dropped": True},
            {"source_field": "full_name", "destination_field": "full_name", "lookup_name": None, "dropped": False},
        ]
        db.commit()

    response = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/codegen",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "unmapped_required_destination_fields"
    assert "customer_id" in data["error"]["message"]


def test_codegen_excludes_dropped_field_from_rendered_prompt(
    monkeypatch: pytest.MonkeyPatch, admin_token: str
) -> None:
    project_id, source_definition_id = _seed_project()
    with SessionLocal() as db:
        snapshot = db.scalars(
            select(MappingSnapshot).where(
                MappingSnapshot.project_id == project_id,
            )
        ).first()
        assert snapshot is not None
        snapshot.field_bindings = [
            {"source_field": "customer_id", "destination_field": "customer_id", "lookup_name": None, "dropped": False},
            {"source_field": "full_name", "destination_field": "full_name", "lookup_name": None, "dropped": False},
            {"source_field": "old_email_col", "destination_field": "email_address", "lookup_name": None, "dropped": True},
        ]
        db.commit()

    fake = FakeAdapter()
    monkeypatch.setattr(codegen_service_module, "get_adapter", lambda *a, **k: fake)

    response = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/codegen",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    assert len(fake.calls) == 1
    rendered_prompt = fake.calls[0].user
    assert "old_email_col" not in rendered_prompt
    assert "customer_id" in rendered_prompt
    assert "full_name" in rendered_prompt
```

Check `_seed_project()`'s `nullable` setup for `customer_id`/`full_name`/`email_address` (search `nullable` in this file) before writing the second test — only `email_address` should be nullable, so the required-field validation doesn't 422 before the AI call.

## Verification

```bash
# Confirm no migration is accidentally required (this task adds a JSON key, not a column)
cd engine && /Users/vjkotra/projects/katana/.venv/bin/python -m alembic heads
cd /Users/vjkotra/projects/katana

# Targeted tests
.venv/bin/python -m pytest engine/tests/test_mapping_review_api.py engine/tests/test_codegen_service_api.py -q

# Full regression
.venv/bin/python -m pytest engine/tests -q
```

Use `.venv/bin/python`/`.venv/bin/pytest` always — a bare `python`/`pytest` on this machine resolves to a stale global editable install of an unrelated sibling package and fails with `ModuleNotFoundError: No module named 'migrations_engine.db'`.

## Pitfalls

- Do NOT write an Alembic migration for this task — `field_bindings` is already a `JSON` column; `dropped` is a new key inside it, not a new column. Writing a migration here means you've misunderstood the change.
- Do NOT edit the `# Keep signed-off bindings that the AI dropped` block in `mapping/proposal.py` — a different, pre-existing concept with the same word in its comment. Confusing the two will produce a plausible-looking but wrong diff.
- Do NOT edit only one of the two `lookup_names = sorted({...})` blocks in `codegen/service.py` — they're in two different functions (`_select_lookup_snapshot_version` and `_build_lookup_tables`) with near-identical bodies; it's easy to edit one and assume both are done.
- Do NOT skip the Jinja template edit because "the Python validation already blocks the risky case" — required-field validation only catches dropping the *last* mapping for a *required* column. A dropped field mapped to a nullable column, or one where another binding still covers the required column, sails through Python validation untouched and would still leak into generated SQL without the template fix.
- Do NOT assume `patch_mapping`'s sign-off preservation "just works" without the test in this plan — the `changed_pairs` two-loop logic (lines 117-125) is subtle enough to warrant the explicit round-trip test rather than trusting the reasoning alone.

## Commit

```
feat(mapping): add dropped soft-delete flag to table-mapping field bindings
```
