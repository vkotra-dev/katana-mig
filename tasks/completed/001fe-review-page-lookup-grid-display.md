---
type: Task
title: Review Page Lookup Grid Clean Label and Inline Editable Source Display
description: Align Review Page and Feed Page lookup mapping grids to render clean Destination Value (ID) labels (eliminating multi-column pipe gibberish) and provide inline editable text inputs for source values.
tags:
  - lookup-mapping
  - review-page
  - UI
  - governance
timestamp: 2026-07-23
---

# Task 001fe: Review Page Lookup Grid Clean Label and Inline Editable Source Display

## Overview
The Review Page lookup grid currently falls back to joining all non-ID reference row columns with ` | ` (e.g. `"Y | N | APPROVED | Approved | 3"`), producing multi-column gibberish string fallbacks. Additionally, source values should be cleanly editable inline when `editingEnabled` is true so operators can key in or modify source mappings for destination anchor rows.

## Target Artifacts
- Task File: `tasks/001fe-review-page-lookup-grid-display.md`
- Plan File: `plans/2026-07-23-001fe-review-page-lookup-grid-display.md`
- Summary File: `tasks/summary/001fe-review-page-lookup-grid-display.md`
- Completed File: `tasks/completed/001fe-review-page-lookup-grid-display.md`

## Objectives
1. Eliminate multi-column pipe string join fallbacks in `LookupMappingTable.tsx`.
2. Format Column 2 ("Destination Value") consistently as `Destination Value (ID)` (e.g., `Approved (3)`).
3. Render Column 1 ("Source Value") as an inline editable `<input>` when `editingEnabled = true`, pre-filled with `sourceValue` or blank for unmapped rows.
4. Replace raw `JSON.stringify(pm.destRow)` on the Feed Page AI Proposed Mappings with formatted `Destination Value (ID)` badges.
5. Ensure `_bridge_lookup_fiber_to_value_map` in `fibers.py` preserves `label` when building `LookupValueMap.destination_table`.
