# E2E and agent runtime instructions

- Playwright starts real aiohttp with the isolated `pwa-e2e` SQLite, media root and NATS prefix. MSW is forbidden here.
- Tests may not contact Telegram, Google, production services or human-runtime ports/state.
- Build all three production bundles, then exercise them on the single loopback
  origin provided by `scripts/e2e_gateway.py`. The gateway proxies exact
  audience API/WebSocket paths to the real aiohttp process; it must never be
  replaced by three unrelated Vite origins, because base paths, cookie paths,
  history fallback, service-worker scopes and browser storage are one-host
  production boundaries.
- Run E2E and visual checks through the lock-aware Make targets backed by
  `scripts/e2e_runner.py`; do not bypass its cross-process lock while shared
  dist output, ports or the seeded E2E database may be in use.
- The gateway is test-only: keep its bind and upstream on literal loopback,
  require `VMSH_RUNTIME_PROFILE=pwa-e2e`, and do not expose its local
  service-worker-generation/runtime-mode control routes outside this harness.
- Every `*.spec.ts` imports `test`, `expect` and Playwright types from
  `./fixtures`, never directly from `@playwright/test`. The auto-fixture blocks
  browser HTTP/WebSocket access outside the literal one-origin gateway and
  turns an attempted escape into a test failure.
- A request-context assertion proves only server routing. For navigation
  fallback exclusions, activate the audience Service Worker and repeat exact
  API, malformed WebSocket and missing-asset cases as real page navigations so
  `NavigationRoute` cannot hide a gateway error behind the app shell.
- Keep the PWA update controller independent from runtime and IndexedDB startup
  gates. Update tests must prove that a waiting worker can recover an
  incompatible startup instead of assuming the protected shell mounted.
- This Phase-0 gateway does not model a trusted production reverse proxy:
  upstream `Host` is the API listener while browser `Origin` is the gateway.
  Phase-1 auth/CSRF tests must add an explicit public-origin/proxy contract and
  cover spoofed `Forwarded` and `X-Forwarded-*` headers.
- Keep Chromium, WebKit and Firefox coverage. Make browser-specific baselines explicit rather than loosening a global pixel threshold.
- Seed deterministic data and isolate browser contexts. Never depend on test order or a developer's existing local storage.
- Visual baseline updates require inspection of diffs. A failed screenshot is evidence to review, not permission to overwrite.
- Prefer stable roles/names/test IDs over CSS selectors; assert the user-visible result and backend receipt, not implementation timing.

## Traceability And Progress

- E2E and visual specs cite the acceptance requirement, route, and contract they prove; keep comments concise and actionable.
- Testing documentation links to exact spec files and named scenarios.
- Add executed commands, browser coverage, artifacts, exceptions, and remaining gaps to the affected phase proof and status files.
