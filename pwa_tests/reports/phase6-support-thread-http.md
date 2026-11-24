# Phase 6Q proof: private support-thread HTTP boundary

Date: 2026-07-29

Revision: `0b09eb4` — strict runtime contracts, authenticated Student/Staff
routes and an audience-aware browser client over the accepted support-thread
persistence boundary.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted boundary

- An authenticated Student can create a problem-specific or general lesson
  question, read the resulting private chronological thread and append another
  text entry. Student identity always comes from the authenticated principal;
  identity fields supplied by a client are rejected by the strict request
  shape.
- An authorized Teacher or administrator can read and reply to an exact thread
  only within current Staff course/group scope. The server, not the request,
  assigns the reply author ID and the `teacher`/`admin` author kind.
- Student and Staff use separate audience routes and path-scoped cookies. A
  browser cannot accidentally send one audience cookie to the other audience's
  API, so a cross-audience request is anonymous and returns `401`.
- All request and response payloads are versioned and runtime-validated. Unknown
  fields, inconsistent problem/general context, invalid public IDs, non-UTC
  timestamps, blank text and oversized bodies fail closed.
- Responses expose public IDs only, keep entries in chronological order and
  prove that `latestEntryAt` equals the chronological tail. Repository
  not-found, scope and idempotency conflicts map to stable `404`, `403` and
  `409` API errors with correlation IDs.
- The shared browser client rejects Family construction, chooses the Student or
  Staff API base from verified runtime configuration, retries once after a
  successful session refresh and validates both success and error envelopes.
- TanStack Query keys include audience and account identity. Successful create
  and append mutations update only the matching account-scoped thread cache.
- This increment adds no list/inbox route, realtime invalidation, notification,
  attachment, local draft UI or Telegram compatibility write.

Implementation and executable specification:

- `apps/pwa_api/support_routes.py`
- `apps/pwa_app.py`
- `vmshpwa/packages/contracts/src/support.ts`
- `vmshpwa/packages/contracts/src/support.test.ts`
- `vmshpwa/packages/app-shell/src/support-client.ts`
- `vmshpwa/packages/app-shell/src/support-client.test.ts`
- `pwa_tests/integration/test_support_thread_http_api.py`
- `pwa_tests/integration/test_support_thread_repository.py`

## Executable evidence

- Focused contract/client tests: **5 passed**.
- Focused authenticated HTTP and repository tests: **9 passed**.
- `make pwa-lint`: **PASS** for ESLint and Stylelint.
- `make pwa-typecheck`: **PASS** for route generation, all applications,
  packages and tool configuration.
- `make pwa-test`: **409 frontend tests passed** and **1290 PWA Python tests
  passed / 3 intentional skips / 1 existing SymPy deprecation warning**.
- `make pwa-build`: **PASS** for Student, Family and Staff production builds;
  Student and Family each produced an `injectManifest` service worker.
- Targeted Ruff format/check and `git diff --check`: **PASS**.
- `make pwa-schema-check`: **PASS**, 338 product objects, SHA-256
  `d968c6a5ec83bbebc695619bc010cba850af335ea50c0698f8198fad9a7baaba`.
  This HTTP increment has no migration or schema change.

## Still open in the support flow

- paginated Student history and Staff unanswered/inbox projections;
- owner/scoped realtime invalidation and notification delivery;
- reload-safe Student/Staff draft persistence, application pages, Storybook
  interactions and three-browser production-build E2E;
- attachment upload through the existing media proxy;
- characterized Telegram dual-write/mapping to legacy `questions` and
  historical negative-problem/SOS paths.

This proof accepts the authenticated wire boundary for one exact private
support thread, not the complete Phase 6 questions experience.
