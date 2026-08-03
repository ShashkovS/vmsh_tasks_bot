# API, realtime-события и карта файлов

Статус: целевой contract map. Каждый endpoint появляется только в своём этапе. Все body/query/response/error payloads получают Zod schema и Python fixture.

## Общие HTTP-правила

- Base paths: `/student/api/v1`, `/family/api/v1`, `/staff/api/v1`.
- Успех возвращает предметный JSON. Ошибка — единый envelope: `error.code`, `error.message`, `error.details`, `requestId`.
- `401` означает отсутствующую/истёкшую сессию; `403` — authenticated principal без права; `409` — version/idempotency/lease conflict; `422` — schema/domain validation. `429` с `Retry-After` может выставить nginx для IP-level защиты либо auth service для account/login-level throttling; эти уровни дополняют друг друга.
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

Student login payload: `username`, `telegramToken`, optional `deviceLabel`;
`telegramToken` — password, заданный Student batch. Family/staff используют поле
`password`. Ответ не возвращает token, plaintext provisioning value или session
secret, только principal и policy dates. Все audience sessions имеют абсолютную
границу ближайшего 10 августа. Неуспешная попытка учитывается одновременно в
IP- и normalized-login buckets, не раскрывая существование account.

Реализующие файлы:
`apps/pwa_api/{auth_routes,auth_service,middleware,realtime_control,websocket_sessions}.py`,
`db_methods/pwa/auth.py`, `models/pwa/auth.py` и composition root
`apps/pwa_app.py`. Wire/API доказательство: real-aiohttp + migrated-SQLite suite
`pwa_tests/integration/test_auth_http_api.py`; чистые
security/session/realtime проверки —
`pwa_tests/{test_auth_service,test_auth_config,test_permissions,test_request_security,test_websocket_sessions,test_realtime_control}.py`.
WebSocket session binding, exact Origin до upgrade, periodic SQLite
revalidation и close при logout/revoke/logout-all реализованы в том же Phase-1
adapter. Refresh-only logout публикует close только по repository-verified
target; malformed/foreign refresh не создаёт realtime-команду.

## Student API

### Чтение — этап 3

- `GET /student/api/v1/courses`
- `GET /student/api/v1/courses/{courseId}/enrollment`
- `PATCH /student/api/v1/courses/{courseId}/enrollment/active-group`
- `PATCH /student/api/v1/courses/{courseId}/enrollment/attendance`
- `GET /student/api/v1/courses/{courseId}/home`
- `GET /student/api/v1/courses/{courseId}/lessons?group=&cursor=`
- `GET /student/api/v1/courses/{courseId}/lessons/{lessonPublicId}`
- `GET /student/api/v1/problems/{problemPublicId}`
- `POST /student/api/v1/problems/{problemPublicId}/hint-reveal`
- `POST /student/api/v1/problems/{problemPublicId}/solution-reveal`
- `GET /student/api/v1/banners/active`

Home read model содержит phase of week, active lesson, `submissionClosesAt`, отдельный nullable `solutionScheduledAt`/фактический publication state, attention items, unread counts, oral-window summary и banners, но не join secret.

Любая группа с действующим `course_group_access` даёт полный набор problem actions, а не read-only режим. Смена active group инвалидирует home/tasks только соответствующего курса и не скрывает собственную историю старой группы.

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
- `GET /student/api/v1/in-person-events/{eventPublicId}/classroom-assignment`
- `GET /student/api/v1/news`, `GET /student/api/v1/news/{postPublicId}`
- `GET /student/api/v1/courses/{courseId}/progress/summary`, `/lessons`, `/activity`, `/achievements`
- `GET/PUT /student/api/v1/notifications/preferences`, `POST/DELETE /student/api/v1/push-subscriptions`
- `GET/PUT /student/api/v1/courses/{courseId}/notifications/preferences` — course override поверх общих категорий
- `POST /student/api/v1/notification-events/{eventPublicId}/read` и аналогичный Family route — идемпотентный account-scoped acknowledgement после client visibility timer; client timestamp не становится `readAt`.

