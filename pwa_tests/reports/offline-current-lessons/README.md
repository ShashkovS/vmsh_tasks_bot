# Student offline current lessons — 27 September 2026

Implementation: [decision and file references](../../../vmshpwa/docs/offline-current-lessons.md).

## Verification

- Full frontend `pnpm test`: **183 files / 938 tests passed**.
- Final targeted preparation/contracts/auth-store regression after adding resume
  and duplicate-scope coverage: **27 tests passed**.
- Backend content HTTP and E2E runner regression: **64 tests passed**;
  the final combined runner command was rechecked independently: **9 passed**.
- `make pwa-typecheck`, `make pwa-lint`, `make pwa-i18n-check`: passed.
- Production builds for all audiences through the lock-aware E2E runner: passed.
- `make pwa-e2e-offline-current`: **10 passed, 2 explicitly skipped**.
  This target runs both offline-current and publication scenarios. Current levels
  download on Now, then work through Tasks navigation, level switching, reload,
  new tabs and direct links. Image bytes are checked, not just image elements.
  A mounted Student document also receives a newly published condition and its
  rollback without manual reload, in all three engines.

## Browser boundary

Chromium passes real `context.setOffline(true)` cold-start/navigation checks.
All three engines pass the API-disconnected version with real account-scoped
IndexedDB and the production service worker. Firefox/WebKit network-mode cases
are explicitly skipped after reproducing the pre-existing harness limitation:
Firefox rejects cached navigation with `NS_ERROR_OFFLINE`; WebKit rejects cached
module loading with an internal error and its native offline reload stalls.
These skips are not a claim of a real network-offline Safari/Firefox cold-start
proof. The existing content-publication test documents the same limitation.

## Screenshots

Inspected Chromium offline captures from the real production build:

- [Current level, conditions, figures and mathematics](chromium-offline-g-1.png)
- [Another level opened without any prior visit](chromium-offline-g-2.png)

The browser's deletion of site storage still removes downloaded content. No
production deployment, real-account access or database migration was performed.
