# Phase 6F proof: live Staff review workspace and durable browser draft

Date: 2026-07-28

Revisions:

- `e2e3882` — review API exposes the complete conversation timeline and
  course/group/problem provenance separately from the immutable evidence
  snapshot;
- `c5dff65` — Staff queue/workspace routes, lease lifecycle, real review
  completion and reload-safe local draft;
- `016ac9b` — deterministic review seed and production-build Playwright flow in
  Chromium, WebKit and Firefox.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted boundary

- `/staff/review` is a live, scoped queue rather than a prototype list. It
  supports oldest/newest ordering, logical synonym cases and explicit claim.
- `/staff/review/{queuePublicId}` claims the logical case, displays its exact
  evidence and the full chronological conversation, and identifies the source
  course, group and problem for every branch. Synonymous submissions are still
  stored against their original problems.
- The workspace renews its lease while open and offers an explicit release.
  Completion sends the exact queue/branch/evidence versions returned by the
  server; lease, scope and stale-evidence conflicts remain fail-closed.
- A review draft is scoped by runtime instance, Staff account, logical case and
  immutable evidence fingerprint. Comment, verdict, internal reaction, future
  annotation manifests and the stable idempotency key survive a page reload.
  A different account or changed evidence cannot inherit the draft.
- Successful completion clears the draft. Release, network failure and
  optimistic conflict preserve it so significant Teacher work is not lost.
- The shared `ReviewFeedbackForm` accepts restored state and reports draft
  changes without importing application or domain code into `packages/ui`.
- The review navigation item is shown only with `review.write`; HTTP scope
  remains authoritative and returns `403` for forbidden access.

Implementation:

- `apps/pwa_api/review_routes.py`
- `db_methods/pwa/reviews.py`
- `vmshpwa/apps/staff/src/review-queue-page.tsx`
- `vmshpwa/apps/staff/src/review-workspace-page.tsx`
- `vmshpwa/apps/staff/src/review-draft.ts`
- `vmshpwa/packages/contracts/src/review-queue.ts`
- `vmshpwa/packages/product/src/review-feedback-form.tsx`
- `vmshpwa/e2e/review-workspace.spec.ts`
- `vmshpwa/scripts/seed_e2e_review.py`

## Executable evidence

- ESLint, Stylelint and workspace TypeScript: **PASS**.
- Frontend unit suite: **51 files / 384 passed**.
- Python PWA suite: **1256 passed / 3 intentional skips / 1 existing SymPy
  deprecation warning**.
- Storybook browser suite: **39 files / 191 passed**. It includes restored
  review-draft interaction coverage.
- Student, Family and Staff production builds: **PASS**; Student and Family
  `injectManifest` service workers were generated.
- Focused production-build Playwright command `make pwa-e2e-review`: **3 passed**
  — one independent real-aiohttp case in each of Chromium, WebKit and Firefox.
- Seed/runner guards: **10 passed** across the focused runner and review-seed
  tests.
- `git diff --check`: **PASS** for the accepted code and report increment.

The browser scenario logs in as a scoped Teacher, opens the real queue row,
claims it, observes an earlier Teacher question and later Student reply, edits
the comment/verdict/internal reaction, reloads the page, proves exact draft
restoration, completes through the real API and verifies that the queue case
disappears.

## Full-suite context

A separate pre-existing full non-visual Playwright run completed with **148
passed and 8 failed**. The focused Phase 6 scenario and the Staff shell/deep
link checks passed in all browsers. The remaining failures are outside this
increment:

- three runtime-isolation assertions still assume that the runtime-config
  localStorage cache keys do not exist;
- one Phase 5 written-photo draft scenario timed out;
- the remaining content-publication/Phase-4 repair timeouts occurred in
  Firefox.

Those failures are recorded rather than hidden, but they do not invalidate the
three-browser Phase 6 acceptance proof above.

## Still open in Phase 6

- interactive photo-annotation editing, undo/redo and rendering of the
  canonical immutable manifests in Student, Family and Staff;
- Student reactions and the admin complaint/appeal view;
- historical Telegram review/reaction backfill and duplicate-resolution report;
- durable outbox dispatch for review notifications;
- correction/recheck policy and Telegram composite-PNG derivative;
- repair of the unrelated full Playwright failures listed above.

This proof accepts the live written-review workspace and its no-data-loss draft
boundary, not Phase 6 as a whole.
