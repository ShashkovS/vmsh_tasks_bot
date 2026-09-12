# Phase 6J proof: atomic written-submission review handoff

Date: 2026-07-28

Revision: `9f3ce4c` — atomic Student submission-to-review-queue handoff,
owner/Staff invalidations and production-build browser coverage.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted boundary

- A successful PWA written-entry submission and its legacy-compatible
  `written_tasks_queue` case are committed in one SQLite transaction. Staff
  cannot observe a reviewable immutable submission without a queue case.
- The queue keeps one row per `(student_id, problem_id)`. An exact
  idempotency replay returns the stored receipt and creates no duplicate.
- A later submitted entry updates the existing case without changing its
  original waiting timestamp. Queue ordering therefore cannot be reset by a
  resubmission.
- A later entry does not steal or silently reset an active Staff claim. Its
  claim token, reviewer, lease timestamps and lease version remain unchanged;
  review completion detects the changed thread version and requires the
  reviewer to refetch the complete evidence.
- The database commit is authoritative. After it succeeds, the runtime emits
  an owner-scoped Student thread invalidation and an audience-scoped Staff
  `review-queue` invalidation. Broker delivery is a refetch hint, not the
  durable queue.
- This increment does not merge synonymous problem branches or change the
  legacy Telegram review adapter.

Implementation:

- `db_methods/pwa/written_submissions.py`
- `apps/pwa_app.py`
- `pwa_tests/integration/test_submission_repository.py`
- `pwa_tests/integration/test_content_http_api.py`
- `pwa_tests/test_pwa_app.py`
- `vmshpwa/e2e/test-submission.spec.ts`

## Executable evidence

- Ruff, ESLint, Stylelint, workspace TypeScript and `git diff --check`:
  **PASS**.
- Python PWA suite: **1260 passed / 3 intentional skips / 1 existing SymPy
  deprecation warning**.
- Student, Family and Staff production builds: **PASS**. Student and Family
  `injectManifest` service workers were generated.
- Focused production-build command `make pwa-e2e-submissions`: **9 passed** —
  three scenarios in Chromium, WebKit and Firefox.
- The written browser scenario creates a real Student draft, compresses and
  uploads a photo, survives reload/offline delivery, submits and replaces the
  entry, then opens the existing Staff session and proves that exactly one
  review row exists without compatibility seeding.
- The HTTP review/Family integration now claims the queue case produced by
  the Student submit itself; it no longer inserts `written_tasks_queue`
  manually.
- Repository tests prove generated opaque queue IDs, strict replay, original
  wait-age preservation and active-lease preservation.
- Invalidation tests prove the exact Student owner and Staff audience payloads;
  the HTTP cursor test proves both audiences advance only on the committed
  submission.

Known non-blocking build/runtime output:

- the existing Student chunk-size warning;
- the existing Workbox/Rolldown `inlineDynamicImports` deprecation;
- transient closed-transport WebSocket relay assertions in the E2E gateway;
  all nine browser assertions still pass and the gateway issue is not part of
  this handoff contract.

## Still open in Phase 6

- Family live invalidation after review completion;
- merged synonymous timelines and combined review cases with provenance;
- Student reactions and the admin complaint/appeal view;
- durable notification outbox dispatch;
- explicit product policy for attachment mutation while a review is actively
  claimed;
- visual snapshot acceptance by the product owner.

This proof accepts the atomic submission-to-review-queue boundary, not Phase 6
as a whole.
