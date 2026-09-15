# Phase 6B proof: scoped review queue HTTP and frontend client

Date: 2026-07-28

Revisions:

- `8742244` — Staff aiohttp routes, public-ID scope, synonym-aware queue list,
  renewable claim/heartbeat/release and real auth/SQLite tests;
- `b2c539c` — strict TypeScript contracts, account-scoped query keys and Staff
  browser client.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Implemented boundary

- `GET /staff/api/v1/review/items` lists complete logical cases in oldest or
  newest order and supports opaque cursor plus `problemGroup` filtering.
- `POST /staff/api/v1/review/items/{queuePublicId}/claim` atomically claims all
  current branches of one Student/synonym case.
- `POST .../heartbeat` renews the 30-minute lease only for its authenticated
  owner, exact queue anchor and current Staff scope.
- `POST .../release` releases every branch owned by that lease.
- The browser never supplies a teacher/user identity. Request bodies are exact
  versioned JSON objects; unknown fields fail with `422`.
- Admin has global scope. A teacher is authorized by public course/group IDs
  loaded from the current session. If any synonym branch is outside that
  scope, the collection omits the whole case and direct claim returns `403`.
- Active PWA and legacy Telegram locks are visible as safe lock metadata but
  never expose integer IDs or claim tokens in the queue list.
- Second-actor claim returns `409 review_already_claimed`; expired/released or
  foreign lease mutations return `409 review_lease_lost`.

Implementation:

- `db_methods/pwa/reviews.py`
- `apps/pwa_api/review_routes.py`
- `apps/pwa_app.py`
- `vmshpwa/packages/contracts/src/review-queue.ts`
- `vmshpwa/packages/app-shell/src/review-queue-client.ts`

## Executable evidence

Focused Python:

- `pwa_tests/integration/test_review_queue_repository.py`
- `pwa_tests/integration/test_review_queue_http_api.py`
- result: **8 passed**.

Focused TypeScript:

- `packages/contracts/src/review-queue.test.ts`
- `packages/app-shell/src/review-queue-client.test.ts`
- result: **2 files / 9 passed**.

Full checkpoint:

- ESLint + Stylelint: **PASS**;
- workspace TypeScript and generated TanStack route trees: **PASS**;
- frontend unit suite: **50 files / 376 passed**;
- Python PWA suite: **1237 passed / 3 intentional skips / 1 existing SymPy
  deprecation warning**;
- Student, Family and Staff production builds: **PASS**;
- Student and Family `injectManifest` service workers: **PASS**.

The real HTTP suite uses migrated SQLite plus real Staff login cookies. It
contains separate full-course teacher, one-group teacher and admin identities,
and covers anonymous access, fail-closed partial scope, claim conflict, foreign
token, heartbeat, release, reclaim and strict-body rejection.

The client suite proves runtime audience validation, URL/query serialization,
server-owned actor identity, exact mutation retries after a single session
refresh, API error parsing, malformed-response rejection, network error
separation and Staff-account cache isolation.

## Intentionally still open

- problem-group aggregate chooser/dashboard endpoints;
- review evidence snapshot, verdict transaction, annotation and reaction
  persistence;
- NATS queue invalidation after claim/release/complete;
- Staff route/page wiring and multi-browser Playwright race;
- legacy review/result/reaction backfill and Telegram historical completion
  tests.

Those remain later Phase 6 gates; this proof accepts only the queue HTTP and
typed-client increment.
