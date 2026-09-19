# Сверка запланированных публикаций Telegram

Этот runbook нужен перед будущим включением Staff-планировщика публикаций. В
первой версии сообщения, вручную запланированные редакторами в приложении
Telegram, остаются под управлением Telegram и не импортируются автоматически.

## Почему инвентарь ручной

По состоянию на 3 августа 2026 года Bot API сообщает боту о новых и
отредактированных channel posts, но не предоставляет метод чтения очереди
сообщений, запланированных человеком в Telegram-клиенте. Telegram MTProto API
умеет читать scheduled history, однако официальный
[`messages.getScheduledMessages`](https://core.telegram.org/method/messages.getScheduledMessages)
доступен только пользовательским сессиям. Описание очереди находится в
[официальной документации scheduled messages](https://core.telegram.org/api/scheduled-messages),
а перечень Bot API updates — в
[Telegram Bot API](https://core.telegram.org/bots/api#update).

Мы не добавляем user-account session и не расширяем доступ бота ради одноразовой
сверки. Владелец каждой destination вручную просматривает очередь в обычном
Telegram-клиенте и составляет локальный owner-only JSON. Утилита не обращается
к сети, Telegram, Google или production SQLite.

## Формат инвентаря

За основу берётся синтетический пример
[`telegram-scheduled-queue-v1.json`](../../pwa_tests/fixtures/telegram-scheduled-queue-v1.json).
Каждая строка содержит:

- локальный непрозрачный `itemKey`;
- `destinationKey` — `public_id` уже проверенного `telegram_binding`, а не raw
  `chat_id`;
- время с явным timezone;
- SHA-256 текущей и просмотренной content revision;
- SHA-256 текущего и просмотренного media manifest либо `null`;
- ровно одно решение:
  `retain_in_telegram`, `cancel_and_recreate_in_staff` или
  `cancel_as_obsolete`;
- `staffDraftKey` только для варианта с переносом в Staff.

Текст, Telegram message/chat IDs, bot token, имена и контакты в файл не входят.
После любого изменения запланированного сообщения текущий hash расходится с
просмотренным, и cutover блокируется до нового просмотра.

## Проверка

```sh
make pwa-telegram-schedule-reconcile \
  PWA_TELEGRAM_SCHEDULE_INVENTORY=/absolute/owner-only/inventory.json \
  PWA_TELEGRAM_SCHEDULE_REPORT=.runtime/vmshpwa/telegram-schedule-report.json
```

Команда завершается успешно только при `status=ready`. Она блокирует:

- изменение content/media после просмотра;
- повторный `itemKey`;
- две активные публикации с одинаковыми destination, временем и revision;
- повторное использование одного Staff draft;
- отсутствие Staff draft у `cancel_and_recreate_in_staff`;
- лишние или неизвестные поля, включая попытку положить payload в inventory.

Публичный aggregate report содержит только counts, номера строк и стабильные
коды проблем. Он не повторяет ключи, hashes или содержимое инвентаря.

## Выполнение cutover

1. Пока Staff scheduler не реализован, все записи остаются
   `retain_in_telegram`; этот runbook ничего не отменяет и не отправляет.
2. Перед включением scheduler создаются реальные Staff drafts для выбранных
   `cancel_and_recreate_in_staff` строк.
3. После `ready` владелец вручную выполняет отмеченные отмены в Telegram и
   отдельно публикует/активирует проверенные Staff drafts.
4. Отчёт сохраняется как privacy-safe deployment proof. Owner-only inventory
   не коммитится и после приёмки удаляется вручную.

Удаление уже опубликованных channel posts — другой процесс. Bot API не присылает
обычный `deleted_channel_post`, поэтому отсутствие сообщения нельзя выводить из
отсутствия update; для этого нужен отдельный явный deletion reconciliation.
