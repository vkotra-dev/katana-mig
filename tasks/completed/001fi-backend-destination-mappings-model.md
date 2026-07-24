# Task 001fi: Backend DB Schema & API Endpoints for `destination_mappings` 1-to-Many Model

- **Plan**: [2026-07-24-001fi-backend-destination-mappings-model.md](../plans/2026-07-24-001fi-backend-destination-mappings-model.md)
- **Domain**: [governance.md](../docs/domain/governance.md)

## Objective
Refactor `LookupValueMap` and `LookupSnapshot` backend DB models (`db/models.py`), Pydantic API schemas (`api/schemas.py`), and routes (`routes/lookup_mapping.py`) to natively store and manage 1-to-Many Destination-Anchored mappings (`destination_mappings: list[dict]`). Add backend PATCH actions for adding/removing source values per destination, updating `lookup_upsert.py` and `fibers.py` bridge logic.

## Requirements
1. Update `LookupValueMap` DB model in `db/models.py` to add `destination_mappings` (`JSON list[dict]`).
2. Update Pydantic schemas in `api/schemas.py` and PATCH route in `lookup_mapping.py` to support discrete 1-to-Many actions (`add_source_value`, `remove_source_value`, `move_source_value`).
3. Update `_bridge_lookup_fiber_to_value_map()` in `fibers.py` to build `destination_mappings` directly.
4. Update `lookup_upsert.py` SQL codegen generator to flatten `destination_mappings` into `INSERT INTO ref_table (source_val, dest_val) VALUES ...`.
5. Ensure 100% backend test suite health (`pytest` passes 100%).