## Family API — этап 9, кроме auth

- `GET /family/api/v1/children`
- `GET /family/api/v1/children/{studentPublicId}/courses`
- `GET /family/api/v1/children/{studentPublicId}/courses/{courseId}/enrollment`
- `GET /family/api/v1/children/{studentPublicId}/courses/{courseId}/home`
- `GET /family/api/v1/children/{studentPublicId}/courses/{courseId}/lessons`
- `GET /family/api/v1/children/{studentPublicId}/problems/{problemPublicId}`
- `GET /family/api/v1/children/{studentPublicId}/courses/{courseId}/activity`
- `GET /family/api/v1/children/{studentPublicId}/courses/{courseId}/progress/*`
- `PATCH /family/api/v1/children/{studentPublicId}/courses/{courseId}/enrollment/active-group`
- `PATCH /family/api/v1/children/{studentPublicId}/courses/{courseId}/enrollment/attendance`
- `GET /family/api/v1/children/{studentPublicId}/in-person-events/{eventPublicId}/classroom-assignment`
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
- annotation manifests передаются только внутри atomic `POST .../complete`;
  отдельного изменяемого post-complete endpoint нет
- `PUT/DELETE /staff/api/v1/reviews/{reviewPublicId}/internal-reaction` — одна реакция, окно редактирования один час
- `POST /staff/api/v1/reviews/{reviewPublicId}/correct` — teacher/admin исправляет текущий verdict
- Owner-confirmed material-move core — teacher выбирает одно или несколько
  сообщений/фото, Student видит target history. Следующие два endpoint являются
  безопасным implementation default для preview, scoped admin и post-review
  correction; append-only invariant остаётся обязательным:
- `POST /staff/api/v1/submission-material/reassignment-preview` — проверяет
  выбранные `entry_text|attachment` items и целевую задачу без изменения
  данных; preview показывает target timeline, scope/ownership, уже завершённые
  reviews и то, что verdict не переносится
- `POST /staff/api/v1/submission-material/reassign` — teacher/admin применяет
  подтверждённую append-only correction; immutable files/review evidence и
  существующий verdict не перемещаются; повтор требует новый idempotency key,
  а повтор с тем же key/hash возвращает тот же batch
- `GET /staff/api/v1/review/student-reactions`
- `GET/POST /staff/api/v1/questions/*`

Phase 6B реализует первый ограниченный срез списка и lease API. `GET
/review/items` принимает только `problemGroup`, `sort=oldest|newest` и opaque
`cursor`. `claim` принимает строго `{"schemaVersion":1}`; `heartbeat` и
`release` — только `schemaVersion` и server-issued `claimToken`. Actor всегда
берётся из Staff cookie. Collection возвращает logical case только целиком:
если хотя бы одна актуальная synonym-ветка вне public course/group scope
teacher, кейс не попадает в список, а прямой claim получает `403`. Ответы не
содержат integer IDs; lock metadata показывает безопасное имя преподавателя,
тип `pwa|legacy`, expiry и принадлежность текущей сессии. Реализация:
`apps/pwa_api/review_routes.py`, `db_methods/pwa/reviews.py`,
`packages/contracts/src/review-queue.ts` и
`packages/app-shell/src/review-queue-client.ts`; executable proof —
[`phase6-review-queue-http.md`](../../../pwa_tests/reports/phase6-review-queue-http.md).

