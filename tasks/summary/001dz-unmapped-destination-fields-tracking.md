# Summary: 001dz — Unmapped Destination Fields Tracking

## What was built
The mapping review page now surfaces which destination fields (from the DDL) have no binding at
all, and code generation refuses to proceed if a required one is left unmapped.

### Key changes
- **Unmapped destination list (UI)**: pure frontend derived calculation —
  `table.destinationFields.filter(f => !table.bindings.some(b => b.destinationField === f))` —
  rendered inside the existing "Unmapped source fields" amber warning box. No backend change
  needed; `MappingSnapshot.destination_fields` was already parsed from the DDL and sent to the
  frontend. Recomputes instantly on every render, so removing a mapping makes the field reappear
  immediately.
- **Codegen gate**: `generate_codegen_artifact` (`codegen/service.py`) computes
  `set(destination_fields) - set(mapped_dest_fields)`, and — using newly added DDL nullability
  parsing — throws a validation error and halts SP generation for a table if any unmapped
  destination field is `NOT NULL` with no default.
- **DDL nullability extraction**: `_parse_all_ddl_tables` previously discarded everything but
  column names; extended to also capture and return `NOT NULL`/`DEFAULT` per column, consumed
  only by the codegen gate (not persisted on `MappingSnapshot.destination_fields`, which stays
  `list[str]` to avoid breaking existing consumers).
- **Sequencing**: implemented after 001dy, so the unmapped-fields check is written against the
  final 1-to-N-aware binding structure from the start.

## Verification
Confirmed via code review: the frontend calculation needs no backend round-trip; the codegen gate
correctly re-parses the destination DDL live rather than mutating the shared `destination_fields`
field's shape.
