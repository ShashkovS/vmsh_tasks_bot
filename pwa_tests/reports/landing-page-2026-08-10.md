# Public landing page — proof, 10 August 2026

## Scope

The public root is a separate React/Vite bundle. It has no session, API,
SQLite, Telegram, Google, PWA or audience state. It exposes only the Student
and Family entry points.

## Traceability

- Source: [`vmshpwa/apps/landing/src/landing-page.tsx`](../../vmshpwa/apps/landing/src/landing-page.tsx)
- Story: [`Product/Landing--home`](http://localhost:6006/?path=/story/product-landing--home)
- Release packager: [`vmshpwa/scripts/static_release.py`](../../vmshpwa/scripts/static_release.py)
- One-origin gateway: [`vmshpwa/scripts/e2e_gateway.py`](../../vmshpwa/scripts/e2e_gateway.py)
- Nginx template: [`vmshpwa/deploy/nginx/vmshpwa.conf.template`](../../vmshpwa/deploy/nginx/vmshpwa.conf.template)

## Automated checks

- Python release/gateway/nginx/smoke tests: **78 passed**.
- Storybook browser interaction and a11y tests: **265 passed**.
- ESLint and Stylelint: **pass**.
- Strict TypeScript and all four production bundles: **pass**.
- Static-release permission regression: **pass** (`0755` directories, `0644` files).
- Landing gateway checks: `/` is `200` with `no-cache`, Student/Family links,
  no Staff link; hashed `/landing/assets/` is immutable-cacheable; missing
  assets return `404`.
- Targeted Playwright shell coverage: **3/3 passed** in Chromium, WebKit and
  Firefox. The full multi-browser suite remains a deployment-stage command.

## Not run or intentionally deferred

- Full frontend unit suite remains red in ten pre-existing
  `packages/app-shell` auth/realtime/session-management tests; no landing test
  is involved.
- Visual snapshots were not updated. Owner review of mobile-light and
  desktop-light Storybook variants is still required.
- Production server configuration and one-time permissions repair require the
  deployment operator; backend and migrations are out of scope.
