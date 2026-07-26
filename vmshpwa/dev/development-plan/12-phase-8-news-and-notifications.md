# Этап 8. Telegram-news, realtime, Web Push и баннеры

## Результат

Посты Telegram-канала с 1 апреля 2026 года, включая edits/deletes, идемпотентно зеркалируются в Student/Family PWA. Admin может скрыть пост только в PWA и создать scheduled local publication/banner. Полный broadcast composer и Staff→Telegram publishing откладываются во вторую версию.

Дизайн-контракт этапа: [Telegram-rich news, connectivity/update/push states, audience news pages и Storybook stories](18-design-implementation-map.md#phase-8-design).

## Модель данных

Migration: `pwa_news_notifications_delivery`.

Таблицы: `news_posts`, `news_revisions`, `news_media`, `news_visibility`, `notification_preferences`, `push_subscriptions`, `notification_events`, `notification_deliveries`, `delivery_outbox`, `group_banners`. `broadcasts`, targets/deliveries и Markdown-editor schema добавляются во второй фазе, а не заранее пустыми таблицами.

Telegram update identity: chat/message/media-group IDs + source hash. Source chat сопоставляется с группой через verified `groups.telegram_channel_id`; `news_posts.group_id` фиксирует это сопоставление. Edit creates new revision; source delete убирает пост из обычной PWA-ленты, manual hide не меняет Telegram.

## News ingest/rendering

- Telegram adapter backfills from `2026-04-01` and consumes new/edited/deleted channel posts without becoming required app startup adapter.
- У каждой учебной группы свой DB-configured Telegram channel. Unmapped/disabled channel update не присваивается группе по title/username, а останавливается в diagnostics до явной настройки.
- Media copies to S3/file storage; local DB keeps source payload and revision.
- Telegram-rich source is sanitized into PWA representation with headings, paragraphs, emphasis/mark/sub/sup/spoiler, links, lists, quotes, code, details, tables, divider, media and math extensions; unsupported entity produces diagnostic/fallback, not raw unsafe HTML.
- Новые условия задач публикуются в Telegram полноценным текстом Rich Message. Скриншот условия не является основным представлением; отдельные SVG/рисунки остаются media. Исторические fixtures берутся из `_external_pipelines/ChatExport_2026-07-25`.
- Album order/caption and post edits preserved.
- Local post v1 остаётся в PWA. Telegram preview/publish используется во второй версии для автоматической публикации условий.
- Баннер имеет display window и исчезает после него; публикация в нормальном случае остаётся навсегда. Dismissal баннера хранится только локально на устройстве.

## Notification semantics

Categories at minimum: `lesson_published`, `hint_published`, `solution_published`, `review_completed`, `thread_updated`, `oral_window`, `classroom_assignment`, `deadline`, `news`. Категория `broadcast` появляется вместе с полной функцией во второй фазе.

- Defaults all on except `oral_window`; exact split in-app/push follows preference contract.
- 21:00–09:00 в timezone пользователя подавляет только sound. Event remains visible/delivered.
- Все review-completed events ученика агрегируются в одну пачку за 30 минут.
- Foreground can suppress duplicate native push display while still marking in-app event.
- Review event становится read после минимум трёх непрерывных секунд видимости: client запускает monotonic timer только для реально видимого события и затем отправляет идемпотентный acknowledgement, а server ставит собственный `readAt`. Read-state account-scoped, поэтому второе устройство получает invalidation/refetch и снимает badge. Telegram delivery не считается read без надёжного receipt. Badge «Задачи» считает обновлённые/проверенные задачи, которые student ещё не видел.
- Family по умолчанию получает один weekly digest после окончания всей проверки, без потока individual review pushes.
- `classroom_assignment.changed` продолжает vertical slice этапа 7: Student получает push/in-app при назначении, сбросе и новой комнате; Family только refetch-ит API/WS state и не получает delivery этой категории.
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
- Channel routing fixtures: две группы/два channel ID, unmapped/disabled/changed destination, запрет дубля channel ID и неизменность исторического `news_posts.telegram_chat_id` после перенастройки группы.
- Sanitizer/CSP/entity/math/oversize/unsupported media tests.
- Delivery outbox crash/lease/retry/dedup/batching/quiet hours tests with frozen clocks.
- Read acknowledgement: background tab/быстрый scroll не засчитываются, два устройства сходятся к одному `readAt`, duplicate ack безопасен, Telegram sent не снимает PWA badge.
- Three-audience WS plus private owner leakage tests across two workers/NATS.
- Classroom delivery routing: owner Student получает event/push, связанный Family socket обновляет state без push, посторонние principals не видят payload.
- Service-worker push/update routing tests on supported browser; contract tests elsewhere.
- Storybook news cards/albums/two previews/banner/push prompts/connection states.
- Playwright production build: backfill/edit/delete fixture → PWA; offline news; scheduled banner with local dismiss; WS/read-after-3s; family weekly digest; teacher forbidden admin routes.

## Критерии приёмки

- Duplicate Telegram update creates no duplicate post/media/delivery.
- Private review event cannot be observed by other student, family or unrelated staff socket.
- Reconnect yields correct state even when worker cursor is lower.
- Quiet hours do not hide/belay in-app information, only suppress sound behavior.
- Storybook первой фазы честно показывает deferred scope рассылок и не имитирует отправку. Markdown editor, aggregated delivery/retry и Staff→Telegram остаются phase two.
- Telegram adapter outage does not stop PWA API.

## Пруфы завершения этапа

- [ ] Revision/migration: `<sha/paths/results>`.
- [ ] Telegram fixture ingest/edit/album/idempotency report: `<path/result>`.
- [ ] Demo Telegram mirror, полное текстовое условие, PWA-local publication/hide/banner + PWA offline: `<routes/evidence>`.
- [ ] WS audience/owner/two-worker/reconnect leakage tests: `<result>`.
- [ ] Push/outbox/batching/quiet-hours failure matrix: `<path/result>`.
- [ ] Storybook stories/interactions/a11y/visual approval: `<ids/paths>`.
- [ ] Playwright production preview 3 browsers/capability skips: `<result>`.
- [ ] Telegram historical adapter tests: `<result>`.
- [ ] Docs/delivery runbook/known limitations/acceptance: `<paths/issues/name/date>`.
