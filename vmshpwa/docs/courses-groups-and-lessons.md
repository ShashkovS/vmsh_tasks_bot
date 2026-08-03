# Курсы, независимые группы, занятия и синонимы задач

Статус: принятое целевое решение от 26 июля 2026 года. Первый course/access и
lesson/content persistence + authenticated content vertical уже реализованы
additive migrations `0039`–`0043` и revisions `1aad776`/`866e3fe`; Telegram
bindings, очные события и production backfill остаются целевой моделью
последующих этапов. Прототипы интерфейса живут в `packages/product` и Storybook.

## Иерархия и границы владения

Основная иерархия — `сезон → курс → группа → групповое занятие`.

- Сезон задаёт календарную и организационную границу.
- Курс — крупный учебный контекст: предмет, программа, собственная статистика, достижения и настройки уведомлений.
- Группа — независимый поток внутри курса. У неё свои расписание, публикации, Telegram-настройки и список участников.
- `course_lesson` объединяет занятия групп одного курса только по одинаковому номеру.
- `group_lesson` владеет исходниками LaTeX, публикациями, подсказками, решениями, дедлайнами и окнами сдачи. Эти данные не переиспользуются между группами автоматически.

Группы разных курсов не связываются номером занятия. Группа может пропустить номер, не создавая пустой `group_lesson`.

## Целевые таблицы

### Курсы и группы

`courses`:

- `id`, `public_id`, `season_id`;
- `code`, `name`, `subject_code`;
- `status = draft | active | archived`, `sort_order`, `accent_key`;
- `created_at`, `updated_at`, `created_by`, `updated_by`, `version`.

`course_runtime_settings`:

- `course_id` PK/FK, `schema_version`, `values_json`;
- `updated_at`, `updated_by`, `version`.

`values_json` принимает только описанные Python-моделью ключи, перенесённые из
legacy `_BotSettings`; неизвестный key блокирует preview. Настройки читаются
per-course и могут кешироваться до рестарта backend. `save_sol_mode` отсутствует:
content и submissions всегда сохраняются в S3. Отдельной таблицы редактируемых
UI-текстов в v1 нет; тексты hardcoded до v2 i18n.

Существующая `groups` расширяется полями:

- `public_id`, `course_id`, `status`, `color_key`;
- `created_at`, `updated_at`, `version`.

Legacy `group_id` сохраняется. Название и короткий код группы уникальны внутри курса; совпадения между курсами допустимы.
В переходной миграции `course_id` и audit timestamps остаются nullable для
legacy-строк, а `public_id` получает детерминированный `legacy-...`; Phase 11
закрывает nullability после production-size backfill. Composite key
`(course_id, group_id)` является FK-границей для course-owned записей.

`course_enrollments`:

- `id`, `public_id`, `student_user_id`, `course_id`;
- `active_group_id` — ровно одна активная группа этого курса;
- `attendance_mode = online | in_person`;
- `status = active | paused | archived`, audit timestamps, `version`.

`course_group_access` хранит интервалы доступа: `enrollment_id`, технический
ownership-key `course_id`, `group_id`, `valid_from`, `valid_to`, `granted_by`,
`revoked_by`, `reason`, `version`. Composite FK одновременно связывает строку
с курсом enrollment и курсом группы. После отзыва ученик не получает новые
материалы группы, но видит собственные старые работы и результаты.

`course_enrollment_events` хранит историю смены активной группы, режима и
состояния курса; технический `course_id` обеспечивает те же composite FK для
старой/новой группы. Existing `user_changes_log` остаётся legacy-аудитом до
миграции и сверки.

`staff_scopes` задаёт `staff_user_id`, `course_id`, optional `group_id`,
`role = teacher | admin`, временные границы и audit. Scope без `group_id`
покрывает весь курс. Legacy admin остаётся глобальным bypass; сохранённая роль
сама по себе не повышает teacher до admin. Отсутствие scope даёт `403`, а не
только скрытую навигацию.

### Занятия и расписание

`course_lessons`:

