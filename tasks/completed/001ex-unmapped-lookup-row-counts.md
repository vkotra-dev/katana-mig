---
type: Task
id: 001ex
slug: 001ex-unmapped-lookup-row-counts
title: Display unmapped row counts for lookups
status: ready
domain: docs/domain/governance.md
plan: plans/2026-07-23-001ex-unmapped-lookup-row-counts.md
---

## Context
When an operator is reviewing lookup mappings, they currently cannot see how many source rows are affected by values that were left unmapped (or mapped to `null`). To avoid a proliferation of JSON tracking columns across mapping models, the architectural decision is to store row-frequency profiles centrally in the `FeedSlice` data ingestion layer, and have the backend compute the unmapped row count on the fly when returning `LookupValueMap` API responses.

## Objective
1. Add a `data_profile` JSON column to the `FeedSlice` model to store source column row frequencies.
2. Update the `GET /projects/{id}/lookup-maps` backend endpoint to calculate and append `unmapped_row_count` to the response DTO.
3. Update the UI to display this `unmapped_row_count` prominently in both the Feed Page (Lookup Fibers cards) and the Review Page (LookupMappingTable component).

## Out of Scope
- Actually implementing the PySpark/Pandas ingestion logic to *populate* the `data_profile`. For this task, assume it can be populated and just test with a mocked `data_profile` in the DB.
- Any changes to `LookupValueMap` database schema.

## Acceptance
- The backend `LookupValueMapResponse` schema includes an `unmapped_row_count` integer.
- The `LookupMappingTable` on the Review page displays a warning badge (e.g., "⚠️ 1,250 unmapped rows") if the count is > 0.
- The Lookup Fiber card on the Feed page displays the same warning badge.
- The calculation dynamically joins the `source_value_map` against the `FeedSlice.data_profile` based on the lookup foreign key column.
