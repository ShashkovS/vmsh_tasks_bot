# Realtime, offline и уведомления

## Foreground realtime

Каждое приложение открывает свой WebSocket. Handshake до upgrade проходит тот
же exact target/proxy/Origin boundary, что browser API, и требует действующую
access-cookie именно этого audience. После `prepare()` соединение связывается с
server-authoritative `accountId` и 32-hex session ID; присланная клиентом
identity никогда не используется для маршрутизации. При первом соединении без
cursor сервер посылает `connected`. Клиент шлёт `ping`, сервер отвечает `pong`;
network backoff имеет jitter и не создаёт reconnect storm. Событие `invalidate`
содержит список ресурсов, причину и audience — после него TanStack Query
повторно читает авторитетное состояние. Handshake, pong, protocol errors,
invalidation и close сериализуются одним per-socket lock с ограничением
конкурентности и времени операции.

Cursor полезен только внутри уже живого соединения и не является durable event offset. Любое повторное подключение передаёт cursor и всегда получает `resync-required`, после чего клиент полностью читает версию/состояние из SQLite. Сравнивать cursor разных gunicorn workers и делать вывод «ничего не пропущено» запрещено.

Production-клиент находится в
[`packages/app-shell/src/realtime.tsx`](../packages/app-shell/src/realtime.tsx)
и подключён к Student, Family и Staff после `AuthenticationProvider`. URL
строится только из validated runtime path и текущего origin; session token,
account ID и другие credentials в URL, Query key либо Web Storage не попадают.
Каждый входящий frame проходит JSON parse и Zod-validation до любого изменения
Query state. Неверный audience, binary/malformed frame и неожиданный повторный
handshake закрывают соединение как protocol failure.

Клиент хранит cursor только в памяти. На первом соединении он принимает только
`connected`; на каждом повторном — только `resync-required` и вызывает полный
refetch активных TanStack Query до перехода в `ready`. Invalidations
коалесцируются перед refetch. Heartbeat, handshake и отсутствие pong имеют
ограниченные таймауты; backoff экспоненциальный, ограниченный и с jitter.
Offline/hidden не создают reconnect storm. Policy close `1008` и
неоднозначный clean close `1000` выполняют authoritative `/auth/me` проверку:
действующая сессия продолжает bounded reconnect, отозванная завершает локальный
auth state, а transient network/5xx остаётся отдельным `unavailable` и повторяет
authority check с bounded backoff. Последнее нужно для transport layers,
которые не сохраняют точный close code; server integration tests по-прежнему
отдельно проверяют `1008`.

NATS переносит invalidation между процессами. В Phase 1 используются два
строго изолированных subject внутри runtime prefix: `pwa_invalidate` и
`pwa_session_control`. Отсутствующий audience в invalidation означает общий
event для Student, Family и Staff; заданный `student`, `family` или `staff`
ограничивает fan-out соответствующим набором соединений. Необязательный
канонический `accountId` разрешён только вместе с audience и маршрутизирует
событие всем вкладкам/сессиям одного аккаунта; это поле остаётся broker routing
metadata и не попадает в browser payload или лог. Неизвестные поля, owner без
audience и неканонические IDs отвергаются. При отсутствии NATS тестовый
однопроцессный wrapper вызывает тот же callback. Текущий production baseline —
два gunicorn worker, поэтому production требует NATS; увеличение числа workers
не меняет протокол.

Audience scope не является user scope. Phase-1 authenticated registry уже
поддерживает owner-account scope; сервис, публикующий приватную invalidation,
сначала проверяет право и передаёт только проверенный account public ID.
Course/group/student mapping остаётся обязанностью предметного service layer
следующих фаз. Независимо от события API повторно проверяет authorization.

Logout, ручной revoke и logout-all сначала закрывают подходящие локальные
сокеты, затем публикуют строгую cross-worker команду `auth.close`. Session
target всегда 32 lowercase hex, account target использует канонический public
ID. Refresh-only logout создаёт команду только если repository доказал текущий
либо consumed refresh secret; malformed/foreign cookie сохраняет равномерный
`204` и не становится DoS-oracle. Ошибка transient publication не отменяет
локальный close: периодическая bounded-проверка снова читает versions,
expiry/revoke/account/credential/principal из SQLite и fail-closed закрывает
оставшиеся соединения.

