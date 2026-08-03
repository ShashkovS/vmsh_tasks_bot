# Этап 8. Telegram-news, realtime, Web Push и баннеры

## Результат

Посты Telegram-канала с 1 апреля 2026 года, включая edits/deletes, идемпотентно зеркалируются в Student/Family PWA. Admin может скрыть пост только в PWA и создать scheduled local publication/banner. Полный broadcast composer и Staff→Telegram channel publishing откладываются во вторую версию; узкая персональная рассылка подтверждённых аудиторий реализует transport этапа 7.

Дизайн-контракт этапа: [Telegram-rich news, connectivity/update/push states, audience news pages и Storybook stories](18-design-implementation-map.md#phase-8-design).

## Модель данных

Migration: `pwa_news_notifications_delivery`.

Таблицы: `news_posts`, `news_revisions`, `news_media`, `news_visibility`, `notification_preferences`, `push_subscriptions`, `notification_events`, `notification_deliveries`, `delivery_outbox`, `group_banners`. `broadcasts`, targets/deliveries и Markdown-editor schema добавляются во второй фазе, а не заранее пустыми таблицами.

Telegram update identity: chat/message/media-group IDs + source hash. Source chat сопоставляется с course/group только через verified `telegram_bindings` purpose `news_source`; `news_posts` snapshot-ит source binding, concrete owner и фактические IDs. Edit creates new revision; source delete убирает пост из обычной PWA-ленты, manual hide не меняет Telegram.

## News ingest/rendering

- Telegram adapter backfills from `2026-04-01` and consumes new/edited/deleted channel posts without becoming required app startup adapter.
- Course/group Telegram channels задаются verified `telegram_bindings`. Course и group news sources складываются; unmapped/disabled channel update не угадывает owner по title/username, а останавливается в diagnostics до явной настройки.
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
- `classroom.assignment.changed` продолжает vertical slice этапа 7 как тихая Student/Family invalidation после confirm/change. Только явный admin delivery batch создаёт `classroom.assignment.announced`: выбранный PWA channel даёт Student in-app/push, выбранный Telegram channel — личное bot message. Family не получает delivery этой категории.
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
- Binding routing fixtures: course+две группы/несколько channel IDs, additive news sources, inherited/replaced materials target, unmapped/disabled/changed destination и неизменность historical binding/chat/message snapshot после перенастройки.
- Sanitizer/CSP/entity/math/oversize/unsupported media tests.
- Delivery outbox crash/lease/retry/dedup/batching/quiet hours tests with frozen clocks.
- Read acknowledgement: background tab/быстрый scroll не засчитываются, два устройства сходятся к одному `readAt`, duplicate ack безопасен, Telegram sent не снимает PWA badge.
- Three-audience WS plus private owner leakage tests across two workers/NATS.
- Classroom delivery routing: confirm обновляет Student/Family sockets без push; explicit batch доставляет только Student через выбранные PWA/Telegram каналы. Проверяются immutable recipient snapshot, preview/version conflict, no-auto-resend, idempotency, retry/partial failure и отсутствие token/chat ID в browser/logs.
- Service-worker push/update routing tests on supported browser; contract tests elsewhere.
- Storybook news cards/albums/two previews/banner/push prompts/connection states.
- Playwright production build: backfill/edit/delete fixture → PWA; offline news; scheduled banner with local dismiss; WS/read-after-3s; family weekly digest; teacher forbidden admin routes.

## Критерии приёмки

- Duplicate Telegram update creates no duplicate post/media/delivery.
- Private review event cannot be observed by other student, family or unrelated staff socket.
- Reconnect yields correct state even when worker cursor is lower.
- Quiet hours do not hide/belay in-app information, only suppress sound behavior.
- Storybook различает узкий classroom delivery preview/send и отложенный общий broadcast composer. Markdown editor, произвольные audiences/content и Staff→Telegram channel publication остаются phase two.
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

## Многокурсовый инкремент Phase 8

`telegram_bindings` поддерживает course/group owners: news sources складываются, group materials targets заменяют course defaults либо наследуют их. Notification categories получают optional course override. WS/NATS invalidations сужаются audience/course/group/student полями; reconnect всегда делает authoritative refetch.

Дополнительный proof: inheritance matrix, private-event leakage tests, course preference isolation и `Product/Staff-admin--telegram-bindings`.

Audit follow-up 2 августа 2026 года: все admin mutations course/group Telegram
bindings пишут безопасный before/after в общей транзакции с изменением; фиксируются
destination, purpose и status, но не bot token. Duplicate/stale запросы не создают
событий, а сбой audit insert откатывает binding. Proof:
[`phase8-telegram-bindings.md`](../../../pwa_tests/reports/phase8-telegram-bindings.md)
и [`phase10-staff-audit.md`](../../../pwa_tests/reports/phase10-staff-audit.md).

## Инкремент сверки Telegram scheduled queue — 3 августа 2026

Offline-команда проверяет owner-reviewed hash inventory без Telegram/Google/
SQLite network dependencies. Поддержаны решения retain, cancel+recreate и
obsolete; changed-after-review и дубли блокируют cutover, а aggregate report не
содержит payload, Telegram IDs, destination keys или content hashes. Реальная
ручная очередь проверяется владельцем непосредственно перед будущей передачей
destination Staff scheduler. Удаление уже опубликованных posts остаётся
отдельным explicit reconciliation gate. Proof:
[`phase8-telegram-scheduled-queue-reconciliation.md`](../../../pwa_tests/reports/phase8-telegram-scheduled-queue-reconciliation.md),
runbook:
[`telegram-scheduled-queue-cutover.md`](../../docs/telegram-scheduled-queue-cutover.md).
