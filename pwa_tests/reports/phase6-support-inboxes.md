# Phase 6R proof: scoped support history and inbox projections

Date: 2026-07-29

Revision: `58904b4` — owner-scoped Student history, current-scope Staff inbox,
strict filters, cursor pagination and account-isolated infinite-query clients.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted boundary

- Student history lists only the authenticated Student's threads, newest
  activity first. Historical own conversations remain listed after access to a
  former group is revoked.
- Staff list queries are restricted in SQLite to the server-resolved current
  course/group scope. A Teacher cannot use filters or a cursor to list another
  group's private questions; a global administrator may list all scopes.
- There is still no mutable ticket status and no Teacher assignment. The
  projection derives `awaiting_staff` when the latest author is the Student,
  `awaiting_student` after a Teacher/admin reply and `activity` for a system
  entry.
- Staff defaults to the actionable `awaiting_staff` inbox and can explicitly
  select all activity or items awaiting the Student, then narrow by thread kind,
  course and group. Unknown and duplicate query parameters fail closed.
- List items contain public identities, exact course/group/lesson/problem
  provenance, latest-author/excerpt/time, entry count and thread version. They
  do not serialize internal SQLite IDs or the full private dialogue.
- Both lists use a validated opaque public-ID cursor and return at most 50
  records per page. A cursor outside the effective owner/scope/filter result is
  rejected rather than becoming a cross-scope capability.
- TypeScript contracts independently verify that reply state matches the latest
  author and that problem context matches thread kind. TanStack infinite-query
  keys include audience, account and normalized Staff filters; successful
  mutations invalidate the matching account's list projection.
- No thread UI, local drafts, realtime publication, notification, attachment or
  Telegram compatibility write is added by this increment.

Implementation and executable specification:

- `db_methods/pwa/support.py`
- `apps/pwa_api/support_routes.py`
- `vmshpwa/packages/contracts/src/support.ts`
- `vmshpwa/packages/contracts/src/support.test.ts`
- `vmshpwa/packages/app-shell/src/support-client.ts`
- `vmshpwa/packages/app-shell/src/support-client.test.ts`
- `pwa_tests/integration/test_support_thread_repository.py`
- `pwa_tests/integration/test_support_thread_http_api.py`

## Executable evidence

- Focused repository and authenticated HTTP tests: **13 passed**.
- Focused contract/client tests: **8 passed**.
- `make pwa-lint`: **PASS** for ESLint and Stylelint.
- `make pwa-typecheck`: **PASS** for route generation, all applications,
  packages and tool configuration.
- `make pwa-test`: **412 frontend tests passed** and **1294 PWA Python tests
  passed / 3 intentional skips / 1 existing SymPy deprecation warning**.
- `make pwa-build`: **PASS** for Student, Family and Staff production builds;
  Student and Family each produced an `injectManifest` service worker.
- Targeted Ruff format/check and `git diff --check`: **PASS**.
- `make pwa-schema-check`: **PASS**, 338 product objects, SHA-256
  `d968c6a5ec83bbebc695619bc010cba850af335ea50c0698f8198fad9a7baaba`.
  The inbox is a read projection over the existing Phase 6P schema.

## Still open in the support flow

- owner/scoped realtime invalidation and notification delivery;
- reload-safe Student/Staff draft persistence, application pages, Storybook
  interactions and three-browser production-build E2E;
- attachment upload through the existing media proxy;
- characterized Telegram dual-write/mapping to legacy `questions` and
  historical negative-problem/SOS paths.

This proof accepts list privacy, derivation and transport behavior, not the
complete Phase 6 questions experience.
