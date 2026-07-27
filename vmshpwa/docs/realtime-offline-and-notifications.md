# Realtime, offline и уведомления

## Foreground realtime

Каждое приложение открывает свой WebSocket. При первом соединении без cursor сервер посылает `connected`. Клиент шлёт `ping`, сервер отвечает `pong`; network backoff имеет jitter и не создаёт reconnect storm. Событие `invalidate` содержит список ресурсов, причину и необязательный audience — после него TanStack Query повторно читает авторитетное состояние.

Cursor полезен только внутри уже живого соединения и не является durable event offset. Любое повторное подключение передаёт cursor и всегда получает `resync-required`, после чего клиент полностью читает версию/состояние из SQLite. Сравнивать cursor разных gunicorn workers и делать вывод «ничего не пропущено» запрещено.

NATS переносит invalidation между процессами. Отсутствующий audience означает общий event для Student, Family и Staff; заданный `student`, `family` или `staff` ограничивает fan-out соответствующим набором соединений. Отправка сокетам внутри процесса выполняется конкурентно. При отсутствии NATS тестовый однопроцессный wrapper вызывает тот же callback. Текущий production baseline — два gunicorn worker, поэтому production требует NATS; увеличение числа workers не меняет протокол.

Audience scope не является user scope. До появления authenticated WebSocket principal запрещено публиковать через student/family-wide invalidation приватный submission ID или другой идентификатор, видимый только одному аккаунту. Owner-scoped fan-out добавляется вместе с реальными сессиями: соединение связывается с account/user ID, а backend проверяет право до отправки. Независимо от события API повторно проверяет authorization.

Назначение аудитории разделяет изменение состояния и доставку. После confirm/change owner-scoped `classroom.assignment.changed` тихо инвалидирует Student и каждый связанный Family account; оба читают authoritative `not_applicable | reassigning | assigned`, имя комнаты и `confirmedAt` из SQLite. Это событие не создаёт notification delivery.

Только admin-only «Разослать аудитории» после preview создаёт immutable delivery batch и `classroom.assignment.announced` для Student. Выбранный PWA-канал создаёт in-app/push, Telegram-канал отправляет личное сообщение через существующего бота. Family не получает classroom push/Telegram. Изменение плана после batch отображается Staff как неразосланное, но автоматический resend запрещён; admin повторяет preview/send явно. Browser/WS payload никогда не содержит token или Telegram chat ID.

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

Для Student и Staff действует общий draft persistence contract. Небольшой сериализуемый текст и значимое UI-state записываются в `localStorage` после каждого осмысленного изменения; blobs, подготовленные фотографии и outbox — в Dexie. Ключ включает runtime, audience, account, entity kind/public ID и base version. При открытии экран предлагает восстановить совместимый draft; конфликт с новой server version не перезаписывается молча. Draft удаляется после server receipt/confirm или явного discard. Logout/account switch предупреждает и не раскрывает draft другому аккаунту. Session secrets в Web Storage не попадают.

Одна логическая письменная сдача содержит text и до 10 фотографий и становится видима teacher только после загрузки всего выбранного набора. Failed file повторяется отдельно. До первого review lock исходную отправку можно изменить/удалить с confirmation; после lock новый материал добавляется отдельной entry, меняет thread version и должен войти в текущую проверку. Порядок меняется кнопками вверх/вниз. Worker создаёт WebP до 1920 px, original не хранится; HEIC fallback выполняет server image service.

## Outbox и дедлайн

Каждая queued mutation получает UUID idempotency key, `createdAtClient`, timezone offset, payload hash и номер попытки. Сервер записывает `receivedAtServer`, решение дедлайна и audit. Дедлайн — отдельный `submission_closes_at` lesson window в `Europe/Moscow`, хранимый в UTC; solution schedule/publication остаются независимыми. Полученная после cutoff отправка, созданная до него, обрабатывается обычно; расхождение часов больше часа маркируется для диагностики.

Review notifications всех задач ученика объединяются за 30 минут. Quiet hours считаются в timezone пользователя и подавляют только sound. Review event считается прочитанным, когда видимый PWA-клиент непрерывно выдержал три секунды и отправил идемпотентный acknowledgement; server ставит собственный account-scoped `readAt`, а другие устройства сходятся через invalidation/refetch. Telegram delivery без read receipt не снимает badge. Task badge считает обновлённые задачи, которые student ещё не видел. Family по умолчанию получает один недельный итог после окончания проверки.

До отдельного подтверждения UX действует безопасное допущение: повтор с тем же ключом и payload hash возвращает тот же результат. Другой payload с тем же ключом получает conflict: исходная операция сохраняется, last-write-wins запрещён, а новая отправка возможна с новым ключом после явного решения пользователя. FIFO действует внутри одной сущности; независимые drafts могут синхронизироваться параллельно. Logout предупреждает о неотправленных данных; после явного подтверждения очередь и drafts этого аккаунта можно удалить.

Notification preferences имеют общий default и optional course override. Invalidations сужаются полями `audience`, `courseId`, `groupId`, `studentUserId`; приватное событие не рассылается другим аудиториям или enrollment. После reconnect клиент всегда делает authoritative refetch. Набор course/group событий перечислен в [многокурсовом контракте](courses-groups-and-lessons.md).
