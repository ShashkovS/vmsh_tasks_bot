# Phase 8: realtime invalidation for news

## Result

- Successful admin hide/restore actions publish the `news` resource to the
  authenticated Student, Family and Staff audiences.
- Version conflicts and forbidden source-deleted transitions do not publish an
  invalidation.
- The existing transport remains authoritative for routing: audience and
  optional account scope are validated before fan-out.
- Every reconnect receives `resync-required`; the browser refetches active HTTP
  queries from SQLite before returning to `ready`. The cursor is not treated as
  a durable event log.
- A transient broker failure after the SQLite commit is logged and does not
  turn a successful moderation action into a retryable HTTP error.

## Implementation

- `apps/pwa_api/news_moderation_routes.py`
- `apps/pwa_app.py`
- `vmshpwa/packages/app-shell/src/realtime.tsx`
- `vmshpwa/packages/app-shell/src/news-client.ts`
- `vmshpwa/packages/app-shell/src/news-moderation-client.ts`

## Proof

- `uv run pytest -q pwa_tests/integration/test_phase8_news_moderation.py pwa_tests/test_pwa_app.py`
  — 37 passed.
- `./node_modules/.bin/vitest run --project unit packages/app-shell/src/realtime-client.test.ts packages/app-shell/src/realtime-provider.test.tsx packages/app-shell/src/news-client.test.ts packages/app-shell/src/news-moderation-client.test.ts`
  — 22 passed.
- `uv run ruff check apps/pwa_app.py apps/pwa_api/news_moderation_routes.py pwa_tests/integration/test_phase8_news_moderation.py`
  — passed.
- `git diff --check` — passed before commit.

No visual snapshot changed in this increment.
