# Phase 10 · searchable Staff audit

Date: 2026-08-02.

## Shipped slice

- Migration [`0075.pwa_staff_audit.sql`](../../migrations/0075.pwa_staff_audit.sql)
  adds one small append-only `audit_events` index. Existing domain journals remain
  the detailed source of provenance; no queue, repository hierarchy or universal
  event framework was introduced.
- Admin account creation/status/credential changes, Family links, course-enrollment
  changes and problem-import apply/rollback append the audit row in the same SQLite
  transaction as the administrative write.
- [`GET /staff/api/v1/audit`](../../apps/pwa_api/audit_routes.py) is admin-only and
  supports object filtering, request/action/object search and stable cursor paging.
- The safe projection in [`models/pwa/audit.py`](../../models/pwa/audit.py) accepts
  only flat primitive before/after values and rejects credential/password/secret/token
  keys before they can reach the browser.
- [`StaffAuditPage`](../../vmshpwa/apps/staff/src/staff-audit-page.tsx) replaces the
  placeholder route with validated URL state, dense Staff table, actor/request ID and
  expandable before/after values.

## Automated proof

- Python focused domain/API/migration/auth/import/account/enrollment suite: **62 passed**.
- Full Python gate in 8 isolated pytest workers: **1521 passed, 5 skipped**.
- Frontend unit suite: **106 files, 577 tests passed**.
- Storybook browser mode with a11y error gate: **48 files, 231 tests passed**;
  stories `Pages/Staff/Audit--SearchableTimeline` and `--EmptySearch`.
- Production-build authentication E2E: **84 passed, 12 intentionally skipped** in
  Chromium, WebKit and Firefox. It proves admin search/expand, teacher denial and the
  real aiohttp/SQLite path without MSW.
- `make pwa-lint`, `make pwa-typecheck`, schema generation/check and production build
  passed for this slice.

## Explicit remaining scope

This slice does not yet claim complete audit coverage of every older Staff mutation.
Course/group catalog, schedules, Telegram bindings, synonym operations, classroom
planning/news moderation and future publication/broadcast writes still need a compact
audit append at their existing transaction boundary. Their domain-specific histories
remain unchanged and authoritative meanwhile.

No visual baseline was updated. Owner visual approval of the dense desktop/mobile
table remains open.
