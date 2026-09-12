# Phase 8: настройки push по курсам

## Проверяемый результат

- Student получает девять категорий для каждого активного курса.
- Пока override отсутствует, `pushEnabled` наследуется из общей настройки.
- Student может включить/выключить push для одной категории одного курса и
  вернуть её к общей настройке.
- Настройка недоступного курса возвращает `404`; URL не расширяет область
  доступа сессии.
- Web Push использует course override только если событие содержит `courseId`.
  Остальные события продолжают использовать общую настройку.
- In-app visibility, quiet hours и timezone остаются общими и не дублируются в
  таблице курса.

## Автоматические доказательства

- `pwa_tests/integration/test_phase8_course_notification_preferences.py`
- `pwa_tests/integration/test_phase8_push_delivery.py`
- `vmshpwa/packages/contracts/src/notifications.test.ts`
- `vmshpwa/packages/app-shell/src/notification-client.test.ts`
- Storybook: `Product/Courses--course-notification-overrides`

## Миграция

- `migrations/0069.pwa_course_notification_preferences.sql`
- `migrations/0069.pwa_course_notification_preferences.rollback.sql`
