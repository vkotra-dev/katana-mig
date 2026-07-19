---
type: Task
status: Ready
created_at: 2026-07-19
title: Fix shared lookup fibers missing data on Feed page
---

# Fix shared lookup fibers missing data on Feed page

**Problem:**
When a lookup fiber is shared across feeds (e.g. `country_code`), the Review page correctly displays the shared `LookupValueMap`. However, the Feed page auto-creates a new `ProjectFiber` for the current feed, which has no `LookupSourceEntry` or `LookupDestFeed` rows associated with it. This causes the UI to show an empty lookup fiber card on the Feed page, even though it was already mapped by another feed.

**Expected Behavior:**
The Feed page should pull in the existing source values and destination CSV from the shared `LookupValueMap` (or the original fiber) so the user sees the existing shared mapping context.

**Scope:**
1. Fetch `LookupValueMap` records on the Feed page.
2. If a local fiber has no source/dest entries, fallback to populating the UI draft state using the global `LookupValueMap` data (reconstructing source values and destination CSV).
