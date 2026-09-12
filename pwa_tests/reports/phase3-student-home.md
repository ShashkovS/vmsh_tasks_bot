# Phase 3C — production Student «Сейчас»

Дата: 2026-07-28

Revision: `77927e0`

## Проверяемый результат

- `GET /student/api/v1/home` возвращает по одному course-owned состоянию для
  каждого revalidated enrollment авторизованного школьника;
- для каждого курса выбирается последнее активное занятие active group с
  фактически опубликованным web-condition; скрытое условие сразу превращает
  состояние курса в `no_lesson`;
- несколько курсов читаются одним ограниченным SQLite statement с placeholder-
  scope predicates и `row_number()` внутри SQL, без цикла запросов по курсам;
- сервер отдельно вычисляет `published | solving | hints | checking |
  solutions`, не связывая момент закрытия сдачи с публикацией решения;
- общий Zod-контракт проверяет, что текущий урок принадлежит course enrollment и
  его active group, а course IDs в одном home response не дублируются;
- production route `/student/` использует реальный same-origin API и не
  подставляет фиктивные даты, прогресс или статус;
- loading, network/offline, forbidden, error, empty-course и published-course
  состояния имеют явное отображение;
- кнопка курса открывает конкретный опубликованный `group_lesson`, сохраняя
  точный provenance группы в валидированном URL state.

## Реализация

- phase policy: `models/pwa/content.py`;
- bounded home projection: `db_methods/pwa/content.py`;
- authenticated HTTP boundary: `apps/pwa_api/course_routes.py`;
- Zod contract и fixture:
  `vmshpwa/packages/contracts/src/courses.ts`,
  `vmshpwa/packages/contracts/fixtures/courses/student-home.v1.json`;
- browser transport и query hook:
  `vmshpwa/packages/app-shell/src/course-client.ts`;
- production page:
  `vmshpwa/apps/student/src/student-home-page.tsx`;
- production-build E2E:
  `vmshpwa/e2e/content-publication.spec.ts`.

## Результаты проверок

- domain content policy: **68 PASS**;
- полный real aiohttp/SQLite content HTTP файл: **32 PASS**;
- focused contracts, browser client и Student mapping: **3 файла / 22 PASS**;
- strict TypeScript для contracts/app-shell/Student, targeted ESLint, Ruff и
  Prettier: PASS;
- Student production build и `injectManifest`: PASS, 93 precache entries;
- `make pwa-e2e-content`: **3 PASS** в Chromium, WebKit и Firefox после
  production build трёх приложений, на настоящих aiohttp/SQLite без MSW;
- `git diff --check`: PASS.

Первый E2E-прогон обнаружил ошибку только в проверке: название курса было
видимым текстом `CardTitle`, но тест ошибочно требовал семантический heading.
Locator исправлен на точный пользовательский текст; destructive retry получает
уникальный synthetic source, поэтому повтор не скрывает первичную ошибку
checksum-конфликтом `409`.

## Намеренно открыто

- production `/student/tasks`: course/group selector, пагинация и canonical
  task list;
- problem detail, synonym/result projection и deliberate reveal events;
- Dexie document cache, cold-offline fallback и quota/identity isolation;
- отдельный offline/deep-link browser proof и owner visual approval.

Поэтому Phase 3C закрывает server-owned home projection и реальную страницу
«Сейчас», но не весь этап 3.
