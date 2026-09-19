# Phase 3E — canonical Student task list and real work states

Дата: 2026-07-28

Revisions: `1aeb78d`, `8448a8b`

## Проверяемый результат

- каждая legacy-задача получила отдельный неизменяемый `problems.public_id`;
  числовой SQLite ID больше не попадает в browser URL или контракт;
- `GET /student/api/v1/courses/{courseId}/lessons/{groupLessonId}/problems`
  возвращает задачи именно текущей опубликованной condition revision;
- сервер повторно проверяет Student session, course enrollment и allowed group;
  URL не расширяет права школьника;
- canonical order и точный `sourceOrdinal` происходят из `problem_revisions`, а
  title/type/answer type — из той же опубликованной revision;
- `not-started`, `sent`, `checking`, `accepted`, `needs-work`, `rejected`
  вычисляются из настоящих `written_tasks_queue`, discussions, results и
  verdicts; pending queue намеренно перекрывает более старый verdict;
- действующая synonym-group объединяет work state логически, не перенося
  submission/result IDs; legacy `problems.synonyms` остаётся ограниченным
  compatibility fallback внутри того же course lesson;
- production `/student/tasks` показывает shared `TaskListItem` с реальными
  статусом/вердиктом, а focused route использует непрозрачный `problem-*` ID и
  повторно разрешает его через авторизованный canonical list;
- ни API, ни UI не придумывают unread, дедлайн, попытки или submission actions,
  которых ещё нет в реализованном read model.

## Реализация

- public identity migration:
  `migrations/0044.pwa_problem_identity.sql` и rollback;
- Student task projection: `db_methods/pwa/content.py`;
- audience/course/group HTTP boundary: `apps/pwa_api/course_routes.py`;
- runtime contract and fixture:
  `vmshpwa/packages/contracts/src/courses.ts` и
  `vmshpwa/packages/contracts/fixtures/courses/student-problems.v1.json`;
- same-origin client/query:
  `vmshpwa/packages/app-shell/src/course-client.ts`;
- production list/mapping/detail:
  `vmshpwa/apps/student/src/student-tasks-page.tsx`,
  `vmshpwa/apps/student/src/student-tasks-view.ts`,
  `vmshpwa/apps/student/src/student-task-detail-page.tsx` и
  `vmshpwa/apps/student/src/routes/tasks.$taskId.tsx`;
- browser path: `vmshpwa/e2e/content-publication.spec.ts`.

## Результаты проверок

- exact migration up/down/up, schema artifacts и deterministic seed identity:
  PASS; focused seed/migration/schema suite **106 PASS**;
- focused real-aiohttp content API suite: **33 PASS**;
- focused contracts/client/page mapping: **3 файла / 27 PASS**;
- `make pwa-test`: frontend unit **31 файл / 263 PASS**; Python PWA
  **1100 PASS, 3 skip**, одна известная legacy SymPy deprecation warning;
- `make pwa-lint`, `make pwa-typecheck`: PASS;
- `make pwa-e2e-content`: production build и **3 PASS** в Chromium, Firefox и
  WebKit на настоящих aiohttp/SQLite, без MSW;
- Student `injectManifest`: PASS, **95 precache entries / 2268.19 KiB**;
- `git diff --check`: PASS.

Browser flow выполняет настоящий Staff upload → compile → matching → metadata
→ publish, открывает Student archive, выбирает занятие, проверяет server-owned
`Не начата`, переходит по `/student/tasks/problem-<opaque-id>` и читает ровно
эту задачу. Затем прежний revision/update/rollback сценарий также остаётся
зелёным во всех трёх браузерах.

## Намеренно открыто

- detail пока реализует condition reading; deliberate reveal подсказки/решения
  и его audit закрываются следующим gate;
- попытки тестов, drafts/outbox, письменные фото и discussion timeline относятся
  к последующим вертикальным этапам;
- cold-offline Dexie cache, unread feedback и attention-order не симулируются;
- synonym merge/split admin workflow ещё не реализован: read model уже уважает
  подтверждённую действующую связь и сохраняет физические ветки раздельно;
- visual snapshots не обновлялись: shared Product-компонент не менялся.

Phase 3E закрывает публичную identity, canonical task list/status и focused
condition URL, но не закрывает весь этап 3.