Phase 6C реализует базовую атомарную часть `complete`. Claim/heartbeat возвращают
`evidenceBranches`; mutation принимает `schemaVersion`, `claimToken`,
`idempotencyKey`, `verdict`, nullable `comment`, `confirmWithoutComment` и полный
массив branches с exact `queueId`/`leaseVersion`, `threadId`/`threadVersion` и
`entryId`/`entryVersion`. Browser не передаёт actor/student/internal IDs.
Если школьник дослал или изменил материал, server отвечает
`409 review_thread_changed` либо `review_evidence_unavailable`, не создавая
частичный verdict. Повтор того же key/payload возвращает исходную квитанцию, а
другой payload с тем же key отклоняется. Для verdict ниже `+.` отсутствие
comment требует `confirmWithoutComment=true`; `+.` и `+` считаются принятыми.
Phase 6D добавляет в этот же request `annotations[]`: exact evidence
`attachmentId`, `schemaVersion=1`, rotation и discriminated normalized marks
`pencil|eraser|text|arrow|rectangle|highlight`. Manifest входит в idempotency
digest и транзакцию review; post-complete update/delete отсутствуют. Реализация
и executable proofs:

- [`phase6-review-completion.md`](../../../pwa_tests/reports/phase6-review-completion.md);
- [`phase6-review-annotations.md`](../../../pwa_tests/reports/phase6-review-annotations.md).

Phase 6E добавляет nullable `internalReactionId` в атомарный complete и strict
`PUT/DELETE /staff/api/v1/reviews/{reviewPublicId}/internal-reaction` с
`expectedVersion`. Current state принадлежит исходному reviewer, меняется или
снимается только в течение часа и сопровождается append-only событиями;
Student/Family payload и owner invalidation эту скрытую пометку не содержат.
Реализация и proof:

- [`phase6-review-internal-reactions.md`](../../../pwa_tests/reports/phase6-review-internal-reactions.md).

### Content — этап 2

- `POST /staff/api/v1/content/uploads`
- `GET /staff/api/v1/content/uploads/{id}/diagnostics`
- `POST /staff/api/v1/content/revisions/{id}/compile`
- `GET/PUT /staff/api/v1/content/revisions/{id}/problem-matches` — разрешение позиционных расхождений задач
- `GET /staff/api/v1/content/revisions/{id}/previews/{web|telegram|print}`
- `GET/POST /staff/api/v1/content/revisions/{id}/assets`
- `PUT /staff/api/v1/group-lessons/{groupLessonId}/metadata-grid`
- `GET/PUT /staff/api/v1/group-lessons/{groupLessonId}/window` — отдельная версионируемая операция для `opensAt`, `submissionClosesAt`, hint/solution schedule; изменение cutoff требует confirmation/audit по `SCHEDULE-01`
- `POST /staff/api/v1/publications`, `POST /staff/api/v1/publications/{id}/rollback`
- `GET /staff/api/v1/publications?groupLesson=`
- `POST /staff/api/v1/problems/{problemId}/recheck-test-attempts`

### Oral, classroom planning, news, admin

- `/staff/api/v1/oral/windows`, `/oral/conversations`, `/oral/results`
- `GET/POST /staff/api/v1/courses`, `GET/PATCH /staff/api/v1/courses/{coursePublicId}`, `POST /staff/api/v1/courses/{coursePublicId}/archive`
- `GET/PUT /staff/api/v1/courses/{coursePublicId}/runtime-settings` — admin-only
  typed per-course replacement главных `_BotSettings`; ответ явно сообщает,
  что cached значения применятся после restart

Backend API этого пункта реализован в
[`admin_course_routes.py`](../../../apps/pwa_api/admin_course_routes.py): GET
возвращает code-owned defaults с version `0`, первый PUT материализует row, а
следующие PUT требуют matching ETag. Staff contract/UI и Telegram compatibility
read остаются отдельным инкрементом.
- `POST /staff/api/v1/imports/student-accounts/preview|apply` — Student batch с
  ФИО, nullable birthday/grade, login/password и collision suffix preview
- `POST /staff/api/v1/imports/family-accounts/preview|apply` — Family batch с
  name, login/password, emails и child logins
- `POST /staff/api/v1/imports/course-enrollments/preview|apply` — один course и
  `login + allowedGroups` на строку; active group выбирается по group order