Назначение аудитории разделяет изменение состояния и доставку. После confirm/change owner-scoped `classroom.assignment.changed` тихо инвалидирует Student и каждый связанный Family account; оба читают authoritative `not_applicable | reassigning | assigned`, имя комнаты и `confirmedAt` из SQLite. Это событие не создаёт notification delivery.

Только admin-only «Разослать аудитории» после preview создаёт immutable delivery batch и `classroom.assignment.announced` для Student. Выбранный PWA-канал создаёт in-app/push, Telegram-канал отправляет личное сообщение через существующего бота. Family не получает classroom push/Telegram. Изменение плана после batch отображается Staff как неразосланное, но автоматический resend запрещён; admin повторяет preview/send явно. Browser/WS payload никогда не содержит token или Telegram chat ID.

Owner-confirmed report допускает частичный успех и раскрываемые списки. Статус
batch содержит по каждому выбранному каналу `selected`, `eligible`,
`suppressed`, `queued`, `attempted`, `succeeded`, `failed` и общие
`deliveredAny`, `deliveredAll`, `partial`. Частичный успех допустим: получатель,
которому сообщение пришло хотя бы по одному каналу, считается охваченным, но
остаётся в раскрываемом списке partial delivery. Список использует только
безопасную публичную identity и per-channel status. По implementation default
действие «Повторить ошибки» создаёт новую попытку только failed
channel-recipient pairs; успешные пары исходного batch не создаются повторно.

## Background

Web Push используется только вне foreground и делится на категории: учебный цикл, результат проверки, новый комментарий, новости, организационные сообщения. Пользователь отдельно разрешает категории; отказ браузера не блокирует кабинет. Notification click ведёт на устойчивый deep link внутри audience scope.

Service worker precache-ит shell, KaTeX CSS/fonts и безопасные статические assets. API/auth ответы не попадают в общий Cache Storage. Текущий production precache около 1.4 MiB и укладывается в бюджет 10–15 MB; значительную часть составляют форматы шрифтов KaTeX. После стабилизации реального математического корпуса нужно оставить необходимые web-форматы/subsets и повторно проверить glyph coverage. Недавно открытые изображения кешируются примерно на 14 дней с LRU/quota cleanup. Версия обновляется через явное неблокирующее состояние «доступно обновление» с возможностью применить его после сохранения draft.

На iOS потеря IndexedDB после долгого отсутствия допустима как платформенный риск: уже зафиксированные авторитетные данные находятся на сервере. Во время обычной сессии reload, закрытие вкладки или применение PWA update не должны терять незавершённую работу. Student/Family мягко предлагают установку PWA, но отказ не блокирует работу.

## Offline data

Student и Family имеют отдельные Dexie namespaces по audience и runtime instance. Поддерживаются:

- чтение ранее открытых листков, новостей, подсказок и решений согласно правам на момент cache;
- локальные текстовые drafts;
- подготовленные фотографии и очередь письменной сдачи;
- отображение точного состояния: offline, local draft, queued, uploading, retrying, synced, conflict, failed.

Owner-confirmed core разрешает после прежнего входа холодный offline-запуск без
повторного credential и допускает потерю непустого outbox при подтверждённом
logout после предупреждения. Implementation default делает кеш account-scoped,
показывает `offline-unverified`, ограничивает доступ известным
`sessionExpiresAt`, а queued mutations синхронизирует только после auth refresh.
Подтверждённый logout, account switch или очистка удаляют cache, drafts и outbox,
чтобы данные одного пользователя общего устройства не показывались другому.

Phase-1 frontend уже реализует узкую безопасную часть этого контракта:
подтверждённый в текущей вкладке principal переживает transient refetch failure
как явно непроверенное offline-состояние, но только до абсолютного server
`sessionExpiresAt`; expiry срабатывает также после browser resume и немедленно
размонтирует private shell. Cold start с персистентным чтением/черновиками и
account-scoped Dexie projection ещё не реализован и не считается готовым.

