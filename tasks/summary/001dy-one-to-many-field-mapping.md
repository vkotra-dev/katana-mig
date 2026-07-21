# Summary: 001dy — One-to-Many Source-to-Destination Field Mapping

## What was built
Operators can now map a single source field to multiple destination fields (e.g. a source
`ADDRESS` field populating both `billing_address` and `shipping_address`).

### Key changes
- **Sign-off re-keying**: `MappingBindingSignOff`'s unique constraint moved from
  `(mapping_snapshot_id, destination_object_name, source_field, user_id)` to also include
  `destination_field`, via a hand-written Alembic migration. `sign_binding`/`unsign_binding` and
  `get_sign_off_status`'s `b_map` now operate on `(source_field, destination_field)` pairs
  instead of collapsing multiple bindings under one source field.
- **`patch_mapping` re-keyed**: diffing (`existing_by_src` → `existing_by_pair`) and the
  changed-fields/sign-off-invalidation check now operate on `(source_field, destination_field)`
  pairs, so a second binding for an already-used source field no longer silently overwrites or
  loses the first.
- **Frontend disambiguation**: `onDestinationFieldChange`/`handleDestinationFieldChange` thread
  the full pair through instead of `sourceField` alone, so editing one of two rows sharing a
  source field no longer blind-copies the change onto both.
- **UI**: "Add Destination" button on the ReviewGrid spawns a new binding row for an existing
  source field; autocomplete excludes destinations already mapped for that specific source field
  to prevent true duplicate rows.
- **AI prompt**: system prompt updated to state a source field MAY map to multiple destination
  fields when it logically populates both (later superseded/reinforced by 001ea's full prompt
  rewrite).

## Verification
Confirmed via code review across three rounds: the sign-off subsystem, `patch_mapping`, and the
frontend edit chain are all re-keyed consistently; no remaining `source_field`-only collapse
points found in `review.py`/`sign_offs.py`/`ReviewGrid.tsx`.
