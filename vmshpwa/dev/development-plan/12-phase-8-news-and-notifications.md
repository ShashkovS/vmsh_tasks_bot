# Этап 8. Telegram-news, realtime, Web Push, баннеры и рассылки

## Результат

Посты Telegram-канала с 1 апреля 2026 года, включая edits/deletes, идемпотентно зеркалируются в Student/Family PWA. Admin может скрыть пост только в PWA и создать scheduled local publication/banner. Staff→Telegram publishing откладывается во вторую версию.

## Модель данных

Migration: `pwa_news_notifications_delivery`.

Таблицы: `news_posts`, `news_revisions`, `news_media`, `news_visibility`, `notification_preferences`, `push_subscriptions`, `notification_events`, `notification_deliveries`, `delivery_outbox`, `broadcasts`, `broadcast_targets`, `broadcast_deliveries`, `group_banners`.

Telegram update identity: chat/message/media-group IDs + source hash. Edit creates new revision; source delete убирает пост из обычной PWA-ленты, manual hide не меняет Telegram.

## News ingest/rendering

- Telegram adapter backfills from `2026-04-01` and consumes new/edited/deleted channel posts without becoming required app startup adapter.
- Media copies to S3/file storage; local DB keeps source payload and revision.
- Telegram-rich source is sanitized into PWA representation with math extensions; unsupported entity produces diagnostic/fallback, not raw unsafe HTML.
- Album order/caption and post edits preserved.
- Local post v1 остаётся в PWA. Telegram preview/publish используется во второй версии для автоматической публикации условий.
- Баннер имеет display window и исчезает после него; публикация в нормальном случае остаётся навсегда. Dismissal баннера хранится только локально на устройстве.

## Notification semantics

Categories at minimum: `lesson_published`, `hint_published`, `solution_published`, `review_completed`, `thread_updated`, `oral_window`, `deadline`, `news`, `broadcast`.

- Defaults all on except `oral_window`; exact split in-app/push follows preference contract.
- 21:00–09:00 в timezone пользователя подавляет только sound. Event remains visible/delivered.
- Все review-completed events ученика агрегируются в одну пачку за 30 минут.
- Foreground can suppress duplicate native push display while still marking in-app event.
- Review event становится read после минимум трёх секунд видимости. Badge «Задачи» считает обновлённые/проверенные задачи, которые student ещё не видел.
- Family по умолчанию получает один weekly digest после окончания всей проверки, без потока individual review pushes.
- Delivery is DB-durable with retry/backoff/dead-letter/admin diagnostics. NATS only invalidates read models.

## WebSocket scoping

- Every event has audience; private event additionally owner account/user.
- Server filters before socket send. Staff-only queue changes never reach Student/Family.
- Reconnect always refetches bootstrap/query state. No «connected means no gap» assumption across two workers.
- `_broadcast` concurrency remains bounded; slow/broken sockets are removed without blocking all clients.

## Push/service worker

- Student/Family separate subscription and SW scope.
- Product допускает полные сведения о проверке на lock screen; payload всё равно owner-scoped и не содержит credentials.
- Click validates route after login; revoked session goes login then intended route.
- Subscription rotation/failure cleanup; VAPID secrets only server-side.
- PWA update flow and push-permission UX are separate; permission is requested contextually, not on first paint.

## Tests

- Telegram new/edit/album/duplicate/reordered/retry fixtures, no live Bot API in unit/E2E.
- Sanitizer/CSP/entity/math/oversize/unsupported media tests.
- Delivery outbox crash/lease/retry/dedup/batching/quiet hours tests with frozen clocks.
- Three-audience WS plus private owner leakage tests across two workers/NATS.
- Service-worker push/update routing tests on supported browser; contract tests elsewhere.
- Storybook news cards/albums/two previews/banner/push prompts/connection states.
- Playwright production build: backfill/edit/delete fixture → PWA; offline news; scheduled banner with local dismiss; WS/read-after-3s; family weekly digest; teacher forbidden broadcasts.

## Критерии приёмки

- Duplicate Telegram update creates no duplicate post/media/delivery.
- Private review event cannot be observed by other student, family or unrelated staff socket.
- Reconnect yields correct state even when worker cursor is lower.
- Quiet hours do not hide/belay in-app information, only suppress sound behavior.
- PWA broadcast shows aggregate delivery state and can be retried without duplicate sends. Sending Staff-created publications to Telegram remains phase two.
- Telegram adapter outage does not stop PWA API.

## Пруфы завершения этапа

- [ ] Revision/migration: `<sha/paths/results>`.
- [ ] Telegram fixture ingest/edit/album/idempotency report: `<path/result>`.
- [ ] Demo Telegram mirror, PWA-local publication/hide/banner/broadcast + PWA offline: `<routes/evidence>`.
- [ ] WS audience/owner/two-worker/reconnect leakage tests: `<result>`.
- [ ] Push/outbox/batching/quiet-hours failure matrix: `<path/result>`.
- [ ] Storybook stories/interactions/a11y/visual approval: `<ids/paths>`.
- [ ] Playwright production preview 3 browsers/capability skips: `<result>`.
- [ ] Telegram historical adapter tests: `<result>`.
- [ ] Docs/delivery runbook/known limitations/acceptance: `<paths/issues/name/date>`.
