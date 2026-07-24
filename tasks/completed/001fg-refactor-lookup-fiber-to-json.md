# Task 001fg: Refactor Fiber AI Discovery to ProjectFiber.proposed_mappings JSON

- **Plan**: [2026-07-24-001fg-refactor-lookup-fiber-to-json.md](../plans/2026-07-24-001fg-refactor-lookup-fiber-to-json.md)
- **Domain**: [governance.md](../docs/domain/governance.md)

## Objective
Refactor `_analyze_lookup_fiber()` and `_bridge_lookup_fiber_to_value_map()` in `engine/src/migrations_engine/management/fibers.py` to store transient AI discovery proposals directly in `ProjectFiber.proposed_mappings` (`JSON list[dict]`), eliminating SQL inserts into transient relational tables.

## Requirements
1. Update `_analyze_lookup_fiber()` to write proposals directly to `fiber.proposed_mappings`.
2. Update `_bridge_lookup_fiber_to_value_map()` to construct `LookupValueMap` draft records directly from `fiber.proposed_mappings`.
3. Update fiber API endpoints and backend unit tests (`test_lookup_fiber_api.py`) to consume `proposed_mappings`.
4. Ensure all backend tests pass 100%.
