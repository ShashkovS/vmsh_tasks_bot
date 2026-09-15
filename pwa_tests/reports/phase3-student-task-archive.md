# Phase 3D — production Student «Задачи» и архив листков

Дата: 2026-07-28

Revision: `42ea05c`

## Проверяемый результат

- production `/student/tasks` больше не показывает prototype задачи и
  фиктивные результаты;
- курс, доступная группа и номер занятия являются валидированным TanStack URL
  state; URL не расширяет revalidated server authority;
- неизвестный курс или группа дают явное forbidden state, а отсутствие курсов
  и опубликованных листков — отдельные empty states;
- курсорный архив использует TanStack Query infinite query и серверный
  `nextCursor`, не копируя server state в локальный store;
- переключение группы означает только контекст чтения и не меняет active group;
  shared `CourseGroupSwitcher` получил отдельный help text для этого режима;
- карточка листка показывает только server-owned номер, дату, title, число задач
  и фактическую доступность подсказки/решения;
- выбор занятия сохраняется в URL, после чего «Открыть листок» передаёт точный
  `group_lesson` в существующий published-content route;
- long sheet рендерится из опубликованного `web_ast`; MSW и prototype adapter в
  production browser path не используются.

## Реализация

- production page: `vmshpwa/apps/student/src/student-tasks-page.tsx`;
- URL/context mapping: `vmshpwa/apps/student/src/student-tasks-view.ts`;
- file-based route: `vmshpwa/apps/student/src/routes/tasks.index.tsx`;
- cursor query: `vmshpwa/packages/app-shell/src/course-client.ts`;
- principal/course/group query key:
  `vmshpwa/packages/contracts/src/courses.ts`;
- shared reading-context copy:
  `vmshpwa/packages/product/src/course-context.tsx`;
- interaction story:
  `product-courses--allowed-group-reading-context`;
- production E2E: `vmshpwa/e2e/content-publication.spec.ts`.

## Результаты проверок

- focused contracts/client/home/tasks: **4 файла / 26 PASS**;
- `make pwa-test`: frontend unit **31 файл / 259 PASS**; Python PWA
  **1098 PASS, 3 skip**, одна legacy SymPy deprecation warning;
- `make pwa-storybook-test`: **36 файлов / 180 PASS** с browser-mode
  interaction/a11y gate;
- `make pwa-lint`, `make pwa-typecheck`: PASS;
- `make pwa-e2e-content`: production build трёх приложений и **3 PASS** в
  Chromium, WebKit и Firefox на настоящих aiohttp/SQLite;
- Student `injectManifest`: PASS, 96 precache entries;
- `git diff --check`: PASS.

Browser flow публикует условие Staff, входит как Student, проверяет реальный
«Сейчас», открывает `/student/tasks` с course/group context, выбирает точный
номер занятия, проверяет обновлённый URL и читает листок. Затем он публикует
вторую revision и откатывает к первой.

## Намеренно открыто

- листок пока является архивной единицей: canonical problem rows, собственные
  статусы задач и их submission/review projection появятся после публичной
  identity для legacy `problems`;
- фильтры task status/topic не изображают данные, которых ещё нет на сервере;
- hint/solution deliberate reveal audit, synonym projection и result state;
- Dexie document cache, cold-offline fallback и owner visual approval.

Phase 3D закрывает настоящий выбор course/group/lesson и чтение длинного листка,
но не весь этап 3.