- `id`, `public_id`, `course_id`, `lesson_number`, optional `title`;
- audit timestamps, `version`;
- unique `(course_id, lesson_number)`.

`group_lessons`:

- `id`, `public_id`, `course_lesson_id`, технический `course_id`, `group_id`;
- `cycle_anchor_date` (transitional schema name) означает локальную дату
  публикации условия; `business_timezone` задаёт зону вычисления schedule;
- `status`, audit timestamps и optimistic `version`;
- unique `(course_lesson_id, group_id)`.

Sources/revisions, exact windows и publications вынесены соответственно в
`content_sources`, `lesson_windows` и `lesson_publications`, поэтому condition,
hint и solution не становятся mutable columns занятия.

`course_schedule_rules` задаёт отдельную versioned rule для каждого поля
`opens_at`, `hint_scheduled_at`, `submission_closes_at` и
`solution_scheduled_at`: integer day offset, local wall time и IANA timezone.
`group_schedule_overrides` для конкретной группы и поля имеет режим `inherit |
override | disabled`, обязательную ссылку на базовую course rule и explicit
value только для `override`; cutoff отключить нельзя. Если базовая rule была
заменена после создания draft override, confirm завершается version conflict и
требует нового impact preview. Materialization создаёт
точные UTC timestamps в `lesson_windows` и immutable per-field provenance в
`lesson_window_schedule_sources`. Изменение шаблона не двигает существующие
занятия: Staff сначала получает impact preview, затем выполняет отдельное
подтверждённое действие.

Основной anchor шаблона курса — время публикации условия. Группа наследует
course rules, но может переопределить отдельные окна. Уже материализованные
timestamps конкретного занятия не пересчитываются молча после правки шаблона.

Phase-2A/2C schema/domain/repository/HTTP boundary реализован в
[`0041.pwa_content_lessons.sql`](../../migrations/0041.pwa_content_lessons.sql),
[`0042.pwa_content_concurrency.sql`](../../migrations/0042.pwa_content_concurrency.sql),
[`0043.pwa_lesson_window_audit.sql`](../../migrations/0043.pwa_lesson_window_audit.sql),
[`models/pwa/content.py`](../../models/pwa/content.py) и
[`db_methods/pwa/content.py`](../../db_methods/pwa/content.py); compiler, HTTP/UI
и audience frontend связаны в revisions `1aad776`/`866e3fe`. Historical
backfill, HTTP asset resolution, matching/metadata mutation, stored PDF, bulk
upload и production content E2E ещё не входят в этот статус.

Условие, подсказка и решение публикуются, планируются, откатываются и диагностируются независимо для каждого `group_lesson`.

## Синонимы задач

Синонимы разрешены только внутри одного `course_lesson`. Совпадение нормализованного названия создаёт кандидата, но связь подтверждает admin. Тип задачи, answer type и checker могут различаться и не блокируют объединение.

`problem_synonym_groups`:

- `id`, `public_id`, `course_lesson_id`, `status`;
- `created_by`, `created_at`, `updated_at`, `version`.

`problem_synonym_members` — версионируемая история:

- `id`, `synonym_group_id`, `problem_id`;
- `valid_from`, `valid_to`, `added_by`, optional `removed_by`, `reason`, `version`.

В одной группе одного занятия допускается не более одного активного экземпляра synonym-group.

### Инвариант хранения

Submission, попытка, фотография, сообщение, result и verdict всегда остаются привязанными к исходному `problem_id`. Merge/split меняет только логическую проекцию и запускает её пересчёт; IDs и содержимое исходных записей не переписываются.

Ученик открывает одну общую хронологию без фильтра по веткам. Каждый блок явно показывает исходные курс, группу и задачу. Общий статус вычисляется по всем текущим членам synonym-group.

Если несколько веток ожидают проверки, очередь создаёт один логический review case и показывает все посылки. Verdict и новый ответ записываются в задачу последней включённой посылки. Review хранит immutable snapshot всех просмотренных `submission_id`. После split verdict остаётся у этой конкретной задачи, а статусы остальных веток снова вычисляются только по их собственным данным. Rate limits и попытки остаются per-problem.

