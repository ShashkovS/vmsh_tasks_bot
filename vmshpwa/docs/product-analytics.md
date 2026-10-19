# Product analytics validation

The tracker in `packages/app-shell/src/product-analytics.tsx` sends ASCII route
shapes without query strings or fragments; non-literal segments become `:id`.
`apps/pwa_api/product_analytics_routes.py` also normalizes Russian group codes
н/п/э (including percent encoding) from cached clients before storing events.
It continues to reject full URLs, query strings and unknown payload fields.

Expected validation failures use keyword-only `PwaApiError` and return 422,
not an unhandled 500. Regression coverage:
`pwa_tests/integration/test_product_analytics_http.py` and
`packages/app-shell/src/product-analytics.test.ts`.

This fix does not change answer delivery or the separate Staff audit projection.

## Bounded ingestion — 18 October 2026

[Approved follow-ups](../../docs/performance/followups-20261018.md) are implemented
by `helpers/pwa/product_analytics.py`, `main.pwa_analytics_lifecycle` and
`db_methods/pwa/product_analytics.py`. The optional store uses the existing
persistent thread-owned SQLite workers. HTTP validates session/boundary/events
before accepting into a RAM queue of at most 5120 events per worker; each write
contains up to 200 events collected for at most 50 ms. A 204 response remains
best effort, and does not promise immediate report visibility or durable delivery.
Queue overflow, failure and shutdown drops are observable with fixed outcomes.
Business audit writes are independent of this queue.

The browser tracker batches short bursts for 100 ms and flushes on pagehide and
unmount using keepalive. Normal server shutdown drains before legacy background
cancellation, then closes connections under the lifecycle lock. Admission metrics
include the fixed store (`main`/`product_analytics`); paths/identities are not labels.
Tests: `pwa_tests/integration/test_product_analytics_store.py` and the tracker tests.
