# Phase 2 content HTTP/API proof

Дата последней проверки: 28 июля 2026 года.

Это proof ограниченного HTTP vertical slice этапа 2, а не отметка о завершении
всей фазы. Авторитетные требования: `vmshpwa/dev/development-plan/06-phase-2-content.md`
и раздел Content в `vmshpwa/dev/development-plan/03-api-events-and-files.md`.
Проверенная backend revision этого среза — `1aad776`; связанный frontend
checkpoint — `866e3fe`.

## Реализованная граница

- Staff admin загружает один LaTeX source через bounded multipart endpoint. Для
  каждой пары `group_lesson + material kind` сохраняется одна активная source
  lineage: повторная загрузка прежнего файла создаёт revision `N + 1`, а другое
  имя или кодировка возвращают явный `409 source_lineage_conflict`.
- Lifecycle revision проходит `uploaded -> compiling -> ready|invalid` с точным
  `If-Match`. Компиляция сначала получает непрозрачный двухминутный lease:
  активный claim нельзя перехватить, зависший claim атомарно reclaim-ится после
  cutoff, а отменённый HTTP handler немедленно освобождает claim для retry.
  Неожиданная ошибка compiler или недоверенный результат неправильной формы
  переводит revision в terminal
  `invalid` с redacted `compiler.internal_error`; текст исключения не попадает
  в HTTP response.
- Успешная компиляция одной SQLite-транзакцией сохраняет ровно
  `web_ast` (`WebContentDocument v1`), compatibility `web_html` и
  `telegram_html`, после чего переводит revision в `ready`. Fault-test доказывает,
  что конфликт второго derivative откатывает уже вставленный первый derivative
  и не делает revision готовой.
- Pure compiler принимает только валидированные typed asset descriptors
  (public ID, SHA-256, safe URL, media type, dimensions); conflicting URL и
  missing TikZ SVG остаются diagnostics, а не silently broken figure.
- Staff preview отдаёт только typed web document либо Telegram-rich HTML
  конкретной revision. Diagnostics и missing asset references доступны отдельно.
- Condition, hint и solution имеют независимые published/scheduled slots.
  Немедленная публикация атомарно supersede-ит прежнюю published revision и
  только тот pending schedule того же material slot, чьи public ID и version
  явно прислал клиент. Поэтому новый schedule, возникший после чтения формы, не
  будет молча отменён, а старое расписание не активируется после publish/rollback.
- Scheduled publication можно явно отменить отдельным действием с `If-Match`.
  Rollback публикует выбранную готовую историческую revision, не переписывая
  source, derivatives или старые publication rows, и атомарно отменяет точно
  ожидаемый pending schedule. Published материал можно отдельно скрыть.
- Встроенный scheduler выбирает только `scheduled_at <= now`, одной
  `BEGIN IMMEDIATE` транзакцией supersede-ит schedule и текущую публикацию и
  создаёт новую published row. Два worker не могут активировать один schedule
  дважды. Терминальные строки сохраняют actor/time, а SQLite triggers запрещают
  прямой обход version/state и изменение source identity.
- После publish/schedule/rollback/cancel/hide и scheduler activation отправляется
  general `pwa_invalidate` для конкретного group lesson/material. Ошибка NATS
  после commit только логируется: HTTP не предлагает клиенту опасный повтор
  уже выполненной мутации.
- Staff history endpoint восстанавливает после reload список revisions, current
  published/scheduled state и bounded history (до 250 revisions/publications на
  material kind) для всех трёх видов. Response содержит авторитетный
  `businessTimezone` конкретного group lesson.
- `ready` означает только успешную компиляцию. Publish, schedule и rollback
  дополнительно fail-closed проверяют, что число resolved
  `content_problem_matches` точно соответствует canonical problem identities,
  а каждый не-omitted match имеет отдельный reviewed `problem_revisions` record.
- Solution нельзя publish или schedule без существующего versioned lesson
  window с `submission_closes_at`. Создание окна, изменение обычного расписания
  и отдельное подтверждённое изменение cutoff имеют optimistic `If-Match` и
  append-only actor/request/before/after audit в `lesson_window_changes`.
- Wall-clock время приходит как `YYYY-MM-DDTHH:mm` вместе с IANA timezone,
  который сервер сверяет с group lesson. Серверный `ZoneInfo` переводит время в
  UTC и отклоняет DST gap/fold; timezone браузера не используется.
- Student и Family читают только текущий `published` `WebContentDocument v1`
  точного вида материала. Scheduled/hidden state, canonical compiler AST,
  compatibility HTML, Telegram HTML, diagnostics и соседние answer/hint/solution
  ветки не входят в audience response.
- Все операции используют public course/group/group-lesson identities,
  авторитетный scope из SQLite и реальный `linked_user_id` Staff actor. Teacher
  получает `403`; Family child ownership и Student group access проверяются
  перед чтением.

## HTTP endpoints

