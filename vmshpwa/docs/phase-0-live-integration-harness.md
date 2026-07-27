# Phase 0: изолированный NATS и Telegram test harness

Этот документ описывает только инфраструктурную проверку границ. NATS здесь
доставляет transient invalidation, а Telegram — один синтетический
send/edit/delete probe. Ни один из этих контуров не заменяет SQLite/outbox и не
является production-функцией публикации.

## Обычный hermetic-контур

- [`helpers/nats_brocker.py`](../../helpers/nats_brocker.py) предоставляет
  `JsonBroker`, `InProcessBroker` и one-owner `NatsBroker`. Историческое имя
  файла и `vmsh_nats` сохранены только для legacy game adapter.
- [`apps/pwa_app.py`](../../apps/pwa_app.py) получает broker через
  `PWA_BROKER`; startup/shutdown одного aiohttp app больше не подключает и не
  отключает broker другого app.
- Prefix и topic состоят только из dot-separated ASCII tokens без `*`, `>` и
  пробелов. Новый subject имеет вид `<profile-prefix>.<topic>`. Такой namespace
  следует официальной рекомендации NATS начинать subject с отдельного
  namespace token. Core NATS остаётся at-most-once pub/sub: после reconnect
  PWA всё равно перечитывает authoritative state из SQLite.
- Startup после `subscribe` делает NATS `flush`, чтобы readiness означала, что
  server уже зарегистрировал subscription. Reconnecting connection временно не
  объявляется рабочей; shutdown пробует graceful `drain`, а если тот невозможен
  во время reconnect — bounded `close`.
- Cursor ведётся отдельно для Student, Family и Staff: staff-only invalidation
  не раскрывает другим аудиториям даже количество событий. Один медленный
  browser ограничен send timeout и перед удалением из fan-out получает
  bounded `close`; если закрытие не удалось, socket остаётся tracked для
  повторной попытки при shutdown. Все tracked WebSocket закрываются с
  `GOING_AWAY` до отключения broker.
- In-process adapter делает настоящий JSON encode/decode round-trip, запускает
  всех подписчиков конкурентно и сообщает об ошибках только после завершения
  всего fan-out. Datetime, tuple, non-string keys, non-finite numbers и integer
  вне signed 64-bit отвергаются одинаково до публикации.
- [`pwa_tests/conftest.py`](../../pwa_tests/conftest.py) устанавливает
  `pwa-e2e` до collection/import. Поэтому даже прямой запуск Python-тестов не
  загружает legacy Telegram/Google credentials и не собирает legacy adapters.
- [`helpers/pwa/telegram_test_harness.py`](../../helpers/pwa/telegram_test_harness.py)
  содержит сетевой `Protocol` и `RecordingBot`. Обычные unit/E2E проверяют
  getMe/getChat/getChatMember/send/edit/delete полностью без сети.

Hermetic checks:

```bash
.venv/bin/python -m pytest -q -n0 \
  pwa_tests/test_nats_broker.py \
  pwa_tests/test_pwa_app.py \
  pwa_tests/test_telegram_test_harness.py
```

Проверено 27 июля 2026 года: **74 passed** в трёх focused-файлах; полный
`make pwa-test` — **29 TypeScript passed**, **407 Python passed, 1 skipped**.

## Opt-in local NATS smoke

[`pwa_tests/integration/test_nats_live.py`](../../pwa_tests/integration/test_nats_live.py)
по умолчанию skipped. Явный запуск использует только
`nats://127.0.0.1:4222`, генерирует одноразовый prefix
`vmshpwa_agent_smoke_<run-id>`, проверяет fan-out и отсутствие доставки в
другой agent prefix. Тест не запускает и не останавливает `nats-server`.

```bash
make pwa-nats-local-smoke
```

Сетевой smoke допустим только при уже запущенном пользовательском локальном
сервере. Адрес нельзя заменить environment-переменной на внешний NATS.
Фактический результат первого прогона зафиксирован в
[`pwa_tests/reports/phase0-nats-local.md`](../../pwa_tests/reports/phase0-nats-local.md).

## Строго opt-in Telegram capability smoke