Реализованный v1 account-batch contract использует `schemaVersion: 1` и не
возвращает credential. Preview принимает `rows`, возвращает по каждой строке
`ready|invalid`, `resolvedLogin`, стабильный diagnostic code и `previewHash`.
Apply принимает исходные `rows`, просмотренные `resolvedLogins` и тот же hash,
повторно валидирует данные и в одной SQLite transaction создаёт только готовые
строки. Ответ содержит public account/user IDs и per-row `created|skipped`, но
не password, token или email. Student и Family — два независимых действия;
course enrollment — третий batch: `login, course, allowed_groups`, preview
явно показывает active group, выбранную по `groups.sort_order`, и apply повторно
проверяет тот же порядок.
- `GET/POST /staff/api/v1/courses/{coursePublicId}/groups`, `PATCH /staff/api/v1/groups/{groupPublicId}`, `POST /staff/api/v1/groups/{groupPublicId}/archive`
- `GET/PUT /staff/api/v1/courses/{coursePublicId}/schedule-rules`, `GET/PUT /staff/api/v1/groups/{groupPublicId}/schedule-overrides`
- `POST /staff/api/v1/group-lessons/{groupLessonPublicId}/schedule-preview`, `POST /staff/api/v1/group-lessons/{groupLessonPublicId}/schedule-confirm`
- `GET/POST /staff/api/v1/telegram-bindings`, `PATCH /staff/api/v1/telegram-bindings/{bindingPublicId}`, `GET /staff/api/v1/groups/{groupPublicId}/telegram-bindings/effective`
- `GET /staff/api/v1/course-lessons/{courseLessonPublicId}/synonym-candidates`, `POST /staff/api/v1/problem-synonyms/impact-preview`, `POST /staff/api/v1/problem-synonyms/merge`, `POST /staff/api/v1/problem-synonyms/{synonymPublicId}/split`
- `GET/POST /staff/api/v1/in-person-events`, `GET/PATCH /staff/api/v1/in-person-events/{eventPublicId}`
- `GET /staff/api/v1/classrooms?search=&status=active|archived|all`
- `POST /staff/api/v1/classrooms`, `PATCH /staff/api/v1/classrooms/{classroomPublicId}`
- `POST /staff/api/v1/classrooms/{classroomPublicId}/archive`, `POST /staff/api/v1/classrooms/{classroomPublicId}/restore`
- `GET /staff/api/v1/classroom-layouts/effective?event=` — effective confirmed layout участвующих групп, optional materialized draft и source/base version
- `POST /staff/api/v1/classroom-layouts/materialize` — создаёт draft для выбранного `in_person_event` из последних подтверждённых конфигураций участвующих групп
- `PUT /staff/api/v1/classroom-layouts/{layoutPublicId}/rooms` — заменяет draft mappings `classroomPublicId + groupId`
- `POST /staff/api/v1/classroom-layouts/{layoutPublicId}/confirm`
- `GET /staff/api/v1/classroom-assignment-plans?event=` — confirmed/draft/stale plan, preview incidents, course/group `inPersonCount/assignedCount/color`, room aggregates и компактные student rows
- `POST /staff/api/v1/classroom-assignment-plans/recalculate`
- `PATCH /staff/api/v1/classroom-assignment-plans/{planPublicId}/assignments` — явный batch-save локально накопленных select/move; принимает одну или несколько строк и confirmation для cross-group changes
- `GET /staff/api/v1/classroom-assignment-plans/{planPublicId}/students/{studentPublicId}/history` — подтверждённые прошлые аудитории школьника
- `POST /staff/api/v1/classroom-assignment-plans/{planPublicId}/confirm`
- `POST /staff/api/v1/classroom-assignment-plans/{planPublicId}/delivery-preview` — только confirmed current version; возвращает число получателей, изменения после предыдущей рассылки, недоступные Telegram destinations и безопасный recipient preview
- `POST /staff/api/v1/classroom-assignment-plans/{planPublicId}/delivery-batches` — admin явно выбирает `pwa` и/или `telegram`, передаёт expected plan version, preview hash и idempotency key; draft/stale/изменившийся после preview plan получает conflict
- `GET /staff/api/v1/classroom-assignment-delivery-batches/{batchPublicId}` — агрегированные per-channel states/retries без токенов и chat IDs
- `POST /staff/api/v1/classroom-assignment-delivery-batches/{batchPublicId}/retry-failed` — implementation-default explicit admin retry только текущих failed recipient/channel pairs; принимает expected batch version и idempotency key
- Полноценные print/export endpoints относятся ко второй версии. V1 не создаёт compatibility export для `a11`–`a14`; narrow classroom delivery не является общим broadcast API.
- `/staff/api/v1/news/import-status`, `/news/posts`, `/news/posts/{id}/visibility`
- будущие `/staff/api/v1/broadcasts`, `/broadcasts/{id}/preview`, `/broadcasts/{id}/send` относятся ко второй фазе вместе с Markdown editor и не входят в initial v1 contract; Staff→Telegram channel publication также относится ко второй версии. Исключение v1 — строго типизированная персональная рассылка подтверждённых аудиторий через endpoints выше.
- `/staff/api/v1/users`, `/groups`, `/permissions`, `/imports`, `/statistics`, `/audit`

