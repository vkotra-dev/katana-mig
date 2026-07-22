# Plan: 001em — Expose destination_columns in the Mapping API + Fix Silent Codegen Skip

## Task and Domain links

- Task: `tasks/001em-expose-destination-columns-codegen-guard.md`
- Design: `docs/superpowers/specs/2026-07-22-unmapped-required-fields-callout-design.md`
- Domain: no `docs/domain/` page currently documents `destination_columns` or this validation
  behavior — no domain doc update required for this task.

## Audience note

This plan is written for an agent with no prior context on this codebase beyond what's quoted
here. Every edit below gives the exact current text to find and the exact replacement text. Do not
improvise field names, error codes, or formatting beyond what's specified — copy them verbatim.

## Current State (verbatim, read immediately before starting)

Before making any edit, re-read each file below in full to confirm it still matches what's quoted
here (someone may have changed it since this plan was written). If it doesn't match, stop and
report the discrepancy instead of guessing.

**`engine/src/migrations_engine/api/schemas.py`** — around line 562-597:

```python
class MappingFieldBindingResponse(BaseModel):
    source_field: str
    destination_field: str
    lookup_name: str | None
    binding_type: str | None = None
    reference_table_name: str | None = None
    destination_table_name: str | None = None
    destination_data_type: str | None = None
    nullable: bool | None = None


class LookupTableReferenceResponse(BaseModel):
    lookup_name: str
    destination_table_name: str


class MappingSnapshotResponse(BaseModel):
    mapping_snapshot_id: str
    project_id: str
    destination_object_name: str
    mapping_snapshot_version: str
    field_bindings: list[MappingFieldBindingResponse]
    status: str
    current_ball_role: str | None = None
    approved_at: datetime | None
    approved_by_user_id: str | None
    created_at: datetime
    lookup_table_references: list[LookupTableReferenceResponse] = []
    destination_fields: list[str] = []

class MappingPatchRequest(BaseModel):
    field_bindings: list[MappingFieldBindingResponse]


class MappingReviewResponse(MappingSnapshotResponse):
    pass
```

**`engine/src/migrations_engine/mapping/review_repository.py`** — `snapshot_to_response`, lines
103-147:

```python
def snapshot_to_response(
    snapshot: MappingSnapshot,
    db: Session,
    destination_fields: list[str] | None = None,
) -> MappingReviewResponse:
    fields = destination_fields if destination_fields is not None else (snapshot.destination_fields or [])
    
    lookup_table_references: list[dict[str, str]] = []
    for binding in snapshot.field_bindings:
        b_type = binding.get("binding_type")
        ref_table = binding.get("reference_table_name")
        l_name = binding.get("lookup_name")
        if b_type == "lookup_fk" and ref_table:
            # Match: lookup_name -> destination_table_name
            lookup_table_references.append({
                "lookup_name": l_name or binding.get("source_field", ""),
                "destination_table_name": ref_table,
            })

    return MappingReviewResponse(
        mapping_snapshot_id=snapshot.mapping_snapshot_id,
        project_id=snapshot.project_id,
        destination_object_name=snapshot.destination_object_name,
        mapping_snapshot_version=snapshot.mapping_snapshot_version,
        field_bindings=[
            MappingFieldBindingResponse(
                source_field=str(binding.get("source_field", "")),
                destination_field=str(binding.get("destination_field", "")),
                lookup_name=binding.get("lookup_name"),
                binding_type=binding.get("binding_type"),
                reference_table_name=binding.get("reference_table_name"),
                destination_table_name=binding.get("destination_table_name"),
                destination_data_type=binding.get("destination_data_type"),
                nullable=binding.get("nullable"),
            )
            for binding in snapshot.field_bindings
        ],
        status=snapshot.status,
        current_ball_role=snapshot.current_ball_role,
        approved_at=snapshot.approved_at,
        approved_by_user_id=snapshot.approved_by_user_id,
        created_at=snapshot.created_at,
        destination_fields=fields,
        lookup_table_references=lookup_table_references,
    )
```

**`engine/src/migrations_engine/routes/mapping_snapshots.py`** — full file, 114 lines (quoted in
full since both edits are in it):

