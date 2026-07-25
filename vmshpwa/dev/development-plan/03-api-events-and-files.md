# API, realtime-события и карта файлов

Статус: целевой contract map. Каждый endpoint появляется только в своём этапе. Все body/query/response/error payloads получают Zod schema и Python fixture.

## Общие HTTP-правила

- Base paths: `/student/api/v1`, `/family/api/v1`, `/staff/api/v1`.
- Успех возвращает предметный JSON. Ошибка — единый envelope: `error.code`, `error.message`, `error.details`, `requestId`.
- `401` означает отсутствующую/истёкшую сессию; `403` — authenticated principal без права; `409` — version/idempotency/lease conflict; `422` — schema/domain validation; `429` выставляет nginx с `Retry-After`.
- Mutation, которую browser/outbox может повторить, требует `Idempotency-Key`. Изменение mutable admin resource требует `If-Match`/`version`.
- Client timestamp не заменяет server timestamp. API принимает `clientCreatedAt`, сервер добавляет `receivedAt` и оценку clock skew.
- List endpoints используют cursor pagination; offset допустим только для маленьких справочников.
- Media upload идёт через aiohttp с streaming limits. Browser никогда не получает S3 write credentials.

## Auth API — этап 1

Для каждого audience доступны одинаковые по смыслу routes с разными cookie paths:

- `POST /{audience}/api/v1/auth/login`
- `POST /{audience}/api/v1/auth/refresh`
- `POST /{audience}/api/v1/auth/logout`
- `GET /{audience}/api/v1/auth/me`
- `GET /{audience}/api/v1/auth/sessions`
- `DELETE /{audience}/api/v1/auth/sessions/{sessionPublicId}`
- `POST /{audience}/api/v1/auth/logout-all`

Student login payload: `username`, `telegramToken`, optional `deviceLabel`. Username создаётся import-ом из транслитерации фамилии и дня рождения, а коллизия разрешается до активации account. Family/staff payload names используют `password`. Ответ не возвращает token/session secret, только principal и policy dates. Все audience sessions имеют абсолютную границу ближайшего 10 августа.

## Student API

### Чтение — этап 3

- `GET /student/api/v1/home`
- `GET /student/api/v1/lessons?group=&cursor=`
- `GET /student/api/v1/lessons/{lessonPublicId}`
- `GET /student/api/v1/problems/{problemPublicId}`
- `POST /student/api/v1/problems/{problemPublicId}/hint-reveal`
- `POST /student/api/v1/problems/{problemPublicId}/solution-reveal`
- `GET /student/api/v1/groups/available`
- `PUT /student/api/v1/profile/group` с confirmation token/version
- `PUT /student/api/v1/profile/attendance-mode`
- `GET /student/api/v1/banners/active`

Home read model содержит phase of week, active lesson, attention items, unread counts, oral-window summary и banners, но не join secret.

Любая группа из `allowed_groups` даёт полный набор problem actions, а не read-only режим. Смена active group немедленно инвалидирует home/tasks, но не скрывает историю старой группы.

### Test — этап 4

- `POST /student/api/v1/problems/{problemPublicId}/test-attempts`
- `GET /student/api/v1/problems/{problemPublicId}/test-attempts?cursor=`

Ответ mutation содержит normalized display answer, `checkStatus`, nullable verdict, attempts used/remaining, result version и thread invalidation key. `invalid_format` не расходует попытку. `pending_configuration` означает, что ответ принят и будет проверен admin-командой после настройки checker; после правильного ответа endpoint остаётся доступен.

### Written/thread — этапы 5/6

- `GET /student/api/v1/problems/{problemPublicId}/thread`
- `POST /student/api/v1/problems/{problemPublicId}/thread/entries` — создаёт draft логической text/photo отправки
- `POST /student/api/v1/thread-entries/{entryPublicId}/attachments` — повторяемая streaming upload отдельного файла
- `POST /student/api/v1/thread-entries/{entryPublicId}/submit` — атомарно публикует entry после загрузки всех выбранных файлов
- `PATCH /student/api/v1/thread-entries/{entryPublicId}` — меняет text до первого review lock с confirmation/version
- `DELETE /student/api/v1/thread-entries/{entryPublicId}` — удаляет незапроверенную отправку с confirmation/version
- `PATCH /student/api/v1/thread-entries/{entryPublicId}/attachments/order`
- `DELETE /student/api/v1/thread-entries/{entryPublicId}/attachments/{attachmentPublicId}` только до lock
- `PUT /student/api/v1/reviews/{reviewPublicId}/reaction`, `DELETE .../reaction` — одна реакция, изменение в течение часа
- `GET /student/api/v1/attachments/{attachmentPublicId}/annotations`

