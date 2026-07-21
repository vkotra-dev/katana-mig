---
type: Task Plan
title: Track and Display Unmapped Destination Fields
status: ready
---

# Task: 001dz-unmapped-destination-fields-tracking

## Context
When an operator removes a destination field mapping from a source field, that destination field disappears from the mapped list, but it is not currently tracked or displayed anywhere. To ensure data completeness, operators need visibility into which destination fields (from the DDL) are completely unmapped. This tracking should also be integrated with the AI analysis step.

## Requirements
1. **Dynamic Unmapped List (UI)**: The mapping review page must display a dynamic list of "Unmapped destination fields" inside the exact same warning block as the current "Unmapped source fields" warning. If a user removes a destination field from an existing mapping, it should immediately reappear in this list.
2. **AI Awareness**: The AI field mapping step should optionally be aware of required destination fields that are missing mappings.
3. **Codegen Gating (Backend)**: Unmapped destination fields must be explicitly flagged and computed during Code Generation. Code generation must halt/stop generating stored procedures if critical destination fields are left unmapped.

## Implementation Plan

### 1. Sequencing Dependency
- **Wait for 001dy**: If `001dy` ships first, a source field can map to multiple destinations. This means "unmapped" should just mean "not the destination of any binding". Ensure this task (`001dz`) is executed *after* `001dy` so the frontend filter checks against the right binding structure from the start.

### 2. Frontend State Management & UI
- **Data Availability**: The backend already parses the DDL and populates `MappingSnapshot.destination_fields` during snapshot creation. This data is already sent to the frontend and available in `table.destinationFields`. No backend API changes are required to deliver this data.
- **Dynamic State Calculation**: In the React frontend (`mapping/page.tsx` or `ReviewGrid.tsx`), compute the unmapped destination fields dynamically on every render:
  `const unmappedDestFields = table.destinationFields.filter(f => !table.bindings.some(b => b.destinationField === f));`
- **Render New Section**: Render the `unmappedDestFields` list directly inside the existing amber warning box that houses "Unmapped source fields".
- **Instant Reactivity**: Because it is computed on the fly on every render, it will naturally update instantly when a mapping is deleted or changed.

### 3. Codegen Gating (Backend Validation)
- **Avoid Snapshot Polluting**: Do not attempt to store nullability metadata on `MappingSnapshot.destination_fields`. Modifying the shape of this array from `list[str]` to `list[dict]` will silently break existing consumers (like `patch_mapping` and the frontend autocomplete).
- **Native DDL Reparsing**: The code generation service (`engine/src/migrations_engine/codegen/service.py`, inside `generate_codegen_artifact`) already fetches the `ProjectDefinition`. Rather than relying on the snapshot, it should natively re-parse the destination DDL at generation time to identify which columns are `NOT NULL`.
- **Validation**: Compute the unmapped fields: `unmapped = set(destination_fields) - set(mapped_dest_fields)`. Using the natively parsed nullability metadata, if any of those unmapped destination fields are required (`NOT NULL` with no default), the service must throw a `CodegenValidationError` and halt generation of the SP for that table.
