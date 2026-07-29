# Phase 9: связанные дети и контекст курсов Family

Дата проверки: 2026-07-29.

## Проверяемый результат

- `/family/children` показывает детей из revalidated Family principal, а не из
  prototype-данных.
- `/family/children/:childId` загружает enrollment’ы только явно связанного
  ребёнка и показывает отдельные курс, активную группу и online/очный режим.
- Неизвестный или несвязанный `childId` получает одинаковый `403`; UI не
  отправляет запрос для профиля, отсутствующего в principal.
- Query key содержит Family account и student public ID, поэтому данные детей
  не делят один cache slot.
- Student-cookie с `Path=/student` не аутентифицирует `/family` endpoint.

## Граница реализации

Новых таблиц, SQL-запросов и repository/factory abstractions нет. Authentication
middleware уже перечитывает `family_student_links` и course enrollments на
каждом запросе; endpoint только проецирует эту проверенную authority.

Смена группы/режима, текущее занятие и прогресс входят в следующие вертикальные
срезы Phase 9.

## Автоматические доказательства

```text
pwa_tests/integration/test_phase9_family_courses.py
  2 passed

contracts + app-shell unit
  6 passed

Ruff / ESLint / strict TypeScript
  pass

Family production build
  pass; injectManifest service worker generated
```

Snapshots не создавались и не обновлялись.

## Файлы

- `apps/pwa_api/family_course_routes.py`;
- `vmshpwa/packages/contracts/src/family-courses.ts`;
- `vmshpwa/packages/app-shell/src/family-course-client.ts`;
- `vmshpwa/apps/family/src/family-children-page.tsx`;
- `pwa_tests/integration/test_phase9_family_courses.py`.