### Questions, oral, news, progress

- `POST /student/api/v1/questions`, `GET /student/api/v1/questions`, `GET/POST /student/api/v1/questions/{id}/entries`
- `GET /student/api/v1/oral/windows/current`, `POST /student/api/v1/oral/windows/{id}/join-details`
- `GET /student/api/v1/classroom-assignment?lesson=`
- `GET /student/api/v1/news`, `GET /student/api/v1/news/{postPublicId}`
- `GET /student/api/v1/progress/summary`, `/progress/lessons`, `/progress/activity`, `/progress/achievements`
- `GET/PUT /student/api/v1/notifications/preferences`, `POST/DELETE /student/api/v1/push-subscriptions`

## Family API — этап 9, кроме auth

- `GET /family/api/v1/children`
- `GET /family/api/v1/children/{studentPublicId}/home`
- `GET /family/api/v1/children/{studentPublicId}/lessons`
- `GET /family/api/v1/children/{studentPublicId}/problems/{problemPublicId}`
- `GET /family/api/v1/children/{studentPublicId}/activity`
- `GET /family/api/v1/children/{studentPublicId}/progress/*`
- `PUT /family/api/v1/children/{studentPublicId}/group`
- `PUT /family/api/v1/children/{studentPublicId}/attendance-mode`
- `GET /family/api/v1/children/{studentPublicId}/classroom-assignment?lesson=`
- news и notification routes с family base.

Family endpoints никогда не принимают произвольный `student_id`: server сначала проверяет `family_student_links`. Отдельного self-check endpoint нет. Family видит student-visible thread, AI feedback и реакции ребёнка, но не внутреннюю teacher reaction и не групповое сравнение.

## Staff API

### Dashboard и review — этап 6

- `GET /staff/api/v1/dashboard/week`
- `GET /staff/api/v1/review/problem-groups`
- `GET /staff/api/v1/review/items?problemGroup=&sort=&cursor=`
- `POST /staff/api/v1/review/items/{queuePublicId}/claim`
- `POST /staff/api/v1/review/items/{queuePublicId}/heartbeat`
- `POST /staff/api/v1/review/items/{queuePublicId}/release`
- `POST /staff/api/v1/review/items/{queuePublicId}/complete`
- `POST /staff/api/v1/reviews/{reviewPublicId}/annotations/{attachmentPublicId}` — immutable после complete
- `PUT/DELETE /staff/api/v1/reviews/{reviewPublicId}/internal-reaction` — одна реакция, окно редактирования один час
- `POST /staff/api/v1/reviews/{reviewPublicId}/correct` — teacher/admin исправляет текущий verdict
- `GET /staff/api/v1/review/student-reactions`
- `GET/POST /staff/api/v1/questions/*`

`complete` принимает claim token, expected queue version, expected thread version, evidence boundary, verdict, optional comment, optional single internal reaction и annotations manifest. Если школьник успел дослать материал, server возвращает `409 THREAD_CHANGED`, чтобы teacher увидел новую фотографию и завершил проверку уже по актуальному evidence. Для verdict ниже «Зачтено» отсутствие comment не запрещено API, но Staff требует дополнительного подтверждения.

### Content — этап 2

- `POST /staff/api/v1/content/uploads`
- `GET /staff/api/v1/content/uploads/{id}/diagnostics`
- `POST /staff/api/v1/content/revisions/{id}/compile`
- `GET/PUT /staff/api/v1/content/revisions/{id}/problem-matches` — разрешение позиционных расхождений задач
- `GET /staff/api/v1/content/revisions/{id}/previews/{web|telegram|print}`
- `GET/POST /staff/api/v1/content/revisions/{id}/assets`
- `PUT /staff/api/v1/lessons/{lessonId}/metadata-grid`
- `POST /staff/api/v1/publications`, `POST /staff/api/v1/publications/{id}/rollback`
- `GET /staff/api/v1/publications?lesson=&group=`
- `POST /staff/api/v1/problems/{problemId}/recheck-test-attempts`

### Oral, classroom planning, news, admin

