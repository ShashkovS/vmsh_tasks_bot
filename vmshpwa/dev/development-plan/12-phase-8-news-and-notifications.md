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

## Cutover запланированных публикаций Telegram UI

Очередь сообщений, вручную запланированных редакторами в Telegram UI, является внешним mutable state: до фактической публикации она не представлена в `news_posts` и не должна неявно импортироваться либо дедуплицироваться по тексту. До включения Staff scheduler для destination/time window администратор составляет privacy-safe inventory pending-записей и принимает по каждой решение `retain_in_telegram | cancel_and_recreate_in_staff | cancel_as_obsolete`. Reconciliation сопоставляет destination, intended time, принятую content revision и media manifest. Staff publishing включается только после отчёта, в котором у каждого ожидаемого сообщения ровно один владелец доставки и нет ни пропуска, ни двойной публикации.

## Notification semantics

Categories at minimum: `lesson_published`, `hint_published`, `solution_published`, `review_completed`, `thread_updated`, `oral_window`, `classroom_assignment`, `deadline`, `news`. Категория `broadcast` появляется вместе с полной функцией во второй фазе.

- Defaults all on except `oral_window`; exact split in-app/push follows preference contract.
- 21:00–09:00 в timezone пользователя подавляет только sound. Event remains visible/delivered.
- Все review-completed events ученика агрегируются в одну пачку за 30 минут.
- Foreground can suppress duplicate native push display while still marking in-app event.
- Review event становится read после минимум трёх непрерывных секунд видимости: client запускает monotonic timer только для реально видимого события и затем отправляет идемпотентный acknowledgement, а server ставит собственный `readAt`. Read-state account-scoped, поэтому второе устройство получает invalidation/refetch и снимает badge. Telegram delivery не считается read без надёжного receipt. Badge «Задачи» считает обновлённые/проверенные задачи, которые student ещё не видел.
- Family не получает поток individual review pushes. Admin явно отправляет один
  digest отдельно для выбранной группы и занятия; последующие исправления
  обновляют данные без автоматического повторного уведомления.
- `classroom.assignment.changed` продолжает vertical slice этапа 7 как тихая Student/Family invalidation после confirm/change. Только явный admin delivery batch создаёт `classroom.assignment.announced`: выбранный PWA channel даёт Student in-app/push, выбранный Telegram channel — личное bot message. Family не получает delivery этой категории.
- Delivery is DB-durable with retry/backoff/dead-letter/admin diagnostics. NATS only invalidates read models.
- Owner-confirmed delivery report допускает partial success и раскрываемые
  списки. Staff агрегирует по каждому каналу `selected`, `eligible`,
  `suppressed`, `queued`, `attempted`, `succeeded`, `failed` и общие
  `delivered_any`, `delivered_all`, `partial`. Получателя с успехом хотя бы в
  одном выбранном канале считаем охваченным, но partial cases остаются в
  раскрываемом privacy-safe списке. Implementation-default `retry failed`
  означает явную новую попытку только неуспешной пары recipient/channel и не
  дублирует успешную доставку.

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
- Cutover fixture для Telegram UI scheduled queue: retain/cancel/recreate decisions, изменение pending-записи до cutover, одинаковый текст в разных destination и доказательство no-gap/no-duplicate. Fixture синтетический и не содержит реальные сообщения или Telegram IDs.
- Binding routing fixtures: course+две группы/несколько channel IDs, additive news sources, inherited/replaced materials target, unmapped/disabled/changed destination и неизменность historical binding/chat/message snapshot после перенастройки.
- Sanitizer/CSP/entity/math/oversize/unsupported media tests.
- Delivery outbox crash/lease/retry/dedup/batching/quiet hours tests with frozen clocks.
- Delivery observability: owner-confirmed channel counters/partial list сходятся
  с immutable recipient rows; implementation-default retry создаёт attempts
  только для failed pairs и не меняет уже успешные rows.
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
- Частичная доставка видна Staff и может быть адресно повторена без повторной
  отправки успешным получателям/каналам.
- Staff scheduler нельзя сделать владельцем Telegram destination, пока pending-очередь этого destination/window не прошла явный reconciliation.

## Пруфы завершения этапа

