---
type: Task Plan
title: Support 1-to-N Source-to-Destination Field Mappings
status: ready
---

# Task: 001dy-one-to-many-field-mapping

## Context
Currently, the mapping review page restricts operators from mapping a single source field to multiple destination fields. The autocomplete destination field selector filters or restricts choices, making it impossible to populate two different destination fields from the same source field.

## Requirements
1. **UI Capability**: The operator must be able to select multiple destination fields for a single source field in the mapping review UI. 
2. **AI Capability**: The AI mapping extraction prompt must be instructed that 1-to-N mappings are permissible when logically appropriate (e.g., populating both a `billing_address` and `shipping_address` from a single `ADDRESS` source field).

## Implementation Plan

### 0. Data Model & Unique Constraint Migration
- **Sign-Off Model Update (`db/models.py`)**: The `MappingBindingSignOff` model currently has a unique constraint on `(mapping_snapshot_id, destination_object_name, source_field, user_id)`. This must be updated to include `destination_field` so that sign-offs operate at the `(source, destination)` pair level, not just the source level.
- **Alembic Migration**: Generate and run a migration script to update the constraint on the `MappingBindingSignOff` table.

### 1. Backend Patching & Diffing (`review.py`)
- **`patch_mapping` Re-keying**: The current `patch_mapping` function computes diffs using a dictionary keyed solely by `source_field` (`existing_by_src = {b.get("source_field"): b ...}`). This must be rewritten to operate on `(source_field, destination_field)` pairs so that 1-to-N rows don't silently collapse.
- **Changed Fields Calculation**: Ensure the `changed_fields` variable correctly computes changes at the `(source, destination)` pair level when verifying against `MappingBindingSignOff` records.

### 2. The Sign-Off Subsystem Rewrite (`sign_offs.py`)
This is a critical, parallel subsystem that fundamentally assumes 1 binding per source field and must be re-keyed end-to-end:
- **API routes & signatures**: Update `sign_binding` and `unsign_binding` signatures, API schemas, and validation logic to take `destination_field` alongside `source_field`.
- **Status rendering**: Rewrite `get_sign_off_status` so the `b_map` dictionary nests by `destination_field` as well as `source_field`. Apply `MappingBindingSignOff` records against the exact `(source, destination)` row to prevent ambiguous collapsing.
- **Completeness Gates**: Update the completeness gating loops in `get_sign_off_status` and `push_for_review` to iterate over `(sf, dest_field)` pairs rather than just `sf`. Failing to do this causes hard correctness bugs where a 1-to-N field can falsely trigger or block progression.

### 3. Frontend State Management (`page.tsx` & `ReviewGrid.tsx`)
- **Sign-Off Chain**: Thread `destinationField` down the entire sign/unsign API chain: `signBinding`/`unsignBinding` (`lib/sign-offs-api.ts`) → `onSignBinding`/`onUnsignBinding` (`ReviewGrid.tsx`) → `handleSignBinding`/`handleUnsignBinding` (`review/page.tsx`).
- **Callback Disambiguation**: The `onDestinationFieldChange` callback currently identifies the row to edit using only `(tableName, sourceField)`. It must be updated to thread an index or the `(source, destination)` pair to disambiguate which row is being edited.
- **State Update Logic**: Rewrite `handleDestinationFieldChange` to update the specific indexed row rather than blindly mapping over `b.sourceField !== sourceField`.
- **Add Destination Button**: Add a UI affordance to spawn an additional binding row for a given source field, allowing the operator to map it to multiple destinations. Ensure the autocomplete excludes destination fields that are *already* mapped for that specific source field, preventing true duplicate rows.

### 4. AI Prompt Engineering (`review.py`)
- **System Prompt Update**: Modify the system prompt in `propose_mapping` to explicitly state: "A single source field MAY be mapped to multiple destination fields if it logically populates both."