- `/staff/api/v1/oral/windows`, `/oral/conversations`, `/oral/results`
- `GET /staff/api/v1/classrooms?search=&status=active|archived|all`
- `POST /staff/api/v1/classrooms`, `PATCH /staff/api/v1/classrooms/{classroomPublicId}`
- `POST /staff/api/v1/classrooms/{classroomPublicId}/archive`, `POST /staff/api/v1/classrooms/{classroomPublicId}/restore`
- `GET /staff/api/v1/classroom-layouts/effective?lesson=` — effective confirmed layout, optional materialized draft и source/base version
- `POST /staff/api/v1/classroom-layouts/materialize` — создаёт draft для выбранного lesson из effective base
- `PUT /staff/api/v1/classroom-layouts/{layoutPublicId}/rooms` — заменяет draft mappings `classroomPublicId + groupId`
- `POST /staff/api/v1/classroom-layouts/{layoutPublicId}/confirm`
- `GET /staff/api/v1/classroom-assignment-plans?lesson=` — confirmed/draft/stale plan, preview incidents, group `inPersonCount/assignedCount/color`, room aggregates и компактные student rows
- `POST /staff/api/v1/classroom-assignment-plans/recalculate`
- `PATCH /staff/api/v1/classroom-assignment-plans/{planPublicId}/assignments` — явный batch-save локально накопленных select/move; принимает одну или несколько строк и confirmation для cross-group changes
- `GET /staff/api/v1/classroom-assignment-plans/{planPublicId}/students/{studentPublicId}/history` — подтверждённые прошлые аудитории школьника
- `POST /staff/api/v1/classroom-assignment-plans/{planPublicId}/confirm`; print/export endpoints относятся ко второй версии
- `/staff/api/v1/news/import-status`, `/news/posts`, `/news/posts/{id}/visibility`
- будущие `/staff/api/v1/broadcasts`, `/broadcasts/{id}/preview`, `/broadcasts/{id}/send` относятся ко второй фазе вместе с Markdown editor и не входят в initial v1 contract; Staff→Telegram publication также относится ко второй версии
- `/staff/api/v1/users`, `/groups`, `/permissions`, `/imports`, `/statistics`, `/audit`

Teacher получает `403` на content/checker, broadcasts, Staff classroom catalog/layout/plan routes и audit. Он может менять уровень доступного ученика, исправлять/перепроверять работу и читать общую статистику кружка. Остальные capabilities проверяются по role/group permissions, а не предполагаются по видимости navigation.

Все classroom mutations используют `If-Match`/`version`; stale version возвращает `409 VERSION_CONFLICT`. Нормализация имени выполняется сервером, duplicate возвращает `409 CLASSROOM_NAME_CONFLICT` вместе с существующим `publicId`. Layout confirm возвращает `409 CLASSROOM_LAYOUT_STALE`, если base больше не effective. Assignment confirm возвращает `409 CLASSROOM_ASSIGNMENTS_STALE` для устаревшего layout и `422` с отдельными кодами `CLASSROOM_STUDENT_UNASSIGNED`, `CLASSROOM_GROUP_MISMATCH` или `CLASSROOM_MIXED_GROUPS` для нарушенного плана.

Assignment batch не вызывается на каждую смену select. Клиент передаёт полный набор локальных изменений, base plan version и для каждого cross-group move явное `confirmGroupChange=true`; server применяет group history и assignments атомарно. Read payload содержит nullable `ageYears`, `grade`, `strength`, но не `birthday`; room summary содержит `studentCount`, nullable `averageAgeYears`, `averageGrade`, `averageStrength`. Каждый average исключает соответствующие `NULL` и округляется до одного знака. Fuzzy name search выполняется на клиенте по уже загруженным нескольким сотням строк и не требует отдельного endpoint.

Student/Family read model одинаков по смыслу и содержит только `lessonPublicId`, `status: not_applicable | reassigning | assigned`, nullable `classroomName` и nullable `publishedAt`; internal IDs, layout draft и другие школьники не попадают в payload. `not_applicable` означает online/отсутствие необходимости в очной комнате; очный школьник без действующего опубликованного назначения получает `reassigning`. Скрытие используемой комнаты немедленно меняет `assigned` на `reassigning`.

## WebSocket protocol

Endpoint: `/{audience}/ws`. После authenticated handshake:

```json
{ "type": "connected", "protocolVersion": 1, "connectionId": "...", "heartbeatSeconds": 25 }
```

Client всегда invalidates/refetches authoritative bootstrap queries после reconnect. Cursor можно использовать для диагностики и gaps внутри живого соединения, но не для отмены resync.

Server events:

- `invalidation`: `audience`, optional `ownerAccountId`, `keys[]`, `reason`, `entityVersion`, `requestId`.
- `notification`: продукт разрешает полные сведения о проверке, но payload всё равно адресуется конкретному account и не содержит credentials/media write URLs.
- `lease-changed`: staff group/queue key, не чужая работа целиком.
- `server-update`: новая frontend release/service-worker hint.
- `resync-required`: protocol/schema mismatch или обнаруженный gap.
- `classroom.assignment.changed`: owner-scoped invalidation с `audience`, `ownerAccountId`, `lessonPublicId`, новым публичным `status` и query keys. Для школьника выпускается Student event, для каждого связанного Family account — отдельная Family invalidation; Student может создать push/in-app, Family только обновляет API/WS state.

