# Phase 8 proof: classroom delivery observability

Date: 2026-08-02

Authoritative requirements:

- [`12-phase-8-news-and-notifications.md`](../../vmshpwa/dev/development-plan/12-phase-8-news-and-notifications.md);
- [`product-ux-decisions-2026-07.md`](../../vmshpwa/docs/product-ux-decisions-2026-07.md).

## Result

The existing explicit classroom announcement flow now returns and renders the
owner-approved delivery report. For each selected channel Staff sees:

- selected recipients;
- eligible destinations;
- suppressed destinations;
- queued deliveries;
- attempted deliveries;
- succeeded deliveries;
- failed deliveries.

The same response reports recipients who received at least one selected
channel, every selected channel, or only a partial delivery. Partial recipients
are available in a compact disclosure with Student name, course, group,
classroom and the PWA/Telegram result. Telegram chat IDs, tokens and other
destinations never enter the browser payload.

## Deliberately simple implementation

No migration, counter table, background projection or new delivery abstraction
was added. [`_batch_payload`](../../apps/pwa_api/classroom_delivery_routes.py)
derives the report from the existing immutable recipient rows whenever the
batch is read:

- `eligible = queued + succeeded + failed`;
- `attempted = succeeded + failed`;
- `deliveredAny` means at least one selected channel has state `sent`;
- `deliveredAll` means every selected channel has state `sent`;
- `partial = deliveredAny - deliveredAll`.

This is sufficient for the current scale and prevents a mutable aggregate from
drifting away from its recipient evidence. The existing explicit retry still
queues only failed Telegram recipient/channel pairs; an already successful PWA
delivery remains untouched.

## Code and stories

- API report: `apps/pwa_api/classroom_delivery_routes.py`;
- Zod contract and fixture: `vmshpwa/packages/contracts/src/classrooms.ts` and
  `fixtures/classrooms/delivery-batch.v1.json`;
- Staff component: `vmshpwa/packages/product/src/classroom-delivery.tsx`;
- Storybook interaction:
  `Product/Classrooms--delivery-partial-report` and
  `Product/Classrooms--delivery-retry-failed`;
- production browser flow: `vmshpwa/e2e/classroom-catalog.spec.ts`.

## Executable evidence

- focused contract unit: **18 passed**;
- focused aiohttp/SQLite delivery integration: **10 passed**;
- focused Storybook interactions: **4 passed**;
- complete lint and strict TypeScript gates: **PASS**;
- complete frontend unit: **102 files / 565 passed**;
- complete PWA Python suite: **1498 passed / 5 intentional skips**;
- complete Storybook browser suite: **47 files / 226 passed**;
- production-build classroom E2E: **9 passed** in Chromium, WebKit and Firefox;
- Student and Family `injectManifest` builds completed as part of the E2E run;
- `git diff --check`: **PASS** before commit.

No visual baselines were updated. Owner visual acceptance of the denser report
remains open, as do the independent live-device Web Push proof and Telegram UI
scheduled-queue inventory.
