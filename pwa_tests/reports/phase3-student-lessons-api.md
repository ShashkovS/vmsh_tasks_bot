# Phase 3B — Student lesson read-model proof

Дата: 2026-07-28
Revision: `66f30c0`

## Проверяемый результат

- `GET /student/api/v1/courses/{courseId}/lessons` возвращает ограниченную
  страницу конкретной активной/доступной группы в обратном порядке номеров;
- `GET /student/api/v1/courses/{courseId}/lessons/{groupLessonId}` читает один
  конкретный `group_lesson`, сохраняя provenance курса и группы;
- активная группа используется по умолчанию, другую группу можно выбрать только
  из revalidated `allowed_groups`; недоступная группа и чужой course context
  возвращают `403`;
- список строится одним SQLite statement и не выполняет запрос на каждый урок;
- урок появляется только при текущей публикации condition с валидным `web_ast`;
  scheduled/draft/hidden condition не раскрывают сам урок;
- hint и solution отражают только фактическую публикацию, а не наличие скрытой
  ревизии;
- `submissionClosesAt` и `solutionScheduledAt` остаются отдельными полями
  materialized lesson window;
- ответ проверяется общими Zod schemas и versioned fixture; browser client
  отклоняет опасные ID/cursor до сети и использует principal/course/group query
  keys.

## Реализация

- HTTP boundary: `apps/pwa_api/course_routes.py`;
- bounded SQLite projection: `db_methods/pwa/content.py`;
- Zod contract и query keys: `vmshpwa/packages/contracts/src/courses.ts`;
- versioned fixture:
  `vmshpwa/packages/contracts/fixtures/courses/student-lessons.v1.json`;
- browser transport/hooks: `vmshpwa/packages/app-shell/src/course-client.ts`;
- real aiohttp/SQLite tests:
  `pwa_tests/integration/test_content_http_api.py`.

## Результаты проверок

- полный `pwa_tests/integration/test_content_http_api.py`: **32 PASS**;
- focused contracts + browser client: **2 файла / 16 PASS**;
- TypeScript strict typecheck packages `contracts` и `app-shell`: PASS;
- targeted ESLint, Ruff и Prettier: PASS;
- `git diff --check`: PASS.

В Python HTTP suite используется настоящий aiohttp application и временная
мигрированная SQLite. Telegram, Google, MSW и production credentials не
используются.

## Намеренно открыто

- `home` projection с server-owned текущим уроком/фазой недели;
- подключение production страниц Student «Сейчас» и «Задачи»;
- problem detail, synonym/result projection и deliberate reveal events;
- Dexie cache/offline fallback и browser E2E в трёх движках.

Поэтому этот proof закрывает только Phase 3B lesson navigation boundary, а не
весь этап 3.
