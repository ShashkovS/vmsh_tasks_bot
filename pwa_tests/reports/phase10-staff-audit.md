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
- Course/group create and edit now use that same boundary. Failed duplicate or stale
  requests append nothing; if the audit insert fails, the catalog write rolls back.
- Telegram binding create/edit/disable/restore/verify records the old and new owner,
  destination, purpose and status in the same transaction. No bot credential is part
  of the binding row or its audit projection.
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
- Full Python gate in 8 isolated pytest workers: **1523 passed, 5 skipped**.
- Frontend unit suite: **106 files, 578 tests passed**.
- Storybook browser mode with a11y error gate: **48 files, 231 tests passed**;
  stories `Pages/Staff/Audit--SearchableTimeline` and `--EmptySearch`.
- Production-build authentication E2E: **84 passed, 12 intentionally skipped** in
  Chromium, WebKit and Firefox. It proves admin search/expand, teacher denial and the
  real aiohttp/SQLite path without MSW.
- `make pwa-lint`, `make pwa-typecheck`, schema generation/check and production build
  passed for this slice.

Catalog coverage increment:

- focused aiohttp catalog/audit suite: **7 passed**;
- focused frontend unit: **3 passed**;
- focused Storybook interaction/a11y: **2 passed**;
- real object filters: `course` and `group`.

Telegram binding coverage increment:

- focused Telegram binding/audit aiohttp suite: **7 passed**;
- full Python PWA regression: **1523 passed, 5 skipped** in **81.35 seconds**;
- frontend unit: **106 files, 578 passed**;
- focused audit client: **3 passed**;
- focused Storybook interaction/a11y: **2 passed**;
- lint, strict TypeScript and production builds: passed;
- real object filter: `telegram_binding`.

Problem-synonym coverage increment:

- merge and split append a compact summary at the same SQLite transaction
  boundary as the versioned membership history;
- original problems, submissions and results remain untouched, and the detailed
  synonym membership history remains authoritative;
- a synthetic audit-insert failure rolls back the complete merge;
- focused synonym/audit aiohttp suite: **6 passed**;
- full Python PWA regression: **1524 passed, 5 skipped** in **97.44 seconds**;
- frontend unit: **106 files, 578 passed**;
- focused Storybook interaction/a11y: **2 passed**;
- lint, strict TypeScript and production builds: passed;
- real object filter: `problem_synonym`.

## Explicit remaining scope

This slice does not yet claim complete audit coverage of every older Staff mutation.
Schedules, classroom planning/news moderation and future publication/broadcast
writes still need a compact audit append at their existing transaction boundary.
Schedule writes currently commit inside the older `PwaContentRepository`; auditing
them atomically is deliberately deferred instead of adding a second non-atomic write
or expanding that module during this increment. Their domain-specific histories
remain unchanged and authoritative meanwhile.

No visual baseline was updated. Owner visual approval of the dense desktop/mobile
table remains open.