Teacher получает `403` на content/checker, broadcasts, Staff classroom catalog/layout/plan routes и audit. Он может менять активную группу доступного ученика внутри разрешённого курса, исправлять/перепроверять работу и читать разрешённую статистику. Остальные capabilities проверяются по course/group scopes, а не предполагаются по видимости navigation.

Все classroom mutations используют `If-Match`/`version`; stale version возвращает `409 VERSION_CONFLICT`. Нормализация имени выполняется сервером, duplicate возвращает `409 CLASSROOM_NAME_CONFLICT` вместе с существующим `publicId`. Layout confirm возвращает `409 CLASSROOM_LAYOUT_STALE`, если base больше не effective. Assignment confirm возвращает `409 CLASSROOM_ASSIGNMENTS_STALE` для устаревшего layout и `422` с отдельными кодами `CLASSROOM_STUDENT_UNASSIGNED`, `CLASSROOM_GROUP_MISMATCH` или `CLASSROOM_MIXED_GROUPS` для нарушенного плана.

Owner-confirmed delivery report допускает partial success и раскрываемые списки.
Delivery-batch response показывает `selected`, `eligible`, `suppressed`,
`queued`, `attempted`, `succeeded`, `failed` по каждому выбранному каналу и
итоговые `delivered_any`, `delivered_all`, `partial`. Раскрываемые списки
содержат только безопасные Student identity/display fields и per-channel state,
без Telegram chat ID/token. По implementation default «Повтор ошибок» —
отдельное явное admin action, которое создаёт новый attempt только для failed
channel-recipient pairs и не дублирует уже успешную доставку.

Assignment batch не вызывается на каждую смену select. Клиент передаёт полный набор локальных изменений, base plan version и для каждого перехода в другую группу того же курса явное `confirmGroupChange=true`; server применяет group history и assignments атомарно. Аудитория группы другого курса не является допустимым вариантом этой строки. Read payload содержит nullable `ageYears`, `grade`, `strength`, но не `birthday`; room summary содержит `studentCount`, nullable `averageAgeYears`, `averageGrade`, `averageStrength`. Каждый average исключает соответствующие `NULL` и округляется до одного знака. Fuzzy name search выполняется на клиенте по уже загруженным нескольким сотням строк и не требует отдельного endpoint.