- [ ] Revision/migration: `<sha/paths/results>`.
- [ ] Telegram fixture ingest/edit/album/idempotency report: `<path/result>`.
- [ ] Demo Telegram mirror, полное текстовое условие, PWA-local publication/hide/banner + PWA offline: `<routes/evidence>`.
- [ ] WS audience/owner/two-worker/reconnect leakage tests: `<result>`.
- [ ] Push/outbox/batching/quiet-hours failure matrix: `<path/result>`.
- [ ] Delivery counters/partial recipient list/failed-only retry: `<path/result>`.
- [ ] Storybook stories/interactions/a11y/visual approval: `<ids/paths>`.
- [ ] Playwright production preview 3 browsers/capability skips: `<result>`.
- [ ] Telegram historical adapter tests: `<result>`.
- [x] Offline Telegram UI scheduled-queue validator, synthetic
      retain/cancel+recreate/obsolete fixture и privacy-safe aggregate report без
      payload/Telegram IDs/destination keys/hashes:
      [`phase8-telegram-scheduled-queue-reconciliation.md`](../../../pwa_tests/reports/phase8-telegram-scheduled-queue-reconciliation.md).
      Owner-run inventory настоящей Telegram UI queue остаётся deployment gate
      непосредственно перед передачей destination Staff scheduler.
- [ ] Docs/delivery runbook/known limitations/acceptance: `<paths/issues/name/date>`.
- [x] Явная per-group Family lesson digest: admin preview/confirm, дедупликация
      по Family account + group lesson, late-link delivery, Family event/read,
      Student isolation, owner invalidation, API/integration/contracts/UI и
      production-build Playwright scenario. Browser execution и visual gate
      остаются открыты из-за launcher failure:
      [`phase8-family-digest-2026-08-03.md`](../../../pwa_tests/reports/phase8-family-digest-2026-08-03.md).

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

## Инкремент явной сверки удалённых Telegram-постов — 3 августа 2026

Bot API не обещает update об удалении опубликованного `channel_post`, поэтому
v1 не угадывает deletion и не добавляет MTProto user session. Global admin
явно отмечает зеркальный пост `deleted` либо исправляет отметку через `present`
с обязательной причиной и текущим `If-Match`. Изменение source/visibility и
privacy-safe append-only audit атомарны; teacher получает `403`, а Student и
Family перестают видеть `source_deleted`. Proof:
[`phase8-news-source-deletion-reconciliation.md`](../../../pwa_tests/reports/phase8-news-source-deletion-reconciliation.md),
runbook:
[`telegram-news-deletion-reconciliation.md`](../../docs/telegram-news-deletion-reconciliation.md).

## Инкремент локальной публикации PWA по расписанию — 3 августа 2026

Global admin создаёт course- или group-scoped plain-text публикацию без участия
Telegram. Staff вводит московское wall time, API хранит UTC; существующие feed,
detail и notification-event reads не раскрывают публикацию до `published_at`.
Post, revision, initial visibility, scheduled Student/Family events и
privacy-safe audit создаются атомарно. Account/runtime-scoped `localStorage`
сохраняет Staff-черновик до server receipt.

Story IDs: `pages-staff-local-news-composer--scheduled` и
`product-news-moderation--scheduled-local`. Markdown, edit/reschedule и
Staff→Telegram publication остаются следующими инкрементами. Точная due-time
WebSocket invalidation для уже открытой вкладки также не закрыта этим срезом.
Proof:
[`phase8-local-scheduled-news.md`](../../../pwa_tests/reports/phase8-local-scheduled-news.md),
runbook: [`local-scheduled-news.md`](../../docs/local-scheduled-news.md).

## Инкремент due-time foreground invalidation — 3 августа 2026

Существующий пятисекундный content scheduler сканирует successful time windows
для visible local news и при наступлении срока публикует
`local-news-published` для Student, Family и Staff. Новая таблица/lease не
добавлены: NATS-сообщение является безопасным idempotent refetch hint, поэтому
два worker могут отправить дубль. Broker failure не двигает in-memory watermark
и повторяет окно; restart полагается на обязательный WebSocket resync.

Focused Python regression: **52 PASS**; полный PWA Python gate после
объединения с соседним news-edit срезом: **1578 PASS / 6 intentional skips**.
Proof:
[`phase8-local-news-due-invalidation.md`](../../../pwa_tests/reports/phase8-local-news-due-invalidation.md),
runbook: [`local-scheduled-news.md`](../../docs/local-scheduled-news.md).

## Инкремент редактирования будущей локальной публикации — 3 августа 2026

Global admin может до исходного срока изменить plain text и московское время
локальной PWA-публикации. Получатель остаётся прежним, каждое изменение создаёт
immutable revision, а `If-Match` защищает от параллельной перезаписи. Будущие
notification events переносятся в той же SQLite-транзакции; скрытие удаляет их,
восстановление создаёт снова. Runtime/account/post/version-scoped Staff draft
сохраняется в `localStorage` до server receipt.

