# Student: current lessons available offline

Owner decision, 2026-09-27: after an online login, automatically prepare the
current lesson in every allowed group of every enrolled course. Opening Tasks
first is not required. Saved Student reading survives session expiry; server
writes still require valid authentication. Explicit logout/account switch and
an authoritative server rejection clear local account data. Family/Staff expiry
rules are unchanged. Browser/site-storage deletion still requires downloading again.

## Implementation

- [`course_routes.py`](../../apps/pwa_api/course_routes.py),
  `GET /student/api/v1/offline-lessons`, reuses the home snapshot repository for
  all authorized course/group scopes. It never switches enrollment or accepts
  caller-selected identities. Its strict Zod contract and query key live in
  [`courses.ts`](../packages/contracts/src/courses.ts).
- [`StudentOfflinePreparation`](../apps/student/src/student-offline-preparation.tsx)
  stays mounted in the protected shell. Its active query runs on login, reconnect,
  window focus and existing publication realtime invalidations. Online reads
  remain server-first: an open condition updates without reloading the page.
- [`prepareOfflineLessons`](../apps/student/src/prepare-offline-lessons.ts) stages
  access/home/navigation, first archive pages, current lessons, problem lists,
  conditions, published lesson blocks and their figures. It validates publication
  consistency, checks the current lesson selection again before committing, and
  atomically replaces the complete copy. It does not reveal hints/solutions.
- [`lesson-bundle.ts`](../packages/offline/src/lesson-bundle.ts) stores an
  owner-scoped manifest/document snapshot in the existing Dexie documents table;
  no schema migration is required. Interrupted figure downloads are reused on retry, with one staging cache beside
  the previous complete copy. The current copy is pinned against archive
  eviction. Document budget remains 10 MiB; pinned figures have a 15 MiB cap.
  A failed replacement keeps the previous complete copy. Web Locks serialize
  preparation across tabs; abort and transactional owner checks reject late writes.
- [`sw.ts`](../apps/student/src/sw.ts) serves immutable images from the prepared
  asset cache, then the existing recent-media strategy. App shell, lazy modules,
  language catalogs, CSS and math fonts remain in the production precache.
- [`offline-student-data.ts`](../apps/student/src/offline-student-data.ts) reads
  the complete snapshot immediately when disconnected, with independently cached
  same-version updates retained (including audited reveal status). Read hooks and
  durable auth use `networkMode: always`; global queries/mutations are unchanged.
- [`authentication-store.ts`](../packages/offline/src/authentication-store.ts) and
  [`AuthenticationProvider`](../packages/app-shell/src/auth-context.tsx) separate
  Student local reading from expired server authority. Snapshots contain no tokens.

## UI and acceptance

The shell reports saving, complete, incomplete/retry or no local copy. A complete
status is conditional on all referenced figures being present. Offline pages show
saved-at information; missing material has a finite explanatory state. Archive
conditions are not bulk-downloaded. Published blocks already present in the first
archive page may have figures included in the snapshot.

Tests:

- [`prepare-offline-lessons.test.ts`](../apps/student/src/prepare-offline-lessons.test.ts):
  multiple levels without visits, offline reads, interrupted replacement/retry,
  logout/cancellation and missing images.
- [`auth-context.test.tsx`](../packages/app-shell/src/auth-context.test.tsx) and
  [`authentication-store.test.ts`](../packages/offline/src/authentication-store.test.ts):
  actual Query offline state, expired Student reading, explicit cleanup.
- [`test_content_http_api.py`](../../pwa_tests/integration/test_content_http_api.py):
  allowed/non-granted groups, unchanged enrollment, authentication/query boundaries.
- [`offline-current-lessons.spec.ts`](../e2e/offline-current-lessons.spec.ts): real offline
  transition from Now without visiting Tasks, reload/new tab/direct link, API-disconnected cold reading in Chromium, Firefox and WebKit. Publication/reveal/rollback
  remains covered separately by `content-publication.spec.ts`.

The first real `context.setOffline(true)` runs passed all-level reading/reload/new
pages in Chromium. Firefox returned `NS_ERROR_OFFLINE` on reload; WebKit rejected
cached module loads with an internal error and its native reload never completed.
This reproduces the harness limitation already documented in
`content-publication.spec.ts`. The network-mode test explicitly skips those two
engines; their API-disconnected variant still runs with real saved data and a real
service worker. These variants do not claim a full network-offline Safari/Firefox
cold-start proof.

Implementation and automated gates completed locally.
[Verification results and inspected screenshots](../../pwa_tests/reports/offline-current-lessons/README.md):
938 full-suite frontend tests, 27 final focused tests, 64 backend tests; lint,
typecheck, i18n and production build passed; browser acceptance 10 passed with
2 explicit network-mode skips as described above.
