# Этап 7. Устный онлайн-контур, режим присутствия и аудитории

## Проверяемый результат

Онлайн-школьник видит несколько устных окон, раскрывает Zoom details по tap и при желании отправляет устную задачу в обычную письменную очередь. Staff администрирует устные результаты. Admin ведёт постоянный каталог аудиторий, подтверждает наследуемую схему «аудитория → группа», получает preview распределения очных школьников и публикует корректный версионируемый план. Student и Family видят актуальное назначение; classroom push получает только Student.

Дизайн-контракт этапа: [oral/written submission, полный classroom planner, public assignment states и Storybook stories](18-design-implementation-map.md#phase-7-design).

Печатные комплекты и быстрый очный ввод результатов преподавателем относятся ко второй версии. Административное планирование аудиторий входит в v1.

## Граница v1

- Позиции школьника в устной очереди нет.
- Очный школьник не сдаёт через Student PWA; web-интерфейс учителя в аудитории отложен.
- Teacher не имеет classroom routes; server возвращает `403` и Staff показывает forbidden state.
- Oral task и written-before-oral используют существующие numeric problem types без изменения Telegram semantics.
- Telegram-рассылка аудиторий остаётся в legacy-процессе. Staff v1 не публикует её в Telegram, но до cutover должен быть выбран источник данных bridge по `CLASSROOM-01`.
- Classroom planner не получает полноценный print UI, постоянный spreadsheet workflow, вместимость или веса. Если принят рекомендуемый вариант `CLASSROOM-01`, он отдаёт узкий versioned/hash-stamped compatibility export подтверждённого плана для `a02`/`a11`–`a14`; это не пользовательский export-конструктор. Назначения выполняются компактными select; drag-and-drop для этого экрана не используется.

## Миграции и модель данных

Логическая migration: `pwa_support_oral_classroom_plans_banners`.

- `oral_windows` с несколькими sequence numbers (текущий процесс использует три), adapter/view над `zoom_conversation`, `zoom_events`, `zoom_queue`.
- `classrooms` — глобальный каталог с Unicode-normalized unique name, archive/restore, audit и optimistic `version`.
- `classroom_layout_versions` + `classroom_layout_rooms` — draft/confirmed/superseded схемы, действующие начиная с выбранного занятия. Аудитория относится максимум к одной группе; группа может иметь любое число аудиторий.
- `classroom_assignment_plans` + `classroom_assignments` — draft/confirmed/stale/superseded планы и snapshot группы ученика. `assigned` требует комнату, `reassigning` её не содержит.
- `users.grade`, `users.birthday` и существующая `student_strength` используются как nullable read sources. Расчёт силы остаётся совместимым с `_external_pipelines/a53_calc_rating_new.py`, выполняется versioned analytics job раз в несколько часов, публикует только полный successful run и не получает ручного Staff editor. Этап 7 может читать latest projection; исторические lesson metrics и графики подключаются в этапе 9.
- `group_banners` может создаваться здесь или в этапе 8, но oral-window card остаётся отдельным типом UI.
- `user_changes_log` продолжает фиксировать online/in-person и group changes; audit сохраняет catalog/layout/plan mutations и одноразовый import.

Первый production backfill — отдельная одноразовая команда этапа. Она читает текущий Excel-export с колонками `IDd`, `Уровень`, `Аудитория`, сначала формирует dry-run report, затем при явном подтверждении создаёт catalog, effective layout и initial plan. Dry-run показывает неизвестные `IDd`, неизвестные группы, пустые/дублирующиеся после NFKC+casefold комнаты, смешение групп и школьников без назначения. `_external_pipelines` не импортируется в runtime, а исходный файл не становится постоянным source of truth. После apply authoritative source — confirmed Staff plan; legacy print/Telegram scripts получают только утверждённый bridge snapshot либо требуют явно принятого двойного ввода, но не продолжают незаметно читать прежнюю Excel-версию.

## Domain rules

### Каталог

- `name = trim(input)`, пустое значение отклоняется; внутренние пробелы и регистр display-name сохраняются.
- `normalized_name = NFKC(name).casefold()`; `201` остаётся строкой, `Актовый зал` и `актовый зал` конфликтуют.
- Hard delete отсутствует. Rename меняет глобальное отображаемое имя и сохраняет `before/after` в audit. Archive/restore — частые обратимые операции.
- Archive используемой комнаты не меняет прошлые планы. В одной транзакции current plan становится `stale`, layout read model помечает archived reference как invalid, materialize-ится replacement layout/plan draft с затронутыми строками `reassigning`, а публичный read model сразу сбрасывает имя комнаты; restore сам по себе назначения не возвращает. Новую схему нельзя подтвердить, пока archived room не удалена из current mapping.

### Схема по группам

- Новое занятие читает последнюю финализированную версию с `effective_from_lesson <= lesson` напрямую; `superseded` версия остаётся исторически effective до границы следующей.
- Первая правка materialize-ит draft с `base_version_id`; дальнейшие изменения требуют ожидаемую `version`.
- Изменение/подтверждение схемы помечает связанный student plan `stale`. Для продолжения нужны preview, пересчёт и новое подтверждение.
- Неиспользованные active rooms допустимы. Числа вроде 6/5/2 — фактические counts комнат по группам, а не ограничения.
- Для каждой группы read model считает всех active in-person школьников выбранного занятия и отдельно уже назначенных; эти числа не являются capacity. Цвет группы приходит из общего level/group token mapping.

### Распределение школьников

- Для каждого очного школьника сначала сохраняется последняя историческая комната для его текущей группы, если она active и входит в current layout; это позволяет вернуть прежнюю аудиторию после возвращения на уровень.
- Остальные назначаются в наименее заполненную комнату группы. Равенство разрешает server natural sort нормализованного имени (цифровые фрагменты сравниваются как числа), затем стабильный classroom ID.
- Group change и online→in-person сразу применяют это правило к школьнику. In-person→online снимает назначение.
- Если допустимых комнат нет, школьник остаётся `reassigning`, Staff получает blocking incident.
- Manual select/move меняет только draft и фиксирует `source=manual`; explicit full recalculation не перезаписывает confirmed history.
- UI не отправляет mutation после каждого select. Изменения накапливаются в account/lesson/base-version-scoped local draft, переживают reload и отправляются одним batch-save/confirm.
- Выбор комнаты другой группы требует отдельного подтверждения смены группы. Backend применяет group change, запись `user_changes_log` и assignment атомарно; отмена локального draft ничего не меняет на сервере.
- Школьники внутри комнаты всегда сортируются по фамилии и имени. Confirmed plans служат неизменяемой историей аудиторий, доступной из строки школьника.
- Возраст вычисляется на сегодня с точностью до десятой года; класс и сила nullable. Room averages возраста, класса и силы независимо исключают отсутствующие значения и округляются до одного знака. Сила лежит в диапазоне 0–10 и вычисляется автоматически.
- Поиск нормализует case, `ё/е`, пробелы и порядок слов, затем использует ограниченное редакционное расстояние по уже загруженным строкам. Совпадение подсвечивается, к нему можно перейти.
- Confirm запрещён при смешении групп в комнате, mismatch snapshot/current group/layout или любом очном школьнике без комнаты. Active unused room разрешена.

## Backend и API

- Oral window config создаёт только admin; provider v1 — Zoom, written fallback всегда видим.
- Join details endpoint проверяет auth/group/mode и не кеширует/логирует secret.
- Staff oral workflow использует adapter к существующим zoom/result domain functions и не создаёт второй ledger verdict.
- Catalog endpoints: list/search/filter, create, rename, archive, restore.
- Layout endpoints: effective read, materialize, replace room mappings, confirm.
- Assignment endpoints: read preview/current, recalculate, batch-save selected students, read confirmed student room history, confirm.
- Все mutations используют optimistic version/`If-Match`: stale write — `409`; incomplete or invalid plan — `422` с предметным error code.
- Owner-scoped `classroom.assignment.changed` инвалидирует Student/Family read model. Student создаёт push/in-app на first assignment, withdrawal и new assignment; Family только refetch-ит состояние.
- Reconnect всегда делает authoritative refetch; событие не является журналом назначения.

Планируемые файлы этапа:

```text
migrations/<timestamp>_pwa_support_oral_classroom_plans_banners.py
models/pwa/classrooms.py
db_methods/pwa/classrooms.py
helpers/pwa/classroom_assignment.py
helpers/pwa/classroom_import.py
apps/pwa_api/classroom_routes.py
pwa_tests/domain/test_classroom_assignment.py
pwa_tests/api/test_classrooms.py
pwa_tests/integration/test_classroom_import.py
vmshpwa/packages/contracts/src/classrooms.ts
vmshpwa/packages/contracts/fixtures/classrooms/
vmshpwa/apps/staff/src/features/classrooms/
vmshpwa/apps/student/src/features/profile/classroom-assignment.tsx
vmshpwa/apps/family/src/features/children/classroom-assignment.tsx
vmshpwa/e2e/classrooms.spec.ts
```

## Frontend и дизайн-система

- Student oral card: current status, open/close time, join reveal, written composer, offline limitations.
- Mode switch объясняет зарезервированную аудиторию, напечатанные материалы и поиск преподавателей; просит отключать очный режим при неявке.
- Staff navigation использует название «Аудитории» и route `/staff/classrooms`.
- URL search params: `lesson`, `tab=catalog|groups|students`, `roomStatus=active|archived|all` с runtime validation.
- «Каталог»: add/rename, search, active/hidden filter, archive и quick restore; duplicate показывает найденную комнату без потери ввода.
- «По группам»: effective/inherited source, materialize state, строки аудиторий с group select/unassigned, summary фактического числа комнат и пары `очно/распределено` по группе. Цвет — узкий маркер плюс мягкая тонировка границы, не единственный носитель смысла.
- «Школьники»: компактные flex-wrap-карточки комнат, отдельная секция reassigning/unassigned, фамильно-именная сортировка, manual select, поиск с подсветкой/переходом, recalculate, stale warning и confirm.
- Строка школьника: имя, nullable возраст `13.3`, nullable класс, nullable сила 0–10, compact room select и доступ к истории. Заголовок комнаты: assigned count, средний возраст, средний класс и средняя сила; рекомендуемый компактный формат `15 чел. · возраст 13.3 · класс 7.2 · сила 6.8`.
- Массовый сценарий: режим выбора строк с checkbox, sticky action bar, один select аудитории и подтверждение для cross-group move. Типовой одиночный сценарий не требует входить в bulk mode.
- Любое изменение plan UI сразу сохраняется в local browser draft. Reload восстанавливает его; успешный batch-save/confirm очищает, conflict предлагает сравнить/пересчитать, explicit discard требует подтверждения.
- Student/Family view: `not_applicable | reassigning | assigned`, имя комнаты и время публикации. Draft layout/plan и другие школьники не видны.
- Staff mobile layout остаётся последовательным и не теряет catalog/layout/plan actions.

## Тесты

### Unit и domain/property

- trim, empty, NFKC+casefold, кириллический duplicate, archive/restore и optimistic conflict.
- Effective inherited layout resolution, materialize-on-first-edit и historical immutability.
- Свойство: одна комната никогда не содержит разные группы.
- Свойство: прежняя допустимая комната сохраняется.
- Свойство: остальные попадают в наименее заполненную комнату с детерминированным tie-break.
- Свойство: group/mode change и room archive сохраняют инварианты или явно создают `reassigning`.
- Возраст округляется до одного знака и корректно обрабатывает отсутствующую/невалидную дату; nullable age/grade/strength не попадают в соответствующие room averages, сами averages округляются до одного знака.
- Fuzzy normalization покрывает case, `ё/е`, лишние пробелы, переставленные имя/фамилию и одну типичную опечатку.
- Moscow timezone/DST-independent oral boundaries и server/client clock.

### API/integration

- Teacher получает `403` на каждый classroom mutation/read route.
- Stale catalog/layout/plan version получает `409`; повтор confirm идемпотентен либо возвращает актуальный receipt.
- Confirm incomplete/mixed/mismatched plan запрещён; unused room допустима.
- Batch move применяет все строки атомарно; cross-group move без confirmation отклоняется и не меняет ни группу, ни аудиторию. История возвращает только confirmed plans.
- Прошлые confirmed layouts/plans не меняют membership/assignment после archive/recalculation текущего урока. Глобальный rename исправляет отображаемое имя и в истории, а прежнее имя остаётся в audit.
- Join secret исключён из caches, Sentry, WS и list payload.
- Mapping oral results к `results`, duplicate import и legacy Zoom history сохраняются.
- One-time Excel dry-run/import проверяется на anonymized fixtures с `IDd`, `Уровень`, `Аудитория` и сравнительным report по `a11`.
- При варианте compatibility export проверяется round-trip: confirmed plan → export → неизменённые `a02`/`a11`–`a14` fixtures, hash/version watermark и отказ использовать stale snapshot.

### Storybook

- Catalog: active, hidden, duplicate, rename conflict, archive и restore.
- Layout: inherited/effective, materialized draft, unassigned rooms, фактические 6/5/2 комнаты, group colors, `очно/распределено` и optimistic conflict.
- Plan: preview/confirm, stale, отдельная reassigning-секция, empty group, no-room blocking incident, компактные комнаты для 200 школьников, возраст/класс/сила, room averages, fuzzy search+jump, single/bulk select, cross-group confirmation, history и recalculation.
- Local draft: reload restore, explicit discard, successful clear и server-version conflict без потери изменений.
- Student/Family assigned/reassigning/not-applicable; Staff forbidden и mobile layout.
- Все stories проходят interaction, a11y error gate, light/dark и принятые viewports; visual diff принят человеком.

### E2E

- Добавить `201` и `Актовый зал`; попытка добавить `АКТОВЫЙ ЗАЛ` получает понятный duplicate conflict.
- Распределить комнаты по группам, пересчитать и подтвердить школьников, проверить Student/Family read state и отсутствие Family classroom push.
- Набрать несколько локальных изменений, перезагрузить страницу, проверить восстановление, выполнить bulk move и отдельно подтвердить cross-group change.
- Найти школьника по фрагменту с опечаткой, перейти к подсвеченной строке и открыть его прошлые подтверждённые аудитории.
- Скрыть используемую комнату, увидеть `reassigning`, пересчитать и подтвердить новую комнату; прошлый lesson остаётся неизменным.
- Прогон выполняется в Chromium, WebKit и Firefox на production bundles с настоящим aiohttp/seeded SQLite, без MSW.

## Критерии приёмки

- Join secret доступен только eligible online student после explicit tap.
- Oral verdict совместим с исторической статистикой/`results`.
- In-person student не получает online submission CTA, но может безопасно сменить mode после подтверждения.
- Каталог корректно нормализует имена, не удаляет историю и не допускает Unicode/case duplicate.
- Effective layout наследуется без копии и материализуется только при первой правке.
- Confirmed plan удовлетворяет всем group/room invariants; отсутствие комнаты всегда видно и блокирует confirm.
- План остаётся удобным при 6–15 комнатах и примерно 200 школьниках: compact flex-wrap layout, постоянная фамильно-именная сортировка, отдельные неназначенные, single/bulk select и fuzzy jump.
- Age/grade/strength корректно переживают missing data; group/room counts и averages не изображаются как capacity или сравнение учеников.
- Ни reload, ни PWA update не теряют локальный classroom draft; server conflict не перезаписывает его молча.
- Layout edit/archive никогда не переписывает прошлое и переводит текущие затронутые назначения в stale/reassigning.
- Student и Family видят один и тот же опубликованный room state; push/in-app по аудиториям получает только Student.
- В первой версии нет capacity, weights, classroom drag-and-drop, полноценного print/export UI или Staff→Telegram action. Узкий compatibility export, если выбран в `CLASSROOM-01`, является миграционным bridge, а не возвращением spreadsheet source of truth.

Этап 7 завершает classroom domain event, recipient policy и foreground in-app state. Durable Web Push transport и общая notification delivery matrix проходят общий инфраструктурный gate этапа 8; это не меняет правило получателя и не разрешает Family classroom push.

## Пруфы завершения этапа

- [ ] Revision, migration up/down и rehearsal на копии production-size SQLite: `<sha/paths/results>`.
- [ ] One-time Excel dry-run/import report с анонимизированными `IDd`, найденными конфликтами и итоговыми counts: `<path/result>`.
- [ ] Demo online oral + written fallback + Staff result: `<routes/video/evidence>`.
- [ ] Catalog normalization/archive/restore и optimistic conflict report: `<tests/result>`.
- [ ] Classroom assignment property/invariant report: `<seed/count/result>`.
- [ ] Fuzzy-search, age/grade/strength projection, aggregates и rating-job parity с `a53_calc_rating_new.py`: `<tests/result>`.
- [ ] Local draft reload/conflict/discard и atomic single/bulk/cross-group save: `<tests/result>`.
- [ ] Historical immutability и stale/reassigning API tests, включая Teacher `403`: `<result>`.
- [ ] Join secret authorization/no-log/no-cache tests: `<result>`.
- [ ] Storybook catalog/layout/plan/Student/Family stories, interaction+a11y и просмотренный visual diff: `<story-ids/paths/approver/date>`.
- [ ] Playwright classroom E2E в трёх браузерах на production preview: `<result/artifacts>`.
- [ ] Parity evidence против `a11` fixtures и зафиксированная граница отложенной печати: `<paths>`.
- [ ] Telegram/Zoom historical tests: `<result>`.
- [ ] Обновлённые contracts, API/domain docs, runbook, known limitations и запись в `STATUS.md`: `<paths/issues/name/date>`.
