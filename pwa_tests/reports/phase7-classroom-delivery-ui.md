# Phase 7: явная рассылка аудиторий

Дата проверки: 2026-07-29.

## Проверяемый результат

- После подтверждения плана Staff отдельно запрашивает предпросмотр и выбирает PWA и/или Telegram.
- Предпросмотр показывает получателей, изменившиеся назначения и недоступность Telegram, не раскрывая `chat_id`.
- Созданная рассылка и её получатели остаются в SQLite; после перезагрузки Staff получает последнюю рассылку очного события через `delivery-latest`.
- Если после отправки появился другой план или версия, интерфейс требует новый предпросмотр и явную отправку.
- PWA-объявление становится видимым Student; Family читает актуальную аудиторию через API, но не получает отдельного уведомления.
- Telegram-получатели честно остаются в состоянии `queued` до подключения транспорта в Phase 8.

## Реализация

- API: `apps/pwa_api/classroom_delivery_routes.py`.
- Правила предпросмотра и фиксации: `models/pwa/classroom_delivery.py`.
- SQLite-запросы: `db_methods/pwa/classroom_delivery.py`.
- Runtime contracts: `vmshpwa/packages/contracts/src/classrooms.ts`.
- Staff client: `vmshpwa/packages/app-shell/src/classroom-client.ts`.
- Product component: `ClassroomDeliveryPanel` в `vmshpwa/packages/product/src/classroom-delivery.tsx`.
- Staff page: `vmshpwa/apps/staff/src/classroom-assignment-page.tsx`.

## Storybook

- `product-classrooms--delivery-preview`;
- `product-classrooms--delivery-changed-after-send`;
- `product-classrooms--delivery-partial-report`;
- `product-classrooms--delivery-retry-failed`;
- `pages-staff--classroom-delivery`.

Desktop-состояния предпросмотра, частичного результата и Staff page проверены вручную в Storybook. Ошибок браузерной консоли нет. Visual snapshots не обновлялись.

## Автоматические доказательства

- `uv run pytest -q pwa_tests/integration/test_phase7_classroom_delivery.py`: `4 passed`.
- Authenticated aiohttp case `test_admin_materializes_updates_and_confirms_classroom_layout`: `1 passed`.
- Ruff format/check для затронутого Python-кода: успешно.
- Frontend lint: успешно.
- Frontend typecheck: успешно.
- Unit Vitest: `62 files`, `449 tests passed`.
- Storybook browser tests и a11y gate: `42 files`, `204 tests passed`.
- Production build Student, Family и Staff: успешно; оба PWA собраны в `injectManifest` режиме.
- `git diff --check`: успешно.

## Следующий инкремент

Phase 8 должен обработать Telegram-очередь, записать фактические `sent|failed` результаты и реализовать повтор только неуспешных получателей. Текущий API не изображает Telegram-доставку до выполнения этого транспорта.