```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.deps import get_current_user, get_db
from ..api.schemas import MappingSnapshotResponse
from ..db.models import User
from ..management.access import require_project_access
from ..management.feeds import get_source_contract
from ..mapping.snapshots import select_latest_approved_mapping_snapshot, select_all_approved_mapping_snapshots, select_all_feed_mapping_snapshots
from ..mapping.exceptions import SnapshotNotFoundError


router = APIRouter(prefix="/projects/{project_id}/sources/{source_definition_id}", tags=["mapping-snapshots"])


@router.get("/mapping-snapshot", response_model=MappingSnapshotResponse)
def get_latest_mapping_snapshot(
    project_id: str,
    source_definition_id: str,
    destination_object_name: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MappingSnapshotResponse:
    require_project_access(db, user=actor, project_id=project_id)
    source_contract = get_source_contract(db, project_id=project_id, source_definition_id=source_definition_id)

    if not source_contract.destination_object_references:
        raise AuthApiError("mapping_snapshot_not_found", "Source contract has no destination object reference.", 404)

    target_table = destination_object_name
    if not target_table:
        target_table = source_contract.destination_object_references[0]

    try:
        mapping_snapshot = select_latest_approved_mapping_snapshot(
            db,
            project_id=project_id,
            destination_object_name=target_table,
            source_definition_id=source_definition_id,
        )
    except SnapshotNotFoundError as exc:
        raise AuthApiError("mapping_snapshot_not_found", str(exc), 404) from exc
    return MappingSnapshotResponse(
        mapping_snapshot_id=mapping_snapshot.mapping_snapshot_id,
        project_id=mapping_snapshot.project_id,
        destination_object_name=mapping_snapshot.destination_object_name,
        mapping_snapshot_version=mapping_snapshot.mapping_snapshot_version,
        field_bindings=[
            {
                "source_field": str(binding.get("source_field", "")),
                "destination_field": str(binding.get("destination_field", "")),
                "lookup_name": binding.get("lookup_name"),
                "binding_type": binding.get("binding_type"),
                "reference_table_name": binding.get("reference_table_name"),
            }
            for binding in mapping_snapshot.field_bindings
        ],
        status=mapping_snapshot.status,
        approved_at=mapping_snapshot.approved_at,
        approved_by_user_id=mapping_snapshot.approved_by_user_id,
        created_at=mapping_snapshot.created_at,
        destination_fields=mapping_snapshot.destination_fields or [],
    )


@router.get("/mapping-snapshots", response_model=list[MappingSnapshotResponse])
def list_approved_mapping_snapshots(
    project_id: str,
    source_definition_id: str,
    any_status: bool = False,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MappingSnapshotResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    if any_status:
        snapshots = select_all_feed_mapping_snapshots(
            db,
            project_id=project_id,
            source_definition_id=source_definition_id,
        )
    else:
        snapshots = select_all_approved_mapping_snapshots(
            db,
            project_id=project_id,
            source_definition_id=source_definition_id,
        )
    return [
        MappingSnapshotResponse(
            mapping_snapshot_id=s.mapping_snapshot_id,
            project_id=s.project_id,
            destination_object_name=s.destination_object_name,
            mapping_snapshot_version=s.mapping_snapshot_version,
            field_bindings=[
                {
                    "source_field": str(binding.get("source_field", "")),
                    "destination_field": str(binding.get("destination_field", "")),
                    "lookup_name": binding.get("lookup_name"),
                    "binding_type": binding.get("binding_type"),
                    "reference_table_name": binding.get("reference_table_name"),
                }
                for binding in s.field_bindings
            ],
            status=s.status,
            approved_at=s.approved_at,
            approved_by_user_id=s.approved_by_user_id,
            created_at=s.created_at,
            destination_fields=s.destination_fields or [],
        )
        for s in snapshots
    ]
```

**`engine/src/migrations_engine/codegen/service.py`** — lines 78-95 (the check to change):

```python
    if mapping_snapshot.destination_columns is not None:
        required_dest_fields = {
            c["name"] for c in mapping_snapshot.destination_columns
            if c.get("nullable") is False
        }
        mapped_dest_fields = {
            binding.get("destination_field")
            for binding in mapping_snapshot.field_bindings
            if binding.get("destination_field")
        }
        unmapped_required = required_dest_fields - mapped_dest_fields
        if unmapped_required:
            missing = ", ".join(sorted(unmapped_required))
            raise AuthApiError(
                "unmapped_required_destination_fields",
                f"Cannot generate code: Required destination fields are unmapped ({missing}). Please update the mapping first.",
                422,
            )
```

