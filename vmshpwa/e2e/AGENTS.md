# E2E and agent runtime instructions

- Playwright starts real aiohttp with the isolated `pwa-e2e` SQLite, media root and NATS prefix. MSW is forbidden here.
- Tests may not contact Telegram, Google, production services or human-runtime ports/state.
- Exercise audience URLs through their Vite proxies so base paths, cookies, history fallback and WebSocket upgrade are real.
- Keep Chromium, WebKit and Firefox coverage. Make browser-specific baselines explicit rather than loosening a global pixel threshold.
- Seed deterministic data and isolate browser contexts. Never depend on test order or a developer's existing local storage.
- Visual baseline updates require inspection of diffs. A failed screenshot is evidence to review, not permission to overwrite.
- Prefer stable roles/names/test IDs over CSS selectors; assert the user-visible result and backend receipt, not implementation timing.
