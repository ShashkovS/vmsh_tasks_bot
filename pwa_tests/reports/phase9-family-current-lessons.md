# Phase 9: текущие занятия ребёнка в Family

Дата проверки: 2026-07-29.

## Проверяемый результат

- `/family/api/v1/children/:studentId/home` возвращает последнее опубликованное
  занятие активной группы отдельно для каждого курса связанного ребёнка.
- Family видит номер, название и размер листка и может открыть тот же
  опубликованный документ в read-only режиме.
- Если опубликованного browser-ready условия нет, курс остаётся на странице с
  явным состоянием «Новое занятие пока не опубликовано».
- Не связанный с аккаунтом student ID получает `403` до чтения учебных данных.

## Простая граница данных

`db_methods/pwa/family.py` содержит одну короткую функцию с одним прямым SQL.
Она проверяет опубликованное condition, ready revision и живую `web_ast`
производную. В Family-аккаунте ожидается несколько курсов, поэтому handler
выполняет этот понятный запрос по одному разу на enrollment внутри одной
read-операции; отдельный агрегирующий слой и cache table не создаются.

## Автоматические доказательства

```text
Family aiohttp/SQLite integration
  3 passed

contracts + app-shell unit
  8 passed

Ruff / ESLint / strict TypeScript
  pass

Family production build
  pass; injectManifest service worker generated
```

Snapshots не создавались и не обновлялись.

## Файлы

- `db_methods/pwa/family.py`;
- `apps/pwa_api/family_course_routes.py`;
- `vmshpwa/packages/contracts/src/family-courses.ts`;
- `vmshpwa/packages/app-shell/src/family-course-client.ts`;
- `vmshpwa/apps/family/src/family-children-page.tsx`;
- `pwa_tests/integration/test_phase9_family_courses.py`.
