# Phase 8A: Telegram transport для аудиторий

Дата проверки: 2026-07-29.

## Результат

- Telegram используется только когда legacy `tg_bot` явно включён рядом с PWA либо sender передан тестом.
- Чистый PWA startup по-прежнему не импортирует Telegram credentials и не запускает polling.
- Явный classroom delivery отправляет личное plain-text сообщение каждому доступному школьнику.
- Получатель атомарно помечается как обрабатываемый до сетевого вызова: повторный обработчик не забирает ту же строку одновременно.
- Успех записывается как `sent`; Telegram/API/сетевая ошибка — как стабильный error code и `failed`.
- Batch завершается как `completed` или `completed_with_errors`; при отсутствии Telegram adapter честно остаётся `queued`.
- `chat_id` читается только внутренним transport-запросом и не попадает в HTTP payload, лог или fixture.

## Реализация

- Transport: `apps/pwa_api/classroom_delivery_transport.py`.
- Опциональное подключение legacy bot: `apps/pwa_app.py`.
- Текст сообщения: `helpers/pwa/classroom_delivery.py`.
- Storage-only операции claim/result/finalize: `db_methods/pwa/classroom_delivery.py`.

## Доказательства

- `pwa_tests/integration/test_phase7_classroom_delivery.py`: `5 passed`, включая single-claim и failed batch.
- Authenticated classroom HTTP flow с синтетическим sender: `1 passed`; проверены адресат, полный текст, `sent` и итоговый report.
- `pwa_tests/test_pwa_app.py`: `36 passed`; hermetic PWA startup и WebSocket не затронуты.
- Ruff format/check: успешно.
- Внешний Telegram API в unit/integration не вызывался.

## Следующий инкремент

Нужен admin-only `retry-failed`: новая явная попытка должна возвращать в очередь только failed Telegram rows, проверять версию batch и не трогать уже доставленные сообщения. После этого live smoke выполняется только через разрешённый test bot/test channel harness.
