# Phase 6 proof: immutable written-review corrections

Date: 2026-08-02

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted boundary

- A completed written review is never edited in place. A correction appends a
  new review, result and optional Teacher/Admin comment while preserving the
  original review, evidence snapshot, photos, annotations and thread history.
- A Teacher may correct only their own latest review within the current Staff
  scope. A global Admin may recheck any latest review visible in that scope.
  A stale source review returns `409`; an out-of-scope request returns `403`.
- Idempotent replay returns the already-created correction. Reusing the same
  idempotency key with a different payload returns `409`.
- The admin reaction inbox exposes the exact source evidence and marks an item
  stale once a newer review exists. It does not offer a correction action for
  that stale item.
- The Staff form starts with the original verdict and exact comment, shows the
  source text and photographs, and stores the unfinished correction in
  account-scoped `localStorage`. Reloading the page does not lose the draft or
  create a second idempotency key.
- Student and Family see both reviews in the common history and the corrected
  current status. The Student receives the normal result notification; the
  Family projection is refreshed without a Family push.
- Earlier positive legacy `results` rows are retired before the replacement is
  appended because existing legacy readers select the best positive result.
  The immutable review history remains the source of the exact old verdict.

Implementation:

- `models/pwa/review_corrections.py` — correction policy and one transaction;
- `db_methods/pwa/review_corrections.py` — small mechanical SQLite operations;
- `apps/pwa_api/review_routes.py` — validation, authorization mapping,
  notifications and owner-scoped invalidation;
- `db_methods/pwa/reviews.py` — current/stale marker and bounded source-evidence
  projection for the reaction inbox;
- `vmshpwa/packages/contracts/src/review-reactions.ts` — runtime contracts;
- `vmshpwa/packages/app-shell/src/review-queue-client.ts` — HTTP client and
  mutation hook;
- `vmshpwa/apps/staff/src/review-reaction-inbox-page.tsx` — source evidence,
  reload-safe correction draft and submit flow;
- `vmshpwa/e2e/review-workspace.spec.ts` — real browser flow.

No migration was needed: the implementation deliberately reuses the existing
append-only review/result/evidence tables.

## Storybook evidence

- `product-review-reaction-inbox--already-rechecked` demonstrates that an old
  reaction remains inspectable but cannot start a second correction.
- The current-reactions story exercises opening a correction from an eligible
  item.
- `make pwa-storybook-test`: **47 files / 226 tests passed** in browser mode;
  accessibility violations remain errors.
- Visual snapshots were not updated and still require owner review.

## Executable evidence

- Targeted current backend suite: **41 passed** for the repository and real
  aiohttp API correction/inbox paths.
- Full `make pwa-test` run during this increment: **1490 Python tests passed,
  5 skipped** and **565 frontend tests passed**. After the final evidence-field
  adjustment, the targeted backend suite and the complete frontend suite were
  rerun successfully.
- `make pwa-typecheck`: **PASS**.
- `make pwa-lint`: **PASS** for ESLint and Stylelint.
- Targeted Ruff check for every changed Python module/test: **PASS**.
- `make pwa-storybook-test`: **47 files / 226 tests passed**.
- `make pwa-e2e-review`: **3 passed** in Chromium, WebKit and Firefox against
  a real seeded aiohttp/SQLite runtime and production frontend builds, without
  MSW. The flow proves source-photo visibility, correction draft restoration
  after reload, append-only submit, stale-action removal, Student/Family
  history and the `written-review-corrected` realtime refresh.
- Student and Family `injectManifest` service workers were built successfully
  as part of the E2E production-build startup.
- `git diff --check`: **PASS** before commit.

## Still open in Phase 6

- rehearsed legacy reaction backfill and duplicate report;
- Telegram composite image for an annotated written review;
- an explicit decision table for the idea-only `viewwrittensols*` artifacts;
- owner visual acceptance of the review and correction screens.

This proof accepts the written correction/admin-recheck vertical slice, not
Phase 6 as a whole.
