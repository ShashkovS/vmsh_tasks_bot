# Сквозной план многокурсовой модели

Статус: принятое planning input от 26 июля 2026 года. Backend и миграции не реализованы. Этот файл дополняет фазы 1–11 и не создаёт отдельную двенадцатую фазу.

Authoritative product model: [`docs/courses-groups-and-lessons.md`](../../docs/courses-groups-and-lessons.md).

## Сквозные инварианты

- `season → course → group → course_lesson/group_lesson`;
- один active group и несколько allowed groups на `course_enrollment`;
- attendance mode, progress, strength, achievements и notification override — per course;
- content, concrete publication windows и Telegram overrides — per group;
- одна synonym-group только внутри одного `course_lesson`;
- merge/split меняет projection, но не concrete task/submission/result IDs;
- merged timeline не имеет веточных вкладок, но каждый блок показывает provenance;
- combined review пишет verdict в concrete problem последней посылки;
- Student/Family не сравнивают ребёнка с группой;
- `in_person_event` может включать group lessons разных курсов и номеров, но одна аудитория содержит одну группу;
- все scopes и invalidations проверяются сервером, URL state не является авторизацией.

## Раскладка по фазам

### Phase 1 — identity, enrollment и scope

Создать `courses`, расширение `groups`, `course_enrollments`, `course_group_access`, `course_enrollment_events`, `staff_scopes`; backfill текущих групп в «Математика 5–7». Session остаётся audience-scoped, а выбранный курс — resource context, не отдельная сессия.

Проверяемый результат: Student получает список курсов, меняет active group/mode только в одном курсе; Teacher видит разрешённый course/group и получает `403` вне scope.

### Phase 2 — lessons, schedules и независимые публикации

Создать `course_lessons`, `group_lessons`, versioned course rules и group overrides. Материализовать окна при создании group lesson. Condition/hint/solution публиковать и откатывать независимо.

Проверяемый результат: два group lessons одного номера используют разные LaTeX revisions и расписания; последующая правка course template не меняет snapshot без preview/confirm.

### Phase 3 — чтение по курсам

Student «Сейчас» показывает отдельную карточку курса; Tasks хранит `course`, `group`, `lesson` в validated search. Cache/query keys включают course/group. Отозванная группа не получает новые материалы, но собственная история остаётся.

### Phase 4 — тестовые синонимы

Добавить candidate/merge/split projection. Попытки, rate limits и checker остаются per-problem. Общий статус отражает текущую synonym-group, но source attempt IDs не меняются.

### Phase 5 — письменные ветки

Письменные submission/photos/messages хранят concrete `problem_id`. Merged timeline упорядочивает все ветки по времени и показывает курс/группу/задачу без фильтра. Offline outbox key включает concrete problem, а UI после sync обновляет logical projection.

### Phase 6 — combined review

Один review case объединяет ожидающие посылки одной synonym-group/student. Lock/snapshot перечисляет все submission IDs; verdict/comment записывается в problem последней включённой посылки. Split восстанавливает статусы остальных веток.

### Phase 7 — in-person event

Перевести layouts/plans с глобального lesson на `in_person_event`. Event выбирает group lessons любых курсов/номеров и наследует последние подтверждённые комнаты и назначения каждой выбранной группы.

### Phase 8 — Telegram и notifications

Ввести `telegram_bindings` course/group с additive news и replacement/inheritance для materials targets. Notification overrides и owner-scoped invalidations несут course/group/student IDs. Reconnect всегда вызывает authoritative refetch.

### Phase 9 — Family и course analytics

Разделить Family activity, strength, progress, streak и achievements по курсам. В каждом lesson вычислять score каждого доступного group sheet, засчитывая synonym-group один раз внутри листка; выбирать best group по score и stable sort order.

### Phase 10 — Staff catalog

Реализовать полный CRUD/archive курсов и групп, memberships/scopes, schedule overrides, Telegram binding editor и synonym impact preview. Google replacement импортирует данные в course-aware модель.

### Phase 11 — rehearsal и rollout

На production-size копии создать «Математика 5–7», backfill enrollments/access/lessons, сравнить legacy и новые read models, Telegram paths, statistics и classroom inheritance. Подготовить dual-read/rollback и reconciliation report.

## Обязательные API/events

Полный список находится в [`03-api-events-and-files.md`](03-api-events-and-files.md) и product model. Минимальный набор: course list/enrollment/switch/attendance/lessons/progress; Staff course/group CRUD, schedule preview/confirm, Telegram bindings, synonym candidates/merge/split/impact, in-person event composition/inherited plan и explicit classroom delivery preview/send/status. События имеют optional `audience`, `courseId`, `groupId`, `studentUserId`.

## Prototype → implementation

Использовать [`18-design-implementation-map.md`](18-design-implementation-map.md). `CourseView`/`GroupView` — целевые UI-модели; `LevelView` допустим только как временный legacy alias. Prototype callbacks и fixtures не являются готовым API.

## Общий proof многокурсового cutover

- [ ] migrations empty/upgrade/rollback + production-size rehearsal;
- [ ] legacy ID and Telegram-path reconciliation;
- [ ] contract fixtures Student/Family/Staff;
- [ ] enrollment/scope/schedule/Telegram/synonym/statistics/classroom invariant tests;
- [ ] Storybook interaction+a11y для всех stories из design map;
- [ ] production-preview E2E Chromium/WebKit/Firefox;
- [ ] owner-approved mobile-light и desktop visual diff без самовольного snapshot update;
- [ ] updated runbooks, STATUS и known limitations;
- [ ] доказательство, что backend/migrations включены только после фактической реализации.