## Статистика по курсам

Сила 0–10, прогресс, streak и достижения считаются отдельно для каждого курса.

Для одного занятия:

1. Результат synonym-group прикладывается к каждому её экземпляру в доступных групповых листках.
2. Внутри одного листка synonym-group учитывается один раз.
3. Успешность вычисляется отдельно для каждой доступной группы.
4. Группой занятия считается группа с лучшим взвешенным результатом по действующей методике `_external_pipelines/a53_calc_rating_new.py`.
5. При равенстве используется стабильный `groups.sort_order`; числовой результат не меняется.

Student и Family никогда не видят место, процентиль, self marker или словесное сравнение с группой. Aggregate distribution допустим только в авторизованном Staff-контексте.

## Telegram

`telegram_bindings`:

- `id`, `public_id`;
- `owner_type = course | group`, `owner_id`;
- `purpose = news_source | materials_target`;
- `chat_id`, optional `message_thread_id`, `status`;
- audit timestamps, `version`.

Источники новостей курса и доступных групп складываются. Групповой `materials_target` заменяет course default; при отсутствии групповой цели наследуется цель курса. Telegram adapter остаётся параллельным каналом, но unit/E2E используют fixtures и не обращаются к Telegram.

## Очные события и аудитории

`in_person_events` хранит `id`, `public_id`, `season_id`, `name`, `starts_at`, `ends_at`, `status`, audit и `version`. `in_person_event_group_lessons` связывает событие с выбранными `group_lesson`.

Одно событие может объединять группы разных курсов и разные номера занятий. В одной аудитории всё ещё находится только одна группа. Новый draft плана полностью наследует последнюю подтверждённую конфигурацию каждой участвующей группы — комнаты и назначения школьников — после чего admin корректирует изменения.

Режим `online | in_person` хранится per `course_enrollment`. Отдельного workflow коллизий между курсами нет: организаторы не планируют конфликтующие группы, а школьник при необходимости выбирает очный режим только в одном курсе. Staff может показать неблокирующее предупреждение.

В плане аудиторий школьник представлен участием конкретного курса и `group_lesson`. Ручной выбор комнаты другой группы того же курса может после подтверждения изменить `active_group_id` этого enrollment. Комнаты групп другого курса не являются допустимыми вариантами той же строки.

Confirm плана и его рассылка — разные действия. Confirm сразу обновляет authoritative Student/Family read model через owner-scoped invalidation без notification. Затем admin открывает delivery preview, выбирает PWA и/или Telegram и явно создаёт immutable batch только для Student: PWA даёт in-app/push, Telegram отправляет личное сообщение через существующего бота. Family только читает актуальное назначение. Любая последующая перестановка помечается Staff как неразосланная и не вызывает автоматический resend.

`classroom_assignment_delivery_batches` snapshot-ит confirmed plan/version, selected channels, recipient hash/counts, admin actor, idempotency key и aggregate state. Recipient rows связывают batch с concrete Student `course_enrollment`/assignment и per-channel delivery state. Telegram destination остаётся server-side; browser видит только безопасный preview и diagnostics.

## API-контуры

Student/Family:

- `GET /{audience}/api/v1/courses`;
- `GET /{audience}/api/v1/courses/{courseId}/enrollment`;
- `PATCH /student/api/v1/courses/{courseId}/enrollment/active-group`;
- `PATCH /student/api/v1/courses/{courseId}/enrollment/attendance`;
- `GET /{audience}/api/v1/courses/{courseId}/lessons?group=&cursor=`;
- `GET /{audience}/api/v1/courses/{courseId}/lessons/{groupLessonId}`;
- `GET /{audience}/api/v1/courses/{courseId}/progress`;
- course-scoped notification overrides.