**`engine/tests/test_codegen_service_api.py`** — the `MappingSnapshot(...)` block inside
`_seed_project()`, lines 158-180:

```python
        db.add(
                MappingSnapshot(
                    mapping_snapshot_id=str(uuid.uuid4()),
                    project_id=project_id,
                    destination_object_name="Customer",
                    mapping_snapshot_version="v1",
                    field_bindings=[
                        {
                            "source_field": "customer_id",
                            "destination_field": "customer_id",
                            "lookup_name": None,
                        },
                        {
                            "source_field": "full_name",
                            "destination_field": "full_name",
                            "lookup_name": None,
                        },
                    ],
                    status="approved",
                    approved_at=datetime.now(UTC),
                    approved_by_user_id=admin_user.user_id,
                )
        )
```

## Objective

1. Add `MappingDestinationColumnResponse` + `destination_columns` field to the API schema.
2. Populate `destination_columns` in all three response-building call sites.
3. Make `codegen/service.py` fail loud instead of silently skipping when `destination_columns is
   None`.
4. Keep all three existing tests in `test_codegen_service_api.py` passing by updating the shared
   seed helper.
5. Add new tests covering the two behaviors this task adds.

## File Changes

### 1. `engine/src/migrations_engine/api/schemas.py`

Find this exact block (it's the `MappingSnapshotResponse` class and the blank line immediately
after it, quoted above under Current State):

```python
class MappingSnapshotResponse(BaseModel):
    mapping_snapshot_id: str
    project_id: str
    destination_object_name: str
    mapping_snapshot_version: str
    field_bindings: list[MappingFieldBindingResponse]
    status: str
    current_ball_role: str | None = None
    approved_at: datetime | None
    approved_by_user_id: str | None
    created_at: datetime
    lookup_table_references: list[LookupTableReferenceResponse] = []
    destination_fields: list[str] = []

class MappingPatchRequest(BaseModel):
```

Replace it with (adds a new model above `MappingSnapshotResponse`, and one new field inside it —
note the blank line between the new model and `class MappingSnapshotResponse` matches this file's
existing two-blank-line convention between top-level classes):

```python
class MappingDestinationColumnResponse(BaseModel):
    name: str
    destination_data_type: str | None = None
    nullable: bool | None = None


class MappingSnapshotResponse(BaseModel):
    mapping_snapshot_id: str
    project_id: str
    destination_object_name: str
    mapping_snapshot_version: str
    field_bindings: list[MappingFieldBindingResponse]
    status: str
    current_ball_role: str | None = None
    approved_at: datetime | None
    approved_by_user_id: str | None
    created_at: datetime
    lookup_table_references: list[LookupTableReferenceResponse] = []
    destination_fields: list[str] = []
    destination_columns: list[MappingDestinationColumnResponse] | None = None

class MappingPatchRequest(BaseModel):
```

### 2. `engine/src/migrations_engine/mapping/review_repository.py`

