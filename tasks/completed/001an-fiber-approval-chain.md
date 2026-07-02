# Task 001an — Fiber Approval Chain

**Plan:** `plans/2026-07-01-001an-fiber-approval-chain.md`

## Domain

- `docs/domain/api.md` — 3-step approval chain: operator assign → business approve → operator trigger codegen

## Scope

Implement the three fiber lifecycle action endpoints and the frontend detail page:

- `POST /fibers/{fiber_id}/assign` — central team sets `status = "operator_assigned"` (from `"mapped"`)
- `POST /fibers/{fiber_id}/approve` — project stakeholder sets `status = "business_approved"` (from `"operator_assigned"`)
- `POST /fibers/{fiber_id}/trigger` — central team sets `status = "operator_triggered"` → `"codegen_complete"`; logs codegen queue message if all sibling fibers are complete
- Frontend: fiber detail page at `/projects/[id]/feeds/[feedId]/fibers/[fiberId]` showing status badge, field-bindings table (domain_object), proposed-mappings panel (lookup), and role+status-gated action buttons

## Tasks (3)

1. **Backend** — `assign_fiber`, `approve_fiber`, `trigger_fiber` in `management/fibers.py`; three POST routes in `routes/fibers.py`.
2. **Frontend API helpers** — `getFiber`, `assignFiber`, `approveFiber`, `triggerFiber` + `FiberRecord` type in `web/lib/feeds-api.ts`.
3. **Fiber detail page** — `web/app/projects/[id]/feeds/[feedId]/fibers/[fiberId]/page.tsx` with status badge, data panels, and gated action buttons.

## Success criteria

- Full chain executes: assign → approve → trigger, each enforcing correct role + prior status
- Wrong-status 409 for out-of-order calls
- Detail page shows correct buttons for each role/status combination
- All tests pass

## Execution order

Execute after 001al and 001am. This is in the feed/fiber/comment/AI priority
stream and should land before the later-phase delivery tickets.
