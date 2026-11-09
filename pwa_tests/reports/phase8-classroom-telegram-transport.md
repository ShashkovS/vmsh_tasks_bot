# Phase 8A: Telegram transport для аудиторий

Дата проверки: 2026-07-29.

## Результат

- Telegram используется только когда legacy `tg_bot` явно включён рядом с PWA либо sender передан тестом.
- Чистый PWA startup по-прежнему не импортирует Telegram credentials и не запускает polling.
- Явный classroom delivery отправляет личное plain-text сообщение каждому доступному школьнику.
- Получатель атомарно помечается как обрабатываемый до сетевого вызова: повторный обработчик не забирает ту же строку одновременно.
- Успех записывается как `sent`; Telegram/API/сетевая ошибка — как стабильный error code и `failed`.
- Batch завершается как `completed` или `completed_with_errors`; при отсутствии Telegram adapter честно остаётся `queued`.
- Admin может явно повторить только failed Telegram-строки. Версия batch и idempotency key защищают от stale/double retry; `sent` не сбрасывается.
- `chat_id` читается только внутренним transport-запросом и не попадает в HTTP payload, лог или fixture.

## Реализация

- Transport: `apps/pwa_api/classroom_delivery_transport.py`.
- Опциональное подключение legacy bot: `apps/pwa_app.py`.
- Текст сообщения: `helpers/pwa/classroom_delivery.py`.
- Storage-only операции claim/result/finalize: `db_methods/pwa/classroom_delivery.py`.

## Доказательства

- `pwa_tests/integration/test_phase7_classroom_delivery.py`: `6 passed`, включая reversible retry migration, single-claim, failed-only reset, stale version и idempotency.
- Authenticated classroom HTTP flow с синтетическим sender: `1 passed`; проверены адресат, полный текст, `sent`, явный retry и отсутствие дублирования при повторе запроса.
- `pwa_tests/test_pwa_app.py`: `36 passed`; hermetic PWA startup и WebSocket не затронуты.
- Schema inventory: `374` product objects, check и `21` schema tests прошли.
- Frontend: lint/typecheck/build успешно, `449` unit tests и `204` Storybook browser/a11y tests прошли; Staff retry подключён к реальному API.
- Ruff format/check: успешно.
- Внешний Telegram API в unit/integration не вызывался.

## Следующий инкремент

Live smoke выполняется только через разрешённый test bot/test channel harness. Следующий основной инкремент Phase 8 — общая модель in-app notification events/preferences, после неё Web Push и Telegram news mirror.
