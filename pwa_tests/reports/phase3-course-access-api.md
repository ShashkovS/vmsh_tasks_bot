# Phase 3A — Student course/access API

Дата: 28 июля 2026 года. Revision: `d70b0d9`.

## Результат

Первый исполняемый срез Phase 3 открыл два authenticated Student endpoint:

- `GET /student/api/v1/courses`;
- `GET /student/api/v1/courses/{courseId}/enrollment`.

Оба ответа используют ранее принятый Zod-контракт `CourseEnrollment`: один
active group на курс, один или несколько allowed groups, отдельный attendance
mode, course/group presentation tokens и optimistic versions.

## Авторитетность и границы

- Middleware перед каждым запросом заново валидирует сессию и строит authority
  из общей SQLite.
- Route проецирует уже проверенные `course_enrollments`; второго набора
  repository-запросов и N+1 внутри handler нет.
- `studentId` не принимается из query/body.
- Enrollment чужого либо неизвестного курса возвращает одинаковый `403`, не
  раскрывая существование курса.
- Неописанные query-параметры отклоняются с `422`.
- Nullable legacy `color_key` получает безопасный нейтральный presentation
  token; некорректные сохранённые tokens fail closed.
- Новая миграция не нужна: используются таблицы Phase 1 `courses`, расширенные
  `groups`, `course_enrollments` и `course_group_access`.

## Browser client

Публичный `@vmsh/app-shell` export `createStudentCourseClient`:

- фиксирует audience/API base валидированным Student runtime;
- проверяет list/detail ответы через общие Zod schemas;
- валидирует `courseId` до HTTP-запроса;
- использует cookies и `no-store`;
- один раз повторяет GET после штатного auth refresh;
- различает network, error-envelope и protocol failures;
- предоставляет principal-scoped TanStack Query hooks/keys.

Реализующие файлы:

- [`course_routes.py`](../../apps/pwa_api/course_routes.py);
- [`course-client.ts`](../../vmshpwa/packages/app-shell/src/course-client.ts);
- [`course-client.test.ts`](../../vmshpwa/packages/app-shell/src/course-client.test.ts);
- [`test_content_http_api.py`](../integration/test_content_http_api.py).

## Проверки

```text
Ruff affected Python
PASS

Prettier + ESLint affected TypeScript
PASS

strict TypeScript: app-shell + root
PASS

focused real aiohttp/SQLite course API
3 passed

full auth + content aiohttp regression
45 passed

app-shell + course contract Vitest regression
9 files, 90 passed

Student production Vite build + injectManifest service worker
PASS; 92 precache entries
```

## Что остаётся в Phase 3

Этот checkpoint не подменяет lesson/home read model. Следующий срез должен
добавить course-scoped список групповых занятий с publication/window summary,
после чего production Student «Сейчас» и «Задачи» смогут использовать реальные
course/group/lesson данные без фиктивных дат и progress. Затем остаются focused
task detail, hint/solution reveal audit и offline Dexie document cache.
