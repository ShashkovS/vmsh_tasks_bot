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