Student/Family read model одинаков по смыслу и содержит только `eventPublicId`, исходные `courseId/groupId/groupLessonId`, `status: not_applicable | reassigning | assigned`, nullable `classroomName`, `confirmedAt` и nullable `lastAnnouncedAt`; internal IDs, layout draft, delivery destinations и другие школьники не попадают в payload. `not_applicable` означает online/отсутствие необходимости в очной комнате; очный школьник без действующего подтверждённого назначения получает `reassigning`. Скрытие используемой комнаты немедленно меняет `assigned` на `reassigning`. Confirm/update вызывает authoritative refetch, но notification появляется только после отдельного delivery batch.

## WebSocket protocol

Endpoint: `/{audience}/ws`. После authenticated handshake:

```json
{ "type": "connected", "protocolVersion": 1, "connectionId": "...", "heartbeatSeconds": 25 }
```

Это целевая расширенная форма. Реализованный Phase-1 transport пока отдаёт
минимальный совместимый payload `type`, `cursor`, `serverTime`, `audience`; при
наличии reconnect cursor первым событием всегда становится
`resync-required` с причиной `reconnect-full-refetch-required`.

Client всегда invalidates/refetches authoritative bootstrap queries после reconnect. Cursor можно использовать для диагностики и gaps внутри живого соединения, но не для отмены resync.

Server events:

- `invalidation`: `audience`, optional routing `ownerAccountId`, `courseId`, `groupId`, `studentUserId`, `keys[]`, `reason`, `entityVersion`, `requestId`. Phase-1 transport принимает broker `accountId` только вместе с audience, маршрутизирует по authenticated registry и не копирует target ID в browser event; более предметные owner mappings добавляют service layers соответствующих фаз.
- `notification`: продукт разрешает полные сведения о проверке, но payload всё равно адресуется конкретному account и не содержит credentials/media write URLs.
- `lease-changed`: staff group/queue key, не чужая работа целиком.
- `server-update`: новая frontend release/service-worker hint.
- `resync-required`: protocol/schema mismatch или обнаруженный gap.
- `classroom.assignment.changed`: owner-scoped invalidation с `audience`, `ownerAccountId`, `studentUserId`, `eventPublicId`, исходными `courseId/groupId`, новым публичным `status` и query keys. После confirm/change отдельные Student и Family sockets только refetch-ят read model; событие не создаёт push/in-app delivery.
- `classroom.assignment.announced`: создаётся только явным admin delivery batch для Student account. PWA-канал создаёт персональные in-app/push deliveries, Telegram-канал отправляет личное сообщение через существующего бота. Family event/delivery отсутствует. Payload ссылается на immutable plan/batch version и не содержит токен или chat ID.
- `submission.material.reassigned`: owner-scoped invalidation целевого Student и
  связанных Family accounts с source/target thread query keys, но без чужих
  материалов в event payload; Staff получает отдельную scope-filtered
  invalidation очереди. Authoritative timeline после refetch содержит
  provenance label.

Текущий Phase-1 transport использует изолированные subjects
`<runtimePrefix>.pwa_invalidate` и `<runtimePrefix>.pwa_session_control`.
Invalidation без audience остаётся общей, с audience — audience-scoped, а с
`audience + accountId` — owner-scoped. Control event имеет exact schema
`version=1`, `type=auth.close`, `scope=session|account` и канонический target;
лишние поля отвергаются. Целевая предметная декомпозиция по course/group events
может появиться позже, не меняя reconnect/full-refetch contract.

## Invalidation/query keys

Планируемые typed factories в `packages/contracts`:

- `courseKeys.list(audience, principal)`, `enrollmentKeys.detail(course, principal)`
- `homeKeys.course(audience, principal, course)`
- `lessonKeys.list(course, group, filters)`, `lessonKeys.detail(course, group, id, revision)`
- `problemKeys.detail(id, revision)`
- `threadKeys.byProblem(id)`, `reviewKeys.queue(filters)`, `reviewKeys.item(id)`
- `threadKeys.materialReassignmentPreview(student, sourceProblem, targetProblem, selectionHash)`
- `newsKeys.list(audience, course, group)`, `notificationKeys.preferences(course?)`
- `progressKeys.summary(student, course)`, `progressKeys.lesson(student, course, lesson)`
- `adminKeys.contentRevision(id)`, `adminKeys.publications(lesson, group)`
- `classroomKeys.catalog(filters)`, `classroomKeys.layout(event)`, `classroomKeys.plan(event)`, `classroomKeys.assignment(audience, student, event)`
- `classroomKeys.deliveryPreview(plan, version, channels)`, `classroomKeys.deliveryBatch(batch)`
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
  unit_of_work.py        # transaction boundary shared by PWA and touched Telegram paths
