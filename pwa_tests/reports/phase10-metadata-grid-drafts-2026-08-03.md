# Phase 10: reload-safe Staff metadata drafts

Date: 2026-08-03

## Result

The real Staff content workflow now keeps an unfinished problem-metadata grid
under a runtime-, account-, entity- and revision-scoped `localStorage` key. A
reload restores the exact draft for the same Staff account, while another
account in the same browser profile starts from server data and cannot see it.

This increment deliberately adds no storage service or generic draft framework.
The key builder is one pure function in
[`problem-review-draft.ts`](../../vmshpwa/apps/staff/src/problem-review-draft.ts),
and the existing
[`ProblemReviewWorkflow`](../../vmshpwa/apps/staff/src/problem-review-workflow.tsx)
continues to own the small JSON draft beside its form behavior. The production
namespace is `${runtime.instance}:${principal.accountId}` in
[`content-page.tsx`](../../vmshpwa/apps/staff/src/content-page.tsx); session
cookies and credentials are never copied into browser storage.

## Proven behavior

- matching and metadata drafts have different keys;
- group-lesson and content revision remain part of the key, so an old revision
  cannot overwrite a newer grid;
- a successful matching or metadata receipt clears its corresponding draft;
- «Отменить правки» returns to the last server baseline and clears the draft;
- HTTP `409` keeps the local rows, shows the version-conflict state and restores
  the same rows after remount;
- publication confirmation is not silently discarded when a concurrent Staff
  invalidation briefly recomputes the child readiness projection. The server's
  existing publication endpoint remains the authoritative matching/metadata
  gate.

The browser may still evict or disable Web Storage; the product contract does
not promise recovery after browser/device storage deletion. It does prove the
accepted reload, tab close and ordinary PWA-update boundary when storage is
available.

## Storybook evidence

Source:
[`content-page.stories.tsx`](../../vmshpwa/apps/staff/src/content-page.stories.tsx).

- `pages-staff-content-publication--metadata-draft-survives-reload`;
- `pages-staff-content-publication--metadata-draft-is-account-scoped`;
- `pages-staff-content-publication--metadata-conflict-keeps-draft`;
- `pages-staff-content-publication--match-then-review-metadata`.

The stories assert restoration, account separation, conflict preservation,
explicit discard, and cleanup after the server receipt. Focused browser-mode
run: **1 file / 14 tests passed**, with `addon-a11y` still configured as an
error gate. The complete Storybook gate before the final focused assertion was
**50 files / 241 tests passed**.

## Production E2E evidence

[`content-publication.spec.ts`](../../vmshpwa/e2e/content-publication.spec.ts)
uses the production Staff bundle, real aiohttp, seeded isolated SQLite and the
one-origin gateway. It enters a metadata title, reloads before any metadata
mutation, verifies restoration, saves it, and proves the account/revision key
was removed. The surrounding flow then publishes two revisions and performs an
exact rollback.

`make pwa-e2e-content`: **3 passed**, one in Chromium, WebKit and Firefox,
without retry. MSW, Google and Telegram are not used.

The run also exposed a real confirmation race: an unrelated Staff invalidation
could transiently reset local readiness after the confirmation had opened, so
the click returned without an HTTP request. The UI now submits the selected
revision and lets `publish_content_revision` repeat the authoritative server
checks. A brittle retry assertion for literal «Revision 1» was replaced by the
already stronger exact returned `revisionId` assertion.

## Consolidated gates

- scoped Prettier and ESLint: pass;
- `make pwa-lint pwa-typecheck`: pass;
- `make pwa-test`: frontend **111 files / 588 passed**; Python PWA **1560
  passed / 6 intentional skips** in eight isolated xdist workers;
- `make pwa-storybook-test`: **50 files / 241 passed**;
- `make pwa-build`: pass; Student and Family `injectManifest` workers generated;
- `make pwa-e2e-content`: **3 passed** across all required engines;
- visual snapshots were not changed.

## Remaining gate

This closes the Phase-10 metadata-grid draft item, not Phase 10 as a whole.
Owner visual review of the new functional states remains open. Browser-storage
failure messaging may be considered together with the wider cross-product
DraftPersistence status surface; it is not implemented speculatively here.
