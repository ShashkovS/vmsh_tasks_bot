# Phase 7D: явная рассылка аудиторий

Дата проверки: 2026-07-29.

## Что работает

- Admin получает безопасный preview подтверждённого плана: получатели, изменившиеся назначения и доступность PWA/Telegram без `chat_id` и токенов.
- Отдельный POST создаёт immutable snapshot выбранных каналов и получателей. Повтор с тем же idempotency key возвращает тот же batch; повтор с другим payload получает conflict.
- PWA-объявление сразу фиксирует `announcedAt` и инвалидирует только Student. Family видит актуальное значение при следующем чтении, но не получает classroom notification.
- Telegram-получатели сохраняются с server-side `users.chat_id` в состоянии `queued`. Этот этап не изображает отправку успешной до подключения транспортного воркера Phase 8.
- Новое подтверждение плана ничего автоматически не рассылает.

## Реализация

- migration: `0061.pwa_classroom_assignment_delivery`;
- SQLite: `db_methods/pwa/classroom_delivery.py`;
- правила preview/snapshot/idempotency: `models/pwa/classroom_delivery.py`;
- HTTP: `apps/pwa_api/classroom_delivery_routes.py`;
- Student/Family projection: `db_methods/pwa/classroom_assignments.py` и `models/pwa/classroom_public.py`.

## Проверки

- migration up/down/up, snapshot privacy, PWA announcement, idempotency, stale preview и unconfirmed plan: `pwa_tests/integration/test_phase7_classroom_delivery.py`;
- authenticated admin/teacher API, owner-scoped realtime и одинаковое read state Student/Family: `pwa_tests/integration/test_classroom_catalog_http_api.py::test_admin_materializes_updates_and_confirms_classroom_layout`;
- canonical migration-head inventory: `pwa_tests/test_schema_inventory.py`.

Прогоны:

- migration/domain/schema: `30 passed`;
- authenticated aiohttp slice: `1 passed`;
- Ruff по затронутым Python-файлам: pass.

## Оставшаяся граница

Phase 8 должен обработать `telegram_state = queued`, вызвать существующего Telegram-бота, записать `sent|failed` и дать admin явный retry только неуспешных пар recipient/channel. Web Push и общий notification center также остаются Phase 8; они не меняют правило явной рассылки.