```text
POST /staff/api/v1/content/uploads
GET  /staff/api/v1/content/uploads/{revisionId}/diagnostics
POST /staff/api/v1/content/revisions/{revisionId}/compile
GET  /staff/api/v1/content/revisions/{revisionId}/previews/{web|telegram}
GET  /staff/api/v1/group-lessons/{groupLessonId}/lesson-window
POST /staff/api/v1/group-lessons/{groupLessonId}/lesson-window
PATCH /staff/api/v1/group-lessons/{groupLessonId}/lesson-window/schedule
PATCH /staff/api/v1/group-lessons/{groupLessonId}/lesson-window/submission-cutoff
GET  /staff/api/v1/publications?groupLesson={groupLessonPublicId}
POST /staff/api/v1/publications
POST /staff/api/v1/publications/{publicationId}/rollback
POST /staff/api/v1/publications/{publicationId}/cancel
POST /staff/api/v1/publications/{publicationId}/hide

GET /student/api/v1/group-lessons/{groupLessonPublicId}/content/{condition|hint|solution}
GET /family/api/v1/children/{studentPublicId}/group-lessons/{groupLessonPublicId}/content/{condition|hint|solution}
```

Ошибки используют общий `PwaApiError` envelope и request/correlation ID.
Проверены устойчивые `401`, `403`, `404`, `409`, `413` и `422`; SQLite internal
IDs не входят в wire payload.

## Проверки

```text
uv run ruff check \
  apps/pwa_api/content_routes.py apps/pwa_app.py db_methods/pwa/content.py \
  pwa_tests/integration/test_content_http_api.py \
  pwa_tests/integration/test_content_repository.py
PASS

uv run pytest -q \
  pwa_tests/integration/test_phase2_content_concurrency_migration.py \
  pwa_tests/integration/test_phase2_content_schema_migrations.py \
  pwa_tests/integration/test_content_repository.py \
  pwa_tests/integration/test_content_http_api.py \
  pwa_tests/test_pwa_content_scheduler.py
41 passed (migration up/down/up, source/upload races, lease/cancellation, two-worker
activation, exact scheduled-slot rollback, hide and post-commit transport fault)

uv run pytest -q \
  pwa_tests/integration/test_auth_http_api.py pwa_tests/test_pwa_app.py \
  pwa_tests/test_request_security.py pwa_tests/test_permissions.py
176 passed

uv run pytest -q -n0 \
  pwa_tests/domain/test_content.py \
  pwa_tests/domain/test_content_compiler.py \
  pwa_tests/integration/test_content_repository.py \
  pwa_tests/integration/test_content_http_api.py \
  pwa_tests/integration/test_phase2_content_schema_migrations.py \
  pwa_tests/integration/test_phase2_content_concurrency_migration.py \
  pwa_tests/test_pwa_content_scheduler.py \
  pwa_tests/test_schema_inventory.py
127 passed

git diff --check -- <increment paths>
PASS
```

Дополнительный review-fix gate 28 июля:

```text
ruff: PASS
pytest domain/content HTTP/migrations/scheduler: 62 passed
migration lifecycle: 5 passed
0043 lesson-window audit: exact up/down/up PASS
```

Полный объединённый checkpoint этого worktree:

```text
make pwa-lint             PASS
make pwa-typecheck        PASS
make pwa-test             218 TypeScript + 1028 Python PASS; 3 skip; 1 warning
make pwa-storybook-test   167 PASS
make pwa-build            PASS
make pwa-schema-check     192 product objects PASS
make pwa-e2e-auth         60/60 PASS (Chromium, WebKit, Firefox)
```

Новые aiohttp tests используют настоящий `web.Application`, auth middleware и
отдельную migrated/seeded SQLite. MSW, Telegram, Google, S3 и production
credentials не используются.

## Оставшиеся gates

- Phase 2 пока интегрирует task page по явному public `groupLessonId`.
  Авторитетный `problemPublicId` отсутствует в legacy `problems` и в текущей
  additive schema; Phase 3 должен добавить public problem identity и task-list
  read model. Временный integer/composite problem ID намеренно не введён.
- Asset upload/resolution, bulk lesson upload, problem-matching/metadata mutation
  API и metadata grid ещё не входят в этот HTTP increment. Publication уже
  нельзя обойти без соответствующих repository records; Staff mutation flow
  добавляется отдельным вертикальным инкрементом.
- Персональные `hint_reveals`/`solution_reveals` и осознанное раскрытие в
  Student/Family API отложены до Phase 3. Пока published hint/solution — общий
  read model для имеющих доступ к группе.
- Staff publication history ограничена 250 строками каждого вида на material
  kind. Cursor pagination более старой истории явно отложена до Phase 3.
- Source file HTTP limit зафиксирован в `512 KiB`; pure compiler имеет отдельные
  более широкие structural limits. Повышение request limit требует отдельного
  corpus/DoS review.
- Frontend route integration уже зафиксирован в
  [`phase2-content-frontend.md`](phase2-content-frontend.md). Production-build
  content E2E и visual approval выполняются отдельным инкрементом; зелёный
  auth E2E 60/60 не подменяет отсутствующий content flow. Telegram/Google
  adapters не запускаются этим API.