db_methods/pwa/
  auth.py
  content.py
  submissions.py
  reviews.py
  classrooms.py
  notifications.py
  progress.py
  connection.py          # lifecycle/busy policy from DB concurrency ADR
helpers/pwa/
  permissions.py
  idempotency.py
  storage.py
  media_conversion.py
  content_compiler.py
  classroom_assignment.py
  classroom_import.py
  delivery_worker.py
  analytics_worker.py
pwa_tests/
  fixtures/
  contracts/
  api/
  domain/
  integration/
```

Названия каталогов окончательно проверить против Python import conventions до фазы 1. Domain rule не должен зависеть от aiohttp request или React contract fixture. Суффикс `pwa` обозначает место новой реализации, но не отдельную бизнес-модель: Telegram adapter для затронутого write path вызывает те же domain services/unit of work, а не копирует invariant в handler.

## Планируемая карта frontend-файлов

Существующие route filenames сохраняются; `routeTree.gen.ts` генерируется:

```text
vmshpwa/packages/contracts/src/
  common.ts auth.ts courses.ts content.ts tasks.ts submissions.ts reviews.ts
  synonyms.ts in-person-events.ts classrooms.ts news.ts notifications.ts progress.ts staff.ts query-keys.ts
vmshpwa/packages/content/src/
  math-document.tsx katex.ts telegram-preview.tsx figure-viewer.tsx
vmshpwa/packages/offline/src/
  database.ts outbox.ts submission-outbox.ts cache-policy.ts migrations.ts
vmshpwa/packages/app-shell/src/
  auth-boundary.tsx websocket-provider.tsx offline-status.tsx update-flow.tsx
vmshpwa/apps/student/src/features/
  courses/ home/ tasks/ submissions/ news/ progress/ profile/
vmshpwa/apps/family/src/features/
  children/ courses/ lessons/ news/ progress/ profile/
vmshpwa/apps/staff/src/features/
  dashboard/ courses/ content/ synonyms/ review/ oral/ in-person-events/ classrooms/ news/ users/ statistics/ audit/
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

## Multi-course API и события

Student/Family получают course list, enrollment, active-group switch, attendance, course lessons и course progress. Staff получает CRUD/archive courses/groups, scopes, schedule inheritance/override/materialization, Telegram binding management, synonym candidate/merge/split/impact preview, in-person event composition/inherited plan и admin-only classroom delivery preview/send/status.

URL state использует validated `course`, `group`, `lesson`/`event`, `tab`. Query keys и draft keys включают course/group context. Owner-scoped invalidations допускают `audience`, `courseId`, `groupId`, `studentUserId`; отсутствие scope означает общий ресурс. События: `course.enrollment.changed`, `course.group-access.changed`, `group-lesson.publication.changed`, `problem-synonyms.changed`, `review.case.changed`, `course.progress.invalidated`, `notification.preference.changed`, `in-person-event.changed`, `classroom.assignment.changed`, `classroom.assignment.announced`.

Concrete endpoints and payload invariants: [`docs/courses-groups-and-lessons.md`](../../docs/courses-groups-and-lessons.md). Planned frontend files: `packages/product/src/{course-context,course-admin,synonym-context,in-person-event}.tsx`; route compositions — `apps/{student,family,staff}/src/pages.tsx`; contracts migrate to `packages/contracts` only in their vertical phase.
