# 001d-minimal-mapping-slice

## Domain

- [source-model.md](/Users/vjkotra/projects/katana/docs/domain/source-model.md)
- [runs.md](/Users/vjkotra/projects/katana/docs/domain/runs.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)

## Objective

Implement the smallest governed mapping slice: one approved mapping path, one
unmapped-value failure path, and explicit run-record provenance for what was
used.

## Scope

- Approved mapping snapshot selection
- A narrow end-to-end mapping artifact path
- Unmapped-value handling through the governed delta path
- Run history recording for mapping provenance

## Out of Scope

- Full code generation
- Reconciliation expansion beyond the mapping slice needed to prove lineage
- Source-adapter broadening across every source type
- UI redesign outside the minimal mapping review surfaces

## Acceptance Criteria

- Mapping consumes approved, immutable snapshots
- A known mapping case completes end to end
- An unmapped value fails through the governed `LookupDeltaCR` path
- Mapping provenance is recorded in the run history

## Test Expectations

- Approved mapping path produces the expected mapping artifact
- Unmapped value path raises the governed delta condition
- Mapping artifacts remain immutable after approval
- Run records identify the mapping snapshot version used