Story IDs: `pages-staff-local-news-composer--editing-scheduled` и
`product-news-moderation--scheduled-local`. Production E2E проходит создание,
reload сохранённого edit draft и перенос срока в Chromium, Firefox и WebKit.
Редактирование уже видимой публикации остаётся следующим implementation
increment: admin может исправить текст, feed показывает `updatedAt`, но повторное
notification event не создаётся. Текущий `409` — известный разрыв реализации,
а не открытая продуктовая развилка. Proof текущего scheduled-only состояния:
[`phase8-local-news-editing-2026-08-03.md`](../../../pwa_tests/reports/phase8-local-news-editing-2026-08-03.md).

## Инкремент исправления опубликованной local news — 3 августа 2026

Global admin может исправить plain text уже видимой локальной PWA-новости.
Каждое содержательное исправление создаёт immutable revision и новое
`editedAt`; Student/Family feed и Staff moderation показывают исправленный
текст и отметку «Обновлено». Исходные owner и `published_at` неизменны.

API принимает для опубликованной записи только `{schemaVersion, text}`.
Переданный `publishedAt` отклоняется; notification events и delivery outbox
остаются теми же сохранёнными строками, поэтому повторной рассылки нет.
Optimistic `If-Match`, privacy-safe audit и transaction rollback сохранены.

Story IDs: `pages-staff-local-news-composer--editing-published` и
`product-news-moderation--published-local-correction`. Production E2E-сценарий
проверяет заблокированное время и фактическое PATCH-тело без `publishedAt`.
Автоматический browser-run на текущем macOS host не стартовал из-за внешнего
Chromium `MachPortRendezvous`; snapshots не обновлялись и visual acceptance не
заявляется. Proof:
[`phase8-published-local-news-correction-2026-08-03.md`](../../../pwa_tests/reports/phase8-published-local-news-correction-2026-08-03.md).

## Инкремент настоящих Family notification settings — 3 августа 2026

Route `/family/profile/notifications` больше не показывает prototype/no-op
кнопку. Он читает и изменяет account-scoped preferences через реальный aiohttp,
управляет browser/server push subscription и показывает loading/error/denied/
unsupported states. Family видит шесть работающих категорий общих материалов,
новостей и явного итога занятия; per-problem review, oral и classroom push не
предлагаются.
Course override остаётся Student-only.

Browser subscription handshake переиспользуется Student и Family через
`usePushDevice`, а presentation — через `PushDeviceControls`. Story IDs:
`pages-family-notifications--ready`, `--loading`, `--error`, `--push-denied`,
`pages-family--notifications`, `product-connectivity--push-device-states`.
Production E2E меняет preference, подтверждает reload и восстанавливает fixture
в Chromium, Firefox и WebKit. Proof:
[`phase8-family-notification-settings-2026-08-03.md`](../../../pwa_tests/reports/phase8-family-notification-settings-2026-08-03.md).

## Инкремент явной Family lesson digest — 3 августа 2026

Admin отдельно preview-ит и подтверждает один итог конкретной группы и занятия.
Уже уведомлённые Family accounts не получают дубль, а поздно связанный аккаунт
получает первое событие. Последующие исправления обновляют Family API без
автоматической повторной рассылки; отсутствие review queue не запускает
действие. Staff и Family UI, strict contracts/client, owner-scoped invalidation,
API/integration proof и production-build Playwright scenario реализованы.
Browser execution и visual acceptance остаются открыты из-за внешнего macOS
launcher failure. Proof:
[`phase8-family-digest-2026-08-03.md`](../../../pwa_tests/reports/phase8-family-digest-2026-08-03.md).

## Инкремент уведомления об устном окне — 3 августа 2026

Существующий scheduler теперь создаёт `oral_window` event в момент фактического
открытия настроенного окна. Получатели разрешаются тогда же по текущим active
group и `attendance_mode=online`, поэтому поздняя смена режима не оставляет
заранее сформированную рассылку. Family и очные школьники исключены.

Первый проход после startup подхватывает ещё открытое окно; последующие читают
только новый interval. Account/category/window dedupe делает два production
worker идемпотентными. Event не содержит Zoom URL/code, а owner-scoped NATS
остаётся только refetch hint после durable SQLite commit. Proof:
[`phase8-oral-window-notifications-2026-08-03.md`](../../../pwa_tests/reports/phase8-oral-window-notifications-2026-08-03.md).
