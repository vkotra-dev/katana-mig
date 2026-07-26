---
id: 002ab
title: Sync docs/domain/security.md against actual codebase
status: pending
created: 2026-07-24
priority: medium
domain: docs
depends-on: []
---

# Sync docs/domain/security.md

## Objective

Update `docs/domain/security.md` to accurately reflect the current security implementation. Last updated 2026-07-16.

## Scope

- `docs/domain/security.md` only

## What to verify

1. **Identity boundary** — Verify auth-derived authorization matches actual route guards
2. **Project boundary** — Verify project isolation enforcement in routes
3. **PII boundary** — Verify PII classification and masking matches `pii_classifier` module
4. **Audit boundary** — Verify audit event emission matches `audit_bus` module
5. **Threat model** — Verify all listed risks are still relevant
6. **Control requirements** — Verify each control requirement has corresponding code
7. **Session invalidation** — Verify the 6 triggers (password change, role change, disable, logout, secret rotation, soft-delete) match actual code

## Out of scope

- Any other domain doc files
- Backend implementation changes

## Acceptance criteria

- [ ] All security boundaries described match actual enforcement
- [ ] Threat model is current
- [ ] Control requirements map to actual code
- [ ] Changelog updated with sync date
- [ ] timestamp updated to current date
