# Phase 6L proof: live Staff review-queue synchronization

Date: 2026-07-28

Revision: `09edec7` — Staff-scoped claim/release invalidations, resource-aware
realtime query routing and independent two-account browser coverage.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted boundary

- A successful claim publishes one Staff-scoped `review-queue` invalidation
  after SQLite commits the lease. Other reviewers therefore see who owns the
  case without polling.
- A successful release publishes the same Staff-scoped resource after the
  lease is removed. A conflicting claim, a foreign release and a heartbeat do
  not advance the Staff cursor. In particular, the five-minute heartbeat does
  not create an avoidable fleet-wide refetch loop.
- Review completion reuses the same queue publisher after its atomic result,
  evidence and queue-removal transaction. Submission, claim, release and
  completion now share one public Staff queue resource.
- Ordinary WebSocket invalidations coalesce the union of their resource names.
  Queries may opt into exact resource routing; unlabelled queries keep the
  conservative full-invalidation behaviour for compatibility.
- The mutation-backed review lease deliberately ignores ordinary invalidation
  frames. This prevents a Staff claim event from recursively claiming the same
  work and changing its optimistic version immediately before completion.
  Reconnect still refetches every active query from SQLite, and completion
  still rejects genuinely changed evidence.
- The E2E network guard now provides an independent secondary browser context.
  Teacher and admin therefore use distinct Staff cookies while both contexts
  retain the literal-loopback-only network policy.

Implementation:

- `apps/pwa_api/review_routes.py`
- `apps/pwa_app.py`
- `vmshpwa/packages/app-shell/src/realtime.tsx`
- `vmshpwa/packages/app-shell/src/review-queue-client.ts`
- `vmshpwa/e2e/fixtures.ts`
- `vmshpwa/e2e/review-workspace.spec.ts`
- `pwa_tests/integration/test_review_queue_http_api.py`
- `pwa_tests/test_pwa_app.py`
- `vmshpwa/packages/app-shell/src/realtime-client.test.ts`

## Executable evidence

- `make pwa-lint` and `make pwa-typecheck`: **PASS**.
- `make pwa-test`: **397 frontend tests passed** and **1263 PWA Python tests
  passed / 3 intentional skips / 1 existing SymPy deprecation warning**.
- The production build inside `make pwa-e2e-review`: **PASS** for Student,
  Family and Staff; both `injectManifest` service workers were generated.
- `make pwa-e2e-review`: **3 passed**, one complete two-Staff-account review
  flow in Chromium, WebKit and Firefox.
- The second Staff session first sees `Открыть`, changes live to
  `Проверяет Преподаватель Тестовый` after the Teacher claim, and removes the
  row live after completion. The same test continues to prove Student and
  Family owner-scoped completion projections.
- HTTP cursor assertions prove exactly one Staff increment for each successful
  claim and release, and no increment for conflict, foreign release or
  heartbeat.
- Realtime unit coverage proves coalescing of `lesson.current` and `news`,
  exact resource matching, the conservative unlabelled fallback and the
  reconnect-only empty resource set.
- `git diff --check`: **PASS**. Visual snapshots were not updated.

Known non-blocking build output remains unchanged: the Student chunk-size
warning and the Workbox/Rolldown `inlineDynamicImports` deprecation.

## Still open in Phase 6

- proactive invalidation when a lease expires without an explicit release;
- merged synonymous timelines and combined review presentation with full
  provenance;
- Student reactions and the admin complaint/appeal view;
- durable notification outbox and the agreed batched Student notification;
- correction/recheck policy, historical Telegram backfill and composite PNG;
- visual snapshot acceptance by the product owner.

This proof accepts live queue-lock consistency for active Staff sessions, not
Phase 6 as a whole.