[`vmshpwa/scripts/telegram_test_capability.py`](../scripts/telegram_test_capability.py)
не импортирует `helpers.config`, не запускает polling/webhook и читает только
ключ `telegram_bot_token` из фиксированного ignored-файла
`creds_test/vmsh_bot_config_test.json`. Production config и environment token
не поддерживаются.

Live workflow намеренно двухшаговый. Сначала read-only bind:

```bash
VMSH_RUN_TELEGRAM_LIVE_SMOKE=1 \
VMSH_TELEGRAM_TEST_CHANNEL_ID='<canonical-negative-chat-id>' \
  make pwa-telegram-bind-test-channel
```

Bind делает `getMe/getChat/getChatMember`, требует private channel без public
username и сохраняет неизменяемую identity в owner-only
`.runtime/vmshpwa/telegram-smoke/bindings.sqlite3`. Если там уже закреплена
другая identity, команда отказывается её заменять. Bind сообщений не отправляет.

До bind обязательны все проверки:

1. одновременно переданы `--live`, точная confirmation-фраза и отдельный
   environment-флаг;
2. `PROD=true` отсутствует;
3. задан уже канонический signed channel ID; положительный UI fragment
   отвергается, а `-100` никогда не дописывается эвристически;
4. `getMe` вернул именно `@vmsh179devbot`;
5. `getChat` вернул тот же canonical ID, type `channel` и точный title
   `vmsh179devbot channel`;
6. `getChatMember` подтвердил administrator/creator и права post/edit/delete.

Write-enabled smoke не принимает destination из environment: он загружает
`VerifiedTelegramBinding` только из локальной SQLite, ещё раз сверяет всю
identity через Bot API и лишь затем выполняет lifecycle. Текст фиксирован кодом,
notification отключён, после send выполняется edit, а delete находится в
`finally` и пробуется также при ошибке edit. Команда сохраняет safe JSON только в
`.runtime/vmshpwa/telegram-smoke/`: run marker, canonical IDs, operation flags и
generic error code. Файл создаётся с mode `0600`. Token, remote error text и
config payload в отчёт не входят.

Команда write-enabled smoke после принятого bind:

```bash
VMSH_RUN_TELEGRAM_LIVE_SMOKE=1 \
  make pwa-telegram-live-smoke
```

В рамках Phase-0 implementation increment write-enabled команда **не
запускалась**: UI fragment `3913815635` не преобразуется эвристически, прямой
`getChat` его не разрешил, а у test bot включён webhook, поэтому `getUpdates`
недоступен. Нужен canonical signed `chat.id` из webhook update или другого
авторитетного Bot API результата. Первый живой результат заносится в копию
[`pwa_tests/reports/phase0-live-integration-template.md`](../../pwa_tests/reports/phase0-live-integration-template.md),
но runtime JSON с private canonical ID не коммитится.

Phase 0 доказывает identity и простой send/edit/delete lifecycle. Rich Message,
`tg-math`, tables, media и albums проверяются тем же trusted binding как часть
content acceptance в Phase 2, когда существует целевой renderer и cleanup всех
returned message IDs.

## Актуальные первичные источники

- [NATS subject naming and namespace guidance](https://docs.nats.io/nats-concepts/subjects)
- [Core NATS publish/subscribe fan-out](https://docs.nats.io/nats-concepts/core-nats/pubsub)
- [NATS drain and flush behavior](https://docs.nats.io/using-nats/developer/anatomy)
- [nats.py 2.13.1 client implementation](https://github.com/nats-io/nats.py/tree/v2.13.1)
- [aiohttp graceful shutdown for tracked WebSockets](https://docs.aiohttp.org/en/stable/web_advanced.html#graceful-shutdown)
- [Telegram Bot API: getMe](https://core.telegram.org/bots/api#getme)
- [Telegram Bot API: getChat and getChatMember](https://core.telegram.org/bots/api#getchat)
- [Telegram Bot API: administrator capabilities](https://core.telegram.org/bots/api#chatmemberadministrator)
- [Telegram Bot API: editMessageText and deleteMessage](https://core.telegram.org/bots/api#editmessagetext)