The file starts with these exact 10 lines (imports plus one blank line, quoted in full — note `re`
is imported oddly after the sqlalchemy imports and before `..api.deps`; leave that ordering as-is,
it's pre-existing and not part of this task):

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

import re
from ..api.deps import AuthApiError
from ..api.schemas import MappingFieldBindingResponse, MappingReviewResponse
from ..db.models import ProjectDefinition, ProjectRegistry, Feed, MappingSnapshot
from ..management.source_analysis import get_latest_source_schema_artifact
```

Change only this one line:

```python
from ..api.schemas import MappingFieldBindingResponse, MappingReviewResponse
```

to:

```python
from ..api.schemas import MappingDestinationColumnResponse, MappingFieldBindingResponse, MappingReviewResponse
```

Then find this exact return statement inside `snapshot_to_response` (quoted in full above under
Current State):

```python
    return MappingReviewResponse(
        mapping_snapshot_id=snapshot.mapping_snapshot_id,
        project_id=snapshot.project_id,
        destination_object_name=snapshot.destination_object_name,
        mapping_snapshot_version=snapshot.mapping_snapshot_version,
        field_bindings=[
            MappingFieldBindingResponse(
                source_field=str(binding.get("source_field", "")),
                destination_field=str(binding.get("destination_field", "")),
                lookup_name=binding.get("lookup_name"),
                binding_type=binding.get("binding_type"),
                reference_table_name=binding.get("reference_table_name"),
                destination_table_name=binding.get("destination_table_name"),
                destination_data_type=binding.get("destination_data_type"),
                nullable=binding.get("nullable"),
            )
            for binding in snapshot.field_bindings
        ],
        status=snapshot.status,
        current_ball_role=snapshot.current_ball_role,
        approved_at=snapshot.approved_at,
        approved_by_user_id=snapshot.approved_by_user_id,
        created_at=snapshot.created_at,
        destination_fields=fields,
        lookup_table_references=lookup_table_references,
    )
```

Replace with (adds one new kwarg, `destination_columns`, built from `snapshot.destination_columns`
which is `list[dict[str, Any]] | None` on the model — each dict has keys `name`,
`destination_data_type`, `nullable`, matching `MappingDestinationColumnResponse`'s fields exactly):

```python
    return MappingReviewResponse(
        mapping_snapshot_id=snapshot.mapping_snapshot_id,
        project_id=snapshot.project_id,
        destination_object_name=snapshot.destination_object_name,
        mapping_snapshot_version=snapshot.mapping_snapshot_version,
        field_bindings=[
            MappingFieldBindingResponse(
                source_field=str(binding.get("source_field", "")),
                destination_field=str(binding.get("destination_field", "")),
                lookup_name=binding.get("lookup_name"),
                binding_type=binding.get("binding_type"),
                reference_table_name=binding.get("reference_table_name"),
                destination_table_name=binding.get("destination_table_name"),
                destination_data_type=binding.get("destination_data_type"),
                nullable=binding.get("nullable"),
            )
            for binding in snapshot.field_bindings
        ],
        status=snapshot.status,
        current_ball_role=snapshot.current_ball_role,
        approved_at=snapshot.approved_at,
        approved_by_user_id=snapshot.approved_by_user_id,
        created_at=snapshot.created_at,
        destination_fields=fields,
        destination_columns=(
            [
                MappingDestinationColumnResponse(
                    name=c.get("name", ""),
                    destination_data_type=c.get("destination_data_type"),
                    nullable=c.get("nullable"),
                )
                for c in snapshot.destination_columns
            ]
            if snapshot.destination_columns is not None
            else None
        ),
        lookup_table_references=lookup_table_references,
    )
```

### 3. `engine/src/migrations_engine/routes/mapping_snapshots.py`

Change the import line:

```python
from ..api.schemas import MappingSnapshotResponse
```

to:

```python
from ..api.schemas import MappingDestinationColumnResponse, MappingSnapshotResponse
```

In `get_latest_mapping_snapshot`, find this exact `return` statement (quoted in full above):

```python
    return MappingSnapshotResponse(
        mapping_snapshot_id=mapping_snapshot.mapping_snapshot_id,
        project_id=mapping_snapshot.project_id,
        destination_object_name=mapping_snapshot.destination_object_name,
        mapping_snapshot_version=mapping_snapshot.mapping_snapshot_version,
        field_bindings=[
            {
                "source_field": str(binding.get("source_field", "")),
                "destination_field": str(binding.get("destination_field", "")),
                "lookup_name": binding.get("lookup_name"),
                "binding_type": binding.get("binding_type"),
                "reference_table_name": binding.get("reference_table_name"),
            }
            for binding in mapping_snapshot.field_bindings
        ],
        status=mapping_snapshot.status,
        approved_at=mapping_snapshot.approved_at,
        approved_by_user_id=mapping_snapshot.approved_by_user_id,
        created_at=mapping_snapshot.created_at,
        destination_fields=mapping_snapshot.destination_fields or [],
    )
```

Replace with:

```python
    return MappingSnapshotResponse(
        mapping_snapshot_id=mapping_snapshot.mapping_snapshot_id,
        project_id=mapping_snapshot.project_id,
        destination_object_name=mapping_snapshot.destination_object_name,
        mapping_snapshot_version=mapping_snapshot.mapping_snapshot_version,
        field_bindings=[
            {
                "source_field": str(binding.get("source_field", "")),
                "destination_field": str(binding.get("destination_field", "")),
                "lookup_name": binding.get("lookup_name"),
                "binding_type": binding.get("binding_type"),
                "reference_table_name": binding.get("reference_table_name"),
            }
            for binding in mapping_snapshot.field_bindings
        ],
        status=mapping_snapshot.status,
        approved_at=mapping_snapshot.approved_at,
        approved_by_user_id=mapping_snapshot.approved_by_user_id,
        created_at=mapping_snapshot.created_at,
        destination_fields=mapping_snapshot.destination_fields or [],
        destination_columns=(
            [
                MappingDestinationColumnResponse(
                    name=c.get("name", ""),
                    destination_data_type=c.get("destination_data_type"),
                    nullable=c.get("nullable"),
                )
                for c in mapping_snapshot.destination_columns
            ]
            if mapping_snapshot.destination_columns is not None
            else None
        ),
    )
```

In `list_approved_mapping_snapshots`, find this exact `return` statement (quoted in full above):

```python
    return [
        MappingSnapshotResponse(
            mapping_snapshot_id=s.mapping_snapshot_id,
            project_id=s.project_id,
            destination_object_name=s.destination_object_name,
            mapping_snapshot_version=s.mapping_snapshot_version,
            field_bindings=[
                {
                    "source_field": str(binding.get("source_field", "")),
                    "destination_field": str(binding.get("destination_field", "")),
                    "lookup_name": binding.get("lookup_name"),
                    "binding_type": binding.get("binding_type"),
                    "reference_table_name": binding.get("reference_table_name"),
                }
                for binding in s.field_bindings
            ],
            status=s.status,
            approved_at=s.approved_at,
            approved_by_user_id=s.approved_by_user_id,
            created_at=s.created_at,
            destination_fields=s.destination_fields or [],
        )
        for s in snapshots
    ]
```

Replace with:

```python
    return [
        MappingSnapshotResponse(
            mapping_snapshot_id=s.mapping_snapshot_id,
            project_id=s.project_id,
            destination_object_name=s.destination_object_name,
            mapping_snapshot_version=s.mapping_snapshot_version,
            field_bindings=[
                {
                    "source_field": str(binding.get("source_field", "")),
                    "destination_field": str(binding.get("destination_field", "")),
                    "lookup_name": binding.get("lookup_name"),
                    "binding_type": binding.get("binding_type"),
                    "reference_table_name": binding.get("reference_table_name"),
                }
                for binding in s.field_bindings
            ],
            status=s.status,
            approved_at=s.approved_at,
            approved_by_user_id=s.approved_by_user_id,
            created_at=s.created_at,
            destination_fields=s.destination_fields or [],
            destination_columns=(
                [
                    MappingDestinationColumnResponse(
                        name=c.get("name", ""),
                        destination_data_type=c.get("destination_data_type"),
                        nullable=c.get("nullable"),
                    )
                    for c in s.destination_columns
                ]
                if s.destination_columns is not None
                else None
            ),
        )
        for s in snapshots
    ]
```

### 4. `engine/src/migrations_engine/codegen/service.py`

Find this exact block (quoted in full above under Current State, lines 78-95):

```python
    if mapping_snapshot.destination_columns is not None:
        required_dest_fields = {
            c["name"] for c in mapping_snapshot.destination_columns
            if c.get("nullable") is False
        }
        mapped_dest_fields = {
            binding.get("destination_field")
            for binding in mapping_snapshot.field_bindings
            if binding.get("destination_field")
        }
        unmapped_required = required_dest_fields - mapped_dest_fields
        if unmapped_required:
            missing = ", ".join(sorted(unmapped_required))
            raise AuthApiError(
                "unmapped_required_destination_fields",
                f"Cannot generate code: Required destination fields are unmapped ({missing}). Please update the mapping first.",
                422,
            )
```

Replace with (adds an `else` branch that raises a new, distinct error code instead of falling
through silently):

```python
    if mapping_snapshot.destination_columns is not None:
        required_dest_fields = {
            c["name"] for c in mapping_snapshot.destination_columns
            if c.get("nullable") is False
        }
        mapped_dest_fields = {
            binding.get("destination_field")
            for binding in mapping_snapshot.field_bindings
            if binding.get("destination_field")
        }
        unmapped_required = required_dest_fields - mapped_dest_fields
        if unmapped_required:
            missing = ", ".join(sorted(unmapped_required))
            raise AuthApiError(
                "unmapped_required_destination_fields",
                f"Cannot generate code: Required destination fields are unmapped ({missing}). Please update the mapping first.",
                422,
            )
    else:
        raise AuthApiError(
            "destination_metadata_missing",
            "This mapping was approved before destination column metadata tracking was added. "
            "Unapprove, re-run AI Analyze, and re-approve this table to regenerate it before "
            "generating code.",
            422,
        )
```

### 5. `engine/tests/test_codegen_service_api.py` — fix the seed helper

Find this exact block inside `_seed_project()` (quoted in full above under Current State, lines
158-180):

```python
        db.add(
                MappingSnapshot(
                    mapping_snapshot_id=str(uuid.uuid4()),
                    project_id=project_id,
                    destination_object_name="Customer",
                    mapping_snapshot_version="v1",
                    field_bindings=[
                        {
                            "source_field": "customer_id",
                            "destination_field": "customer_id",
                            "lookup_name": None,
                        },
                        {
                            "source_field": "full_name",
                            "destination_field": "full_name",
                            "lookup_name": None,
                        },
                    ],
                    status="approved",
                    approved_at=datetime.now(UTC),
                    approved_by_user_id=admin_user.user_id,
                )
        )
```

Replace with (adds `destination_columns` matching both existing field bindings, both marked
`nullable: False` — the existing bindings already map both fields, so this keeps the required-field
check passing with no unmapped fields, same as today's behavior; only the NULL-column silent-skip
path is what's being closed):

```python
        db.add(
                MappingSnapshot(
                    mapping_snapshot_id=str(uuid.uuid4()),
                    project_id=project_id,
                    destination_object_name="Customer",
                    mapping_snapshot_version="v1",
                    field_bindings=[
                        {
                            "source_field": "customer_id",
                            "destination_field": "customer_id",
                            "lookup_name": None,
                        },
                        {
                            "source_field": "full_name",
                            "destination_field": "full_name",
                            "lookup_name": None,
                        },
                    ],
                    destination_columns=[
                        {"name": "customer_id", "destination_data_type": "INT", "nullable": False},
                        {"name": "full_name", "destination_data_type": "NVARCHAR(255)", "nullable": True},
                    ],
                    status="approved",
                    approved_at=datetime.now(UTC),
                    approved_by_user_id=admin_user.user_id,
                )
        )
```

## Tests

Add these as new test functions in `engine/tests/test_codegen_service_api.py`, following the exact
style of the existing tests in that file (same imports, same `client.post`/`SessionLocal` patterns
already used by `test_post_codegen_creates_active_artifact_and_preview` — read that test first for
the pattern before writing the new ones):

All `AuthApiError` exceptions are serialized by `app.py`'s exception handler
(`app.py:100-106`) as `{"error": {"code": ..., "message": ...}}` — always assert on
`response.json()["error"]["code"]`, never `response.json()["code"]`.

1. **`test_codegen_fails_loud_when_destination_columns_missing`** — seed a project the same way
   `_seed_project()` does, but for this one test's `MappingSnapshot`, explicitly pass
   `destination_columns=None` (or omit the kwarg, since it defaults to `None`) instead of using the
   shared helper's now-populated version. Call the codegen POST endpoint. Assert the response is a
   422 with `response.json()["error"]["code"] == "destination_metadata_missing"`.
2. **`test_codegen_fails_loud_when_required_field_unmapped`** — seed a `MappingSnapshot` with
   `destination_columns` containing a NOT-NULL column that has no matching entry in
   `field_bindings` (e.g. add a third column `"account_status"` with `"nullable": False` to
   `destination_columns` but do not add a matching binding for it). Call the codegen POST endpoint.
   Assert 422 with `response.json()["error"]["code"] == "unmapped_required_destination_fields"` and
   that `response.json()["error"]["message"]` mentions `"account_status"`.
3. **Response schema test** — in `engine/tests/test_mapping_review_api.py`, find an existing test
   that calls the `GET .../mapping-snapshots` or `GET .../mapping-snapshot` endpoint and asserts on
   the response JSON (grep that file for `"/mapping-snapshot"` to find one). Add a new test, or
   extend an existing one, that seeds a `MappingSnapshot` with `destination_columns` set to a
   two-item list, calls the endpoint, and asserts
   `response.json()["destination_columns"] == [{"name": ..., "destination_data_type": ..., "nullable": ...}, ...]`
   matching what was seeded, confirming the field round-trips through the API.

## Verification

Run these commands from the repo root (`/Users/vjkotra/projects/katana`) in order. Every command
must succeed before this task is considered done — do not skip any of them, and do not proceed to
`001en` until all pass:

```bash
.venv/bin/ruff check engine/src/migrations_engine/api/schemas.py engine/src/migrations_engine/mapping/review_repository.py engine/src/migrations_engine/routes/mapping_snapshots.py engine/src/migrations_engine/codegen/service.py engine/tests/test_codegen_service_api.py engine/tests/test_mapping_review_api.py
```
Expect: `All checks passed!`

```bash
.venv/bin/python -m mypy engine/src/migrations_engine/api/schemas.py engine/src/migrations_engine/mapping/review_repository.py engine/src/migrations_engine/routes/mapping_snapshots.py engine/src/migrations_engine/codegen/service.py --strict
```
Expect: no NEW errors. If this command reports errors, check whether they already existed before
your changes by running `git stash`, re-running the same command, and comparing — only errors that
are genuinely new (not present with your changes stashed) need fixing.

```bash
.venv/bin/pytest engine/tests/test_codegen_service_api.py engine/tests/test_mapping_review_api.py -q
```
Expect: all tests pass, including the 3 pre-existing tests in `test_codegen_service_api.py`
(`test_post_codegen_creates_active_artifact_and_preview`,
`test_delivery_bundle_returns_active_artifacts`,
`test_codegen_preserves_raw_response_on_validation_error`) and the new tests added above.

```bash
.venv/bin/pytest engine/tests -q
```
Expect: full suite passes, same count of passed tests as before this task plus the new tests added,
zero failures. This confirms nothing else in the codebase depended on the old
`MappingSnapshotResponse` shape or the old silent-skip behavior.

## Pitfalls

- **The three response-building call sites are NOT the same code.** `snapshot_to_response` in
  `review_repository.py` is used by some endpoints; `routes/mapping_snapshots.py` builds its own
  `MappingSnapshotResponse` directly in two functions, independently. Missing any of the three
  means some API caller gets `destination_columns: null` even when the database has real data —
  this is exactly the kind of duplication bug this session has hit before (see `001ee`/`001ek`'s
  history of two independent DDL parsers). Do all three edits.
- **Updating `_seed_project()` in `test_codegen_service_api.py` is not optional.** Once the
  silent-skip is closed, any test that doesn't set `destination_columns` on its seeded snapshot
  will start failing with the new `destination_metadata_missing` error where it used to succeed.
  Confirm this by running the full test file before and after your `codegen/service.py` change (if
  you skip the seed-helper fix, `test_post_codegen_creates_active_artifact_and_preview` and
  `test_delivery_bundle_returns_active_artifacts` will fail).
- **Do not touch `destination_fields`.** It stays exactly as-is (names-only list) — this task adds
  a new, separate field (`destination_columns`) alongside it. Do not try to merge or replace it.
- **`destination_columns` is nullable at the model level** (`db/models.py`:
  `Mapped[list[dict[str, Any]] | None]`) — always guard with `is not None` before iterating, both
  in the response-building code (already shown above) and in any new test assertions.
- **Match the existing error-response JSON shape exactly** when writing the new tests — grep this
  test file for how an existing `AuthApiError` gets asserted on (e.g.
  `response.json()["code"]` vs some other key name) rather than guessing the field name.

## Commit

Own commit, separate from `001en`. Suggested message: `feat: expose destination_columns in mapping
API, fail loud on missing codegen metadata (001em)`.
