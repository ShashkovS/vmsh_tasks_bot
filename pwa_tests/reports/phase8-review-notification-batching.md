# Phase 8: completed-review notification batching

Дата проверки: 2026-07-29.

## Реализованная граница

- Завершённая письменная проверка создаёт `review_completed` только для активного Student account владельца работы.
- Проверки, завершённые в пределах 30 минут от первой, дополняют одно событие и не создают отдельные push-доставки.
- В payload сохраняются уникальные `reviewIds`, `problemIds` и итоговый `count`; исходные review/submission/result записи не меняются.
- Повтор идемпотентного завершения review не увеличивает счётчик.
- Если первый результат уже прочитан, новая проверка внутри открытого окна снова делает пакет непрочитанным.
- Ровно на границе 30 минут начинается новый пакет.
- Student получает owner-scoped invalidation для тредов и `notification-events`; Family не получает individual review event.
- Русский текст остаётся в HTTP/push/frontend-слое, а SQLite-модуль содержит только короткие прямые запросы.

## Автоматические проверки

- `pwa_tests/integration/test_phase8_review_notifications.py`: три сценария агрегации, границы окна и audience/status scope.
- `pwa_tests/integration/test_review_queue_http_api.py::test_complete_review_is_atomic_and_idempotent_over_http`: реальное завершение review создаёт одно Student event, replay не создаёт второе.
- `pwa_tests/integration/test_phase8_push_delivery.py::test_review_batch_push_uses_the_aggregated_count`: push использует агрегированный счётчик.
- `vmshpwa/apps/student/src/student-notifications-page.test.tsx`: Student UI показывает число проверенных задач в пакете.
- Связанный backend-набор: 21 passed.
- Student notification unit-набор: 3 passed.
- Ruff, ESLint, Stylelint и полный TypeScript typecheck: passed.
- Полный frontend unit-набор: 77 files, 489 passed.
- Полный backend PWA-набор после regression fixes: 1375 passed, 3 skipped.
- Production build Student/Family/Staff и оба `injectManifest` service worker: passed.

## Не входит в этот инкремент

- Family weekly digest после окончания всей проверки.
- Course-scoped overrides настроек уведомлений.
- Полный Staff delivery diagnostics экран.
