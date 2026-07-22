# Plan: 001ep — Allow patch_mapping to Remove a Signed-Off Binding Instead of Rejecting the Request

## Task and Domain links

- Task: `tasks/001ep-allow-patch-mapping-to-drop-signed-off-bindings.md`
- Domain: no `docs/domain/` page documents this specific validation rule — no update required.

## Audience note

Written for an agent with no prior context. Re-read
`engine/src/migrations_engine/mapping/review.py` lines 59-150 immediately before starting to
confirm it still matches what's quoted below.

## Current State (verbatim)

`engine/src/migrations_engine/mapping/review.py`, lines 1-12 (module-level imports — note `select`
is already imported here at module scope):

```python
from __future__ import annotations

from datetime import UTC, datetime


from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import MappingFieldBindingResponse, MappingReviewResponse
from ..db.models import MappingSnapshot, LookupValueMap
from ..management.platform import record_management_audit
```

Lines 110-142 (the block this task changes, inside `patch_mapping`):

```python
    # Detect changed fields and delete their sign-off records
    changed_pairs = []
    new_pairs = {(b.source_field, b.destination_field) for b in field_bindings}
    for old_pair in existing_by_pair.keys():
        if old_pair not in new_pairs:
            changed_pairs.append(old_pair)
    for binding in field_bindings:
        pair = (binding.source_field, binding.destination_field)
        if pair not in existing_by_pair:
            changed_pairs.append(pair)

    if changed_pairs:
        from ..db.models import MappingBindingSignOff
        from sqlalchemy import delete, select, tuple_
        # Check if any changed pairs are already signed off by either reviewer
        signed_fields = db.scalars(
            select(MappingBindingSignOff.source_field)
            .where(
                MappingBindingSignOff.mapping_snapshot_id == snapshot.mapping_snapshot_id,
                tuple_(MappingBindingSignOff.source_field, MappingBindingSignOff.destination_field).in_(changed_pairs),
            )
        ).all()
        if signed_fields:
            raise AuthApiError(
                "mapping_already_approved",
                f"Cannot update mapping for field(s) {', '.join(sorted(set(signed_fields)))} because they have already been signed off by a reviewer.",
                409,
            )

        db.execute(
            delete(MappingBindingSignOff).where(
                MappingBindingSignOff.mapping_snapshot_id == snapshot.mapping_snapshot_id,
                tuple_(MappingBindingSignOff.source_field, MappingBindingSignOff.destination_field).in_(changed_pairs),
            )
        )
```

## Objective

Stop rejecting a patch that removes a signed-off binding. Keep computing which pairs changed, and
keep deleting their sign-off rows — only remove the "is any changed pair already signed off" check
and its 409.

## File Changes

### `engine/src/migrations_engine/mapping/review.py`

Find the exact block quoted above under "Lines 110-142" and replace it with:

```python
    # Detect changed fields and delete their sign-off records. A pair can be "changed" either by
    # being dropped entirely (deletion, or the old half of a rename) or by being newly added (a
    # fresh binding, or the new half of a rename) - either way its sign-off state no longer
    # applies and must be cleared. Deliberately does NOT block on a dropped pair having been
    # signed off: the frontend already prevents renaming a signed-off pair (its destination-field
    # input is locked whenever the binding is signed by either role), so this only ever fires for
    # genuine deletions, which must be allowed to succeed.
    changed_pairs = []
    new_pairs = {(b.source_field, b.destination_field) for b in field_bindings}
    for old_pair in existing_by_pair.keys():
        if old_pair not in new_pairs:
            changed_pairs.append(old_pair)
    for binding in field_bindings:
        pair = (binding.source_field, binding.destination_field)
        if pair not in existing_by_pair:
            changed_pairs.append(pair)

    if changed_pairs:
        from ..db.models import MappingBindingSignOff
        from sqlalchemy import delete, tuple_
        db.execute(
            delete(MappingBindingSignOff).where(
                MappingBindingSignOff.mapping_snapshot_id == snapshot.mapping_snapshot_id,
                tuple_(MappingBindingSignOff.source_field, MappingBindingSignOff.destination_field).in_(changed_pairs),
            )
        )
```

