# Phase 6K proof: review-completion audience fan-out

Date: 2026-07-28

Revision: `9903b65` — current Family recipient resolution, owner-scoped
Student/Family invalidations, shared Staff queue invalidation and live browser
coverage.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted boundary

- Review completion still commits its result, immutable evidence, annotations,
  thread states and queue deletion before publishing any realtime hint.
- The completion transaction resolves every active Student account linked to
  the reviewed user and every active Family account with a current,
  non-revoked `family_student_links` row.
- Blocked/disabled/archived Family accounts and revoked child links receive no
  event. Browser input never supplies either recipient list.
- Each Student and Family account receives an owner-scoped invalidation for
  every problem branch in the reviewed synonym case. Account routing metadata
  remains broker/server-side and is not serialized to the WebSocket client.
- Staff receives an audience-scoped `review-queue` invalidation after the
  completion removes the case, so other reviewers refetch instead of retaining
  a stale row.
- Realtime remains a refetch hint. SQLite is authoritative, reconnect performs
  a full active-query refetch, and broker failure cannot roll back or invite a
  retry of the committed review.
- This increment changes neither Family notification preferences nor push:
  it updates an open Family PWA session only.

Implementation:

- `db_methods/pwa/reviews.py`
- `apps/pwa_api/review_routes.py`
- `apps/pwa_app.py`
- `pwa_tests/integration/test_review_queue_repository.py`
- `pwa_tests/integration/test_content_http_api.py`
- `pwa_tests/test_pwa_app.py`
- `vmshpwa/e2e/review-workspace.spec.ts`

## Executable evidence

- Ruff, ESLint, Stylelint, workspace TypeScript and `git diff --check`:
  **PASS**.
- Python PWA suite: **1262 passed / 3 intentional skips / 1 existing SymPy
  deprecation warning**.
- Student, Family and Staff production builds: **PASS**; both PWA
  `injectManifest` service workers were generated.
- Focused production-build command `make pwa-e2e-review`: **3 passed**, one
  Staff→Student→Family case in Chromium, WebKit and Firefox.
- Repository coverage proves that one current active Family link is selected
  while a blocked account and a revoked link are excluded.
- Real-aiohttp HTTP coverage proves that one completion advances Student,
  Family and Staff cursors exactly once and that the Family projection contains
  the public review without the internal Teacher reaction.
- Exact broker-payload coverage proves separate Student owner, Family owner
  and Staff audience events for a two-branch synonym case.
- Before Staff completes the review, Playwright opens a linked Family session
  and authenticated Family WebSocket. The same session receives
  `written-review-completed` without `accountId`, then reads the committed
  verdict, comment, annotation and WebP media without reload-based login.

Known non-blocking build output remains unchanged: the Student chunk-size
warning and the Workbox/Rolldown `inlineDynamicImports` deprecation.

## Still open in Phase 6

- queue invalidations for claim, release, lease expiry and abandon, not only
  submission and completion;
- merged synonymous timelines and combined review presentation with full
  provenance;
- Student reactions and the admin complaint/appeal view;
- durable notification outbox and the agreed batched Student notification;
- correction/recheck policy, historical Telegram backfill and composite PNG;
- visual snapshot acceptance by the product owner.

This proof accepts live review-completion consistency for Student, Family and
Staff, not Phase 6 as a whole.