Phase-1 session UI уже предоставляет `SessionOfflineWorkGuard`, но не выдаёт
отсутствующий Dexie/outbox за готовый. Будущий adapter проверяет локальную
очередь до current logout/logout-all: ошибка проверки блокирует выход,
непустая очередь показывает отдельное предупреждение, а cleanup callback
запускается строго после успешного server logout и продолжает выполняться при
размонтировании private shell. До подключения durable adapter текущие
Student/Family profiles не показывают вымышленный queued count; это явно
отложенная часть offline-этапа.

Для Student и Staff действует общий draft persistence contract. Небольшой сериализуемый текст и значимое UI-state записываются в `localStorage` после каждого осмысленного изменения; blobs, подготовленные фотографии и outbox — в Dexie. Ключ включает runtime, audience, account, entity kind/public ID и base version. При открытии экран предлагает восстановить совместимый draft; конфликт с новой server version не перезаписывается молча. Draft удаляется после server receipt/confirm или явного discard. Logout/account switch предупреждает и не раскрывает draft другому аккаунту. Session secrets в Web Storage не попадают.

Одна логическая письменная сдача содержит text и до 10 фотографий и становится видима teacher только после загрузки всего выбранного набора. Failed file повторяется отдельно. До первого review lock исходную отправку можно изменить/удалить с confirmation; после lock новый материал добавляется отдельной entry, меняет thread version и должен войти в текущую проверку. Порядок меняется кнопками вверх/вниз. Worker создаёт WebP до 1920 px, original не хранится; HEIC fallback выполняет server image service.

## Outbox и дедлайн

Каждая queued mutation получает UUID idempotency key, `createdAtClient`, timezone offset, payload hash и номер попытки. Сервер записывает `receivedAtServer`, решение дедлайна и audit. Дедлайн — отдельный `submission_closes_at` lesson window в `Europe/Moscow`, хранимый в UTC; solution schedule/publication остаются независимыми. Полученная после cutoff отправка, созданная до него, обрабатывается обычно; расхождение часов больше часа маркируется для диагностики.

Review notifications всех задач ученика объединяются за 30 минут. Quiet hours считаются в timezone пользователя и подавляют только sound. Review event считается прочитанным, когда видимый PWA-клиент непрерывно выдержал три секунды и отправил идемпотентный acknowledgement; server ставит собственный account-scoped `readAt`, а другие устройства сходятся через invalidation/refetch. Telegram delivery без read receipt не снимает badge. Task badge считает обновлённые задачи, которые student ещё не видел. Family по умолчанию получает один недельный итог после окончания проверки.

Production route `/family/profile/notifications` использует настоящий
account-scoped preferences и push-subscription API. Family может включать и
отключать push для нового урока, подсказок, решений, дедлайна и новостей;
индивидуальная проверка, устное окно и аудитория намеренно не предлагаются.
Course-specific override остаётся Student-only. Точный server trigger
недельного Family-итога до реализации зафиксирован вопросом 8 в
[`22-development-questions.md`](../dev/development-plan/22-development-questions.md).

`oral_window` создаётся при фактическом открытии окна для текущих online Student
активной группы. Recipient set не материализуется при редактировании расписания:
это исключает Family, очный режим и устаревшее членство. Startup подхватывает
окно, которое уже открылось и ещё не закрылось; два worker сходятся через
dedupe SQLite. Join URL/code отсутствуют в event и читаются только отдельным
no-store endpoint после повторной проверки Student scope.

До отдельного подтверждения UX действует безопасное допущение: повтор с тем же ключом и payload hash возвращает тот же результат. Другой payload с тем же ключом получает conflict: исходная операция сохраняется, last-write-wins запрещён, а новая отправка возможна с новым ключом после явного решения пользователя. FIFO действует внутри одной сущности; независимые drafts могут синхронизироваться параллельно. Logout предупреждает о неотправленных данных; после явного подтверждения очередь и drafts этого аккаунта можно удалить.

Notification preferences имеют общий default и optional course override. Invalidations сужаются полями `audience`, `courseId`, `groupId`, `studentUserId`; приватное событие не рассылается другим аудиториям или enrollment. После reconnect клиент всегда делает authoritative refetch. Набор course/group событий перечислен в [многокурсовом контракте](courses-groups-and-lessons.md).
