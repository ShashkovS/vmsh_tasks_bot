# Phase 10 — Staff course statistics

Дата проверки: 2 августа 2026 года.

## Что работает

- `GET /staff/api/v1/statistics` отдаёт последний завершённый immutable
  `analytics_runs` snapshot по доступному Staff курсу и, опционально, группе.
- Admin видит доступные ему курсы целиком; teacher получает только строки из
  действующих `staff_scopes`. Чужой курс или группа возвращают `403`.
- API не отдаёт user IDs, фамилии и индивидуальные позиции. На занятие приходят
  только агрегаты и отсортированное обезличенное распределение числа решённых
  задач.
- `/staff/statistics` использует runtime-validated search params `course`,
  `group`, `lesson`, TanStack Query и strict Zod response contract.
- Страница показывает историю занятий, средние значения, состав доступного
  агрегата и violin без маркера отдельного школьника.
- E2E seed создаёт один готовый snapshot только в точной
  `db/vmshpwa_e2e.sqlite3`; повторный запуск идемпотентен.

## Реализация

- SQLite reads:
  [`db_methods/pwa/course_analytics.py`](../../db_methods/pwa/course_analytics.py).
- Pure aggregation:
  [`models/pwa/staff_statistics.py`](../../models/pwa/staff_statistics.py).
- Auth/scoping/API:
  [`apps/pwa_api/staff_statistics_routes.py`](../../apps/pwa_api/staff_statistics_routes.py).
- Runtime contract/client:
  [`staff-statistics.ts`](../../vmshpwa/packages/contracts/src/staff-statistics.ts),
  [`staff-statistics-client.ts`](../../vmshpwa/packages/app-shell/src/staff-statistics-client.ts).
- Route/page:
  [`statistics.tsx`](../../vmshpwa/apps/staff/src/routes/statistics.tsx),
  [`staff-statistics-page.tsx`](../../vmshpwa/apps/staff/src/staff-statistics-page.tsx).
- E2E fixture:
  [`seed_e2e_statistics.py`](../../vmshpwa/scripts/seed_e2e_statistics.py).

## Storybook и ручная проверка

- `Pages/Staff/Statistics--HistoricalCourse` — история курса, выбор группы и
  занятия, обезличенный violin.
- `Pages/Staff/Statistics--NoCompletedRun` — курс без завершённого расчёта.
- Источник:
  [`staff-statistics-page.stories.tsx`](../../vmshpwa/apps/staff/src/staff-statistics-page.stories.tsx).
- Owner snapshots не обновлялись. Desktop и mobile-light на ширине 390 px
  просмотрены вручную в agent Storybook. На узком экране сводка складывается в
  одну колонку, а плотная таблица прокручивается внутри своего контейнера и не
  создаёт горизонтальный scroll всей страницы.

## Автоматические доказательства

- Python focused domain/API/seed: `11 passed`.
- Python PWA full: `1533 passed, 5 skipped` (`-n8`).
- Frontend unit full: `108 files, 583 passed`.
- Storybook browser full: `49 files, 233 passed`; a11y остаётся error gate.
- ESLint, Stylelint, strict TypeScript и production build: pass.
- Production-build authentication E2E: `87 passed, 12 intentional skips`.
  Новый teacher-scoped сценарий прошёл в Chromium, WebKit и Firefox; он
  проверяет отсутствие недоступной группы и наличие анонимного графика.

## Граница этого инкремента

Это первый исторический срез Staff statistics, а не объявление всего модуля
завершённым. Он намеренно переиспользует уже рассчитанные Phase-9 metrics и не
создаёт второй движок рейтингов. Ещё не реализованы:

- live-счётчики сдано/проверено/ожидает;
- нагрузка и скорость проверки преподавателей;
- устная статистика и reach;
- операционные инциденты и выгрузки;
- production scheduler периодического `a53-compatible` расчёта.

Эти пункты остаются в Phase 10 и должны получить отдельные API/read model,
stories и browser proof только после появления соответствующих production
источников данных.
