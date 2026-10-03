# Phase 10 proof: рабочая сводка Staff

Дата проверки: 2 августа 2026 года.

## Что работает

- `GET /staff/api/v1/dashboard` требует Staff-сессию и capability `statistics.read`.
- Admin видит все текущие групповые занятия; teacher — только курсы и группы из
  действующих `staff_scopes`.
- Сводка использует существующие источники истины: логические кейсы письменной
  проверки, ожидающие ответа вопросы, независимые публикации
  condition/hint/solution, устные окна и admin-only ошибки рассылки аудиторий.
- Для каждой доступной группы выбирается последнее начавшееся занятие либо
  ближайшее предстоящее. Фаза выводится из фактических окон и публикаций по
  правилам `vmshpwa/docs/weekly-lifecycle.md`.
- Ответ содержит только агрегаты и групповые занятия. Student rows, тексты
  вопросов и материалы работ в dashboard response не попадают.
- `/staff/` использует этот API вместо прежних прототипных чисел. Карточки ведут
  в специализированные экраны проверки, вопросов, уроков, устного приёма и
  аудиторий.

## Реализация

- механические SQLite-чтения:
  `db_methods/pwa/staff_dashboard.py`;
- чистая temporal/scope projection:
  `models/pwa/staff_dashboard.py`;
- Staff HTTP route:
  `apps/pwa_api/staff_dashboard_routes.py`;
- runtime Zod-контракт и клиент:
  `vmshpwa/packages/contracts/src/staff-dashboard.ts`,
  `vmshpwa/packages/app-shell/src/staff-dashboard-client.ts`;
- production page:
  `vmshpwa/apps/staff/src/staff-dashboard-page.tsx`;
- Storybook:
  `Pages/Staff/Dashboard--CurrentWeek`,
  `Pages/Staff/Dashboard--TeacherScoped`,
  `Pages/Staff/Dashboard--NoCurrentLessons`.

## Проверки

- domain + real aiohttp/SQLite integration: `9 passed`;
- contract/client unit: `3 passed`;
- полный Python PWA: `1542 passed / 5 intentional skips` в 8 workers;
- полный frontend unit: `110 files / 586 passed`; весь ESLint/Stylelint — pass;
- полный Storybook interaction/a11y: `50 files / 236 passed`;
- TypeScript, scoped ESLint, Ruff и production build: pass;
- production-build authentication E2E: `90 passed / 12 intentional skips`;
  новый Staff dashboard сценарий прошёл в Chromium, WebKit и Firefox;
- desktop и mobile-light 390 px просмотрены вручную; horizontal overflow не
  обнаружен, visual snapshots не обновлялись.

## Граница этого инкремента

Это оперативная сводка, а не новая аналитическая система. Она не создаёт
дополнительный read-model или background scheduler и не дублирует правила
очереди проверки. Полный workload по преподавателям, delivery/reach по всем
типам рассылок и Google cutover остаются открытыми пунктами Phase 10.
