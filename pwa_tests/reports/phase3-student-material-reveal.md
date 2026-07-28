# Phase 3F — deliberate Student hint/solution reveal

Дата: 2026-07-28

Revision: `fabdf93`

## Проверяемый результат

- canonical список задач сообщает для каждой конкретной задачи независимое
  состояние подсказки и решения: `unavailable`, `available` или `revealed`;
- Student не может прочитать опубликованную подсказку или решение через старый
  прямой GET: сервер возвращает `409 reveal_confirmation_required`;
- явное подтверждение выполняет строгий JSON POST к точной тройке
  `group_lesson + problem + hint|solution`;
- сервер перед записью повторно проверяет Student session, course enrollment,
  allowed group, текущую condition publication и текущую publication выбранного
  материала;
- reveal атомарно и неизменно записывается в существующую таблицу
  `hint_reveals` либо `solution_reveals`; повтор запроса возвращает исходный
  `revealedAt` и `firstReveal: false`;
- ответ содержит только один выбранный problem node без introduction и не
  раскрывает соседние задачи или другой вид материала;
- новая publication остаётся отдельной audit boundary благодаря ключу
  `(student_user_id, problem_id, publication_id)`; старые события не
  переписываются;
- Student UI сначала показывает принятое предупреждение, не отображает
  материал до успешного audit-запроса, умеет повторить запрос после сетевой
  ошибки и после reload открывает уже раскрытый материал без второго
  предупреждения;
- Family read boundary не менялся: родитель продолжает читать опубликованные
  материалы своего ребёнка без Student reveal event.

Новая миграция не потребовалась: immutable таблицы и DB-триггеры reveal были
созданы в `migrations/0041.pwa_content_lessons.sql`.

## Реализация

- exact publication/problem projection и атомарная запись:
  `db_methods/pwa/content.py`;
- Student HTTP boundary:
  `apps/pwa_api/content_routes.py` и `apps/pwa_api/course_routes.py`;
- strict Zod contracts/fixtures:
  `vmshpwa/packages/contracts/src/{content-api,courses}.ts`;
- same-origin transport:
  `vmshpwa/packages/content/src/content-client.ts`;
- production focused task:
  `vmshpwa/apps/student/src/student-task-detail-page.tsx`;
- transport-aware shared disclosure:
  `vmshpwa/packages/product/src/conscious-disclosure.tsx`;
- interaction proof:
  `Product/Reading--audited-reveal-recovery`;
- production browser path:
  `vmshpwa/e2e/content-publication.spec.ts`.

## Инварианты и отрицательные сценарии

- unknown/unpublished material и problem другого current revision не создают
  reveal row;
- чужой group scope получает `403` до поиска problem;
- лишнее поле JSON получает `422`;
- Student client отклоняет прямой hint/solution GET до сети;
- Family/Staff client не может вызвать Student reveal;
- несовпадение revision, material kind или source ordinal в ответе отклоняется
  runtime-схемой;
- при ошибке API child content остаётся невидимым.

## Результаты проверок

- focused real-aiohttp content API: **33 PASS**;
- focused contracts/client: **3 файла / 43 PASS**;
- `make pwa-test`: frontend unit **31 файл / 265 PASS**; полный Python PWA
  regression PASS (число test functions не изменилось: **1100 PASS, 3 skip**);
- `make pwa-lint`, `make pwa-typecheck`: PASS;
- `make pwa-storybook-test`: **36 файлов / 181 PASS**, a11y gate включён;
- targeted `Product/Reading`: **5 PASS**;
- `make pwa-e2e-content`: production builds и **3 PASS** в Chromium, Firefox и
  WebKit на настоящих aiohttp/SQLite, без MSW;
- Student `injectManifest`: PASS, **95 precache entries / 2275.42 KiB**;
- `git diff --check`: PASS.

Browser flow выполняет настоящий Staff upload → compile → matching → publish
для condition и hint, открывает opaque Student task, подтверждает подсказку,
проверяет `firstReveal: true`, перезагружает production-built PWA и доказывает,
что серверное состояние `revealed` отменяет повторное предупреждение. Затем
прежний condition replace/rollback сценарий остаётся зелёным.

## Намеренно открыто

- cold-offline Dexie cache и повторное чтение уже полученного материала без
  сети закрываются следующим gate Phase 3G;
- offline никогда не должен создавать новый reveal: нераскрытый материал без
  успешного server audit остаётся закрытым;
- визуальные snapshots не обновлялись; owner visual gate остаётся отдельным;
- discussion, submission attempts и review thread относятся к этапам 4–6.

Phase 3F закрывает онлайн-авторизацию и audit раскрытия подсказок/решений, но не
закрывает весь этап 3.