Первый Phase 3 Student read slice реализован revision `d70b0d9`: список курсов
и enrollment detail читают revalidated session authority через
[`course_routes.py`](../../apps/pwa_api/course_routes.py), а браузер использует
strict [`course-client.ts`](../packages/app-shell/src/course-client.ts).
Revision `66f30c0` добавляет Student lesson list/detail: routable ID всегда
принадлежит конкретному `group_lesson`, active group используется по умолчанию,
а explicit `group` принимается только из revalidated `allowed_groups`. Bounded
список строится одним SQLite statement, содержит только активные занятия с
фактически опубликованным browser-readable condition и не раскрывает
scheduled/hidden revisions. Window возвращает самостоятельные
`submissionClosesAt` и `solutionScheduledAt`; hint/solution availability
следует только actual publication. Revision `77927e0` добавляет
`GET /student/api/v1/home`: все revalidated course enrollments получают
последнее опубликованное занятие active group одним bounded SQLite statement,
а server-owned phase не выводит solution из cutoff. Production `/student/`
использует этот контракт; путь publish→home→content→rollback прошёл в Chromium,
WebKit и Firefox. Revision `42ea05c` подключает production `/student/tasks`:
course/group/lesson — validated URL context, allowed-group просмотр не меняет
active enrollment, а cursor archive открывает exact published `group_lesson`.
Family reads, problem status projection и offline cache остаются в последующих
вертикальных gate; наличие остальных routes в перечне само по себе не означает
готовность endpoint.

Staff:

- CRUD/archive курсов и групп, memberships и scopes;
- schedule inheritance/override и materialization preview;
- независимые actions condition/hint/solution;
- Telegram binding CRUD и inheritance preview;
- synonym candidates, merge/split и impact preview;
- создание/изменение `in_person_event` и inherited classroom plan;
- classroom delivery preview/send/status для confirmed plan с PWA/Telegram channel selection.

Ошибки scope возвращают `403`; optimistic conflict — `409`. Search state курса, группы, занятия, события и вкладки проходит runtime-валидацию TanStack Router/Zod.

## Realtime events

Invalidation payload допускает `audience`, `courseId`, `groupId` и `studentUserId`. Наличие поля сужает получателей; отсутствие означает общий ресурс. Минимальные события:

- `course.enrollment.changed`;
- `course.group-access.changed`;
- `group-lesson.publication.changed`;
- `problem-synonyms.changed`;
- `review.case.changed`;
- `course.progress.invalidated`;
- `notification.preference.changed`;
- `in-person-event.changed`;
- `classroom.assignment.changed`;
- `classroom.assignment.announced`.

После любого reconnect клиент делает authoritative refetch; NATS не является durable log.

## Миграционная граница

Текущие группы сезона относятся к курсу «Математика 5–7». Legacy group IDs, задачи, результаты, Telegram-пути и сообщения не переписываются. Phase 11 обязан выполнить rehearsal на production-size копии SQLite, сравнить legacy и новые read models и подготовить rollback. До этого новые таблицы и API считаются только целевой моделью.

## UI и Storybook

Курс показывается как крупный структурный контекст, группа — мягким существующим цветовым маркером. Product-прототипы используют `CourseView` и `GroupView`; `LevelView` остаётся только временным alias на границе legacy fixtures.

Обязательные компоненты и proof stories перечислены в [карте design → implementation](../dev/development-plan/18-design-implementation-map.md). Они покрывают несколько курсов Student, active/allowed groups, Staff-каталог, независимые расписания, Telegram inheritance, merge/split, merged chronology, combined review, multi-course in-person event и раздельный progress.

## Проверяемые инварианты

- один active group и несколько allowed groups на enrollment;
- schedule snapshot не двигается после изменения шаблона;
- Telegram news складываются, group material targets заменяют course defaults;
- merge/split не меняет concrete submission/result IDs;
- merged chronology всегда показывает provenance;
- combined review пишет verdict в задачу последней посылки и сохраняет snapshot IDs;
- split восстанавливает независимые статусы;
- synonym учитывается один раз внутри каждого group sheet;
- best group выбирается по результату и стабильному sort order;
- progress/strength/achievements/notifications не смешиваются между курсами;
- classroom plan наследуется только для участвующих групп.