NATS subject: `<runtimePrefix>.pwa.<audience>.<event>`. Payload обязан иметь `audience`; owner-targeted event фильтруется по authenticated principal до отправки socket. Broad lesson publication публикуется в три явных audience subjects.

## Invalidation/query keys

Планируемые typed factories в `packages/contracts`:

- `homeKeys.audience(audience, principal)`
- `lessonKeys.list(group, filters)`, `lessonKeys.detail(id, revision)`
- `problemKeys.detail(id, revision)`
- `threadKeys.byProblem(id)`, `reviewKeys.queue(filters)`, `reviewKeys.item(id)`
- `newsKeys.list(audience, group)`, `notificationKeys.preferences()`
- `progressKeys.summary(student)`, `progressKeys.lesson(student, lesson)`
- `adminKeys.contentRevision(id)`, `adminKeys.publications(lesson, group)`
- `classroomKeys.catalog(filters)`, `classroomKeys.layout(lesson)`, `classroomKeys.plan(lesson)`, `classroomKeys.assignment(audience, student, lesson)`
- `classroomKeys.studentHistory(plan, student)`

Raw query-key arrays в product code запрещаются после появления factory.

## Планируемая карта backend-файлов

`apps/pwa_app.py` остаётся app factory/composition root. Новые routes не превращают его в монолит:

```text
apps/pwa_api/
  middleware.py          # auth, request-id, errors, CSP/API headers
  auth_routes.py
  student_routes.py
  family_routes.py
  staff_routes.py
  classroom_routes.py
  realtime.py
  serialization.py
  dependencies.py        # repositories/storage/NATS adapters
models/pwa/
  auth.py
  content.py
  submissions.py
  reviews.py
  classrooms.py
  notifications.py
  progress.py
db_methods/pwa/
  auth.py
  content.py
  submissions.py
  reviews.py
  classrooms.py
  notifications.py
  progress.py
helpers/pwa/
  permissions.py
  idempotency.py
  storage.py
  media_conversion.py
  content_compiler.py
  classroom_assignment.py
  classroom_import.py
  delivery_worker.py
pwa_tests/
  fixtures/
  contracts/
  api/
  domain/
  integration/
```

Названия каталогов окончательно проверить против Python import conventions до фазы 1. Domain rule не должен зависеть от aiohttp request или React contract fixture.

## Планируемая карта frontend-файлов

Существующие route filenames сохраняются; `routeTree.gen.ts` генерируется:

```text
vmshpwa/packages/contracts/src/
  common.ts auth.ts content.ts tasks.ts submissions.ts reviews.ts
  classrooms.ts news.ts notifications.ts progress.ts staff.ts query-keys.ts
vmshpwa/packages/content/src/
  math-document.tsx katex.ts telegram-preview.tsx figure-viewer.tsx
vmshpwa/packages/offline/src/
  database.ts outbox.ts submission-outbox.ts cache-policy.ts migrations.ts
vmshpwa/packages/app-shell/src/
  auth-boundary.tsx websocket-provider.tsx offline-status.tsx update-flow.tsx
vmshpwa/apps/student/src/features/
  home/ tasks/ submissions/ news/ progress/ profile/
vmshpwa/apps/family/src/features/
  children/ lessons/ news/ progress/ profile/
vmshpwa/apps/staff/src/features/
  dashboard/ content/ review/ oral/ classrooms/ news/ users/ statistics/ audit/
vmshpwa/packages/test-utils/src/
  fixtures/ msw/ storybook/ builders/
vmshpwa/e2e/
  auth.spec.ts content-publication.spec.ts student-reading.spec.ts
  test-submission.spec.ts written-submission.spec.ts review.spec.ts
  oral.spec.ts classrooms.spec.ts news-push.spec.ts family-progress.spec.ts permissions.spec.ts
```

`packages/ui` остаётся domain-free. Product components с `Problem`, `Submission`, `Review` размещаются в feature или новом согласованном package, но не протаскивают app/domain imports в UI foundation.

## Contract fixtures

Canonical JSON fixtures размещаются в `vmshpwa/packages/contracts/fixtures/<domain>/`. Python tests читают те же файлы, TypeScript tests валидируют Zod-схемой. Минимум для каждой schema:

- `valid-minimal.json`, `valid-complete.json`;
- `invalid-missing-required.json`, `invalid-enum.json`;
- `legacy-compatible.json`, если есть legacy adapter;
- explicit version в fixture metadata.

Из fixtures исключаются реальные фамилии, chat IDs, tokens, cookie и production URLs.