Note exactly what changed: the local `from sqlalchemy import delete, select, tuple_` became
`from sqlalchemy import delete, tuple_` (dropped `select` from this specific import — it's still
imported at module level on line 6 and used elsewhere in the file, this only removes the now-dead
local shadow import), and the entire `signed_fields = db.scalars(...)` query plus the
`if signed_fields: raise AuthApiError(...)` block is deleted. The `db.execute(delete(...))` call at
the end is unchanged, byte-for-byte, from the original.

## Tests

Add to `engine/tests/test_mapping_review_api.py`, directly after `test_patch_updates_field_bindings`
(lines 278-306 as of this writing). `User`, `select`, `SessionLocal`, and `CENTRAL_TEAM_ROLE` are
all already imported at the top of this file (lines 9, 11, 16, 19) — no new imports needed except
`MappingBindingSignOff`, added locally inside each new test function.

1.

```python
def test_patch_succeeds_when_removing_a_signed_off_binding(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
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
        admin_user = db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE))
        assert admin_user is not None
        db.add(
            MappingBindingSignOff(
                mapping_snapshot_id=snapshot.mapping_snapshot_id,
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
        json={"field_bindings": []},
    )

    assert response.status_code == 200, response.text
```

2.

```python
def test_patch_removing_signed_off_binding_deletes_its_sign_off_row(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
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
        json={"field_bindings": []},
    )
    assert response.status_code == 200, response.text

    with SessionLocal() as db:
        remaining = db.scalars(
            select(MappingBindingSignOff).where(
                MappingBindingSignOff.mapping_snapshot_id == snapshot_id,
                MappingBindingSignOff.source_field == "customer_id",
                MappingBindingSignOff.destination_field == "customer_id",
            )
        ).all()
        assert remaining == []
```

3. Before starting, confirm zero existing coverage depends on the removed 409:
   `grep -n "mapping_already_approved" engine/tests/test_mapping_review_api.py` must return
   nothing. If it returns a match, stop and report it instead of silently breaking that test.
4. Run the full existing `test_mapping_review_api.py` file and confirm every pre-existing test
   still passes alongside the 2 new ones.

## Verification

```bash
cd /Users/vjkotra/projects/katana
.venv/bin/ruff check engine/src/migrations_engine/mapping/review.py engine/tests/test_mapping_review_api.py
```
Expect: `All checks passed!` (this specifically catches the now-unused local `select` import if it
was left in by mistake).

```bash
.venv/bin/python -m mypy engine/src/migrations_engine/mapping/review.py --strict
```
Expect: no new errors versus the pre-existing baseline. If any errors appear, compare against
`git show HEAD~1:engine/src/migrations_engine/mapping/review.py` (or `git checkout HEAD~1 --
<file>`, run mypy, then `git checkout HEAD -- <file>` to restore) to confirm whether they're
pre-existing before treating any as caused by this change.

```bash
.venv/bin/pytest engine/tests/test_mapping_review_api.py -q
```
Expect: all tests pass, including the 2 new ones.

```bash
.venv/bin/pytest engine/tests -q
```
Expect: full suite passes, same count as before this task plus the 2 new tests, zero failures.

## Pitfalls

- **Do not remove the `db.execute(delete(MappingBindingSignOff)...)` call.** Only the
  `signed_fields` check and its `raise AuthApiError(...)` are being removed — the actual deletion
  of stale sign-off rows for changed pairs must still happen unconditionally whenever
  `changed_pairs` is non-empty. Losing this would leave orphaned sign-off rows pointing at bindings
  that no longer exist.
- **Don't touch `mapping_not_editable`** (the check just above this block, for `snapshot.status !=
  "draft"`) — that's a separate, still-valid guard (you can only patch a draft snapshot at all) and
  is unrelated to this task.
- **The local `from ..db.models import MappingBindingSignOff` and `from sqlalchemy import delete,
  tuple_` imports stay local to this `if changed_pairs:` block**, matching the existing code's
  style (these are deliberately not hoisted to module level in the original code) — don't move them
  to the top of the file as part of this change; that's an unrelated style change outside this
  task's scope.

## Commit

Own commit, before `001eq`. Suggested message: `fix: allow patch_mapping to remove a signed-off
binding instead of rejecting the request (001ep)`.
