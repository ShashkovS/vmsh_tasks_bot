# Phase 10: управление областями доступа преподавателей

Дата проверки: 2026-07-30.

## Проверяемый результат

- `GET /staff/api/v1/staff-access` возвращает администратору преподавателей,
  staff-аккаунты и текущие области курса/группы.
- `PUT /staff/api/v1/staff-members/{staffUserId}/scopes` заменяет полный набор
  областей преподавателя с optimistic-проверкой всех увиденных версий.
- Глобальные права admin не редактируются через `staff_scopes`; возможности
  teacher остаются фиксированными ролью, а редактор меняет только объекты, к
  которым эти возможности применимы.
- Удалённые области не стираются: прежняя строка получает `valid_to`,
  `revoked_by`, причину и новую версию. Новая область создаётся отдельной
  строкой.
- Изменение видно в `/staff/api/v1/auth/me` уже на следующем запросе с
  существующей сессией.
- Изменение grant/revoke и компактный `staff_scope.replaced` audit-event
  фиксируются одной SQLite-транзакцией. Исторические `staff_scopes` остаются
  детальным источником истины.

## Границы реализации

- Короткие SQLite-операции: `db_methods/pwa/staff_access.py`.
- Единственное чистое правило diff/дубликатов: `models/pwa/staff_access.py`.
- Валидация HTTP, русские сообщения и транзакционная координация:
  `apps/pwa_api/staff_access_routes.py`.
- Новых connection factories, repositories, service wrappers и миграций нет.

## Автоматические доказательства

- `pwa_tests/test_staff_access.py`: diff, дубликаты и запрет одновременно
  course-wide/group-specific области одного курса.
- `pwa_tests/integration/test_phase10_staff_access.py`: teacher `403`, admin
  directory, grant/revoke history, немедленное обновление principal, stale
  `409`, несуществующая цель `422` и неизменяемый глобальный admin.
- Focused Staff-access/audit aiohttp: **8 passed**; synthetic audit failure
  полностью откатывает grant/revoke.
- Полный gate: **578** frontend unit tests и **1525 passed, 5 skipped** Python
  tests; focused Storybook interaction/a11y — **2 passed**.
- `ruff check` и `ruff format --check` для затронутых Python-файлов: пройдено.
- Lint, strict TypeScript и production build всех трёх приложений: пройдены.

Frontend-редактор и browser E2E фиксируются отдельным инкрементом и отдельным
proof-файлом.
