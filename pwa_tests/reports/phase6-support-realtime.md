# Phase 6S proof: owner- and scope-targeted support realtime

Date: 2026-07-29

Revision: `7c4b841` — private support mutations now publish account-targeted
invalidation only after the SQLite transaction has committed.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted boundary

- Creating a question or appending a Student/Staff entry invalidates the
  authenticated Student owner's active accounts and the active Staff accounts
  that currently cover the thread's course/group scope.
- Global administrators are included. Teachers scoped to another group,
  revoked scopes, Family accounts and audience-wide broadcasts are excluded.
- The broker payload contains public account IDs and public resource names; it
  does not expose SQLite IDs or private course/group scope metadata.
- Both the list resource `questions` and the exact dialogue resource
  `questions/{threadPublicId}` are invalidated so list badges and an open
  conversation converge together.
- SQLite remains authoritative. Recipient lookup or broker failure after a
  successful commit is logged, but the mutation still returns success; an
  unsafe client retry cannot duplicate a private message.
- Recipient scope is resolved at publication time rather than copied into the
  thread. A later Staff scope revocation therefore takes effect immediately.
- This increment intentionally adds invalidation/refetch, not Web Push or a
  durable event log. Reconnect still performs an authoritative SQLite refetch.

Implementation and executable specification:

- `db_methods/pwa/support.py`
- `apps/pwa_api/support_routes.py`
- `apps/pwa_app.py`
- `pwa_tests/integration/test_support_thread_repository.py`
- `pwa_tests/integration/test_support_thread_http_api.py`
- `pwa_tests/test_pwa_app.py`

## Executable evidence

- Focused repository, authenticated aiohttp and broker tests: **51 passed**.
- `make pwa-lint`: **PASS** for ESLint and Stylelint.
- `make pwa-typecheck`: **PASS** for route generation, all applications,
  packages and tool configuration.
- `make pwa-test`: **412 frontend tests passed** and **1297 PWA Python tests
  passed / 3 intentional skips / 1 existing SymPy deprecation warning**.
- `make pwa-build`: **PASS** for Student, Family and Staff production builds;
  Student and Family each produced an `injectManifest` service worker.
- Targeted Ruff format/check and `git diff --check`: **PASS**.
- `make pwa-schema-check`: **PASS**, 338 product objects, SHA-256
  `d968c6a5ec83bbebc695619bc010cba850af335ea50c0698f8198fad9a7baaba`.
  Realtime targeting is a read projection and adds no schema object.

## Still open in the support flow

- reload-safe Student/Staff draft persistence, application pages, Storybook
  interactions and three-browser production-build E2E;
- attachment upload through the existing media proxy;
- notification delivery policy beyond foreground invalidation;
- characterized Telegram dual-write/mapping to legacy `questions` and
  historical negative-problem/SOS paths.

This proof accepts the private realtime boundary and failure semantics, not the
complete Phase 6 questions experience.
