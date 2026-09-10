# Этап 7. Устный онлайн-контур, режим присутствия и аудитории

## Проверяемый результат

Онлайн-школьник видит несколько устных окон, раскрывает Zoom details по tap и при желании отправляет устную задачу в обычную письменную очередь. Staff администрирует устные результаты. Admin ведёт постоянный каталог аудиторий, подтверждает наследуемую схему «аудитория → группа», получает preview распределения очных школьников и публикует корректный версионируемый план. Student и Family видят актуальное назначение; затем admin отдельным действием рассылает его Student через PWA и/или личный Telegram-диалог.

Дизайн-контракт этапа: [oral/written submission, полный classroom planner, public assignment states и Storybook stories](18-design-implementation-map.md#phase-7-design).

Печатные комплекты и быстрый очный ввод результатов преподавателем относятся ко второй версии. Административное планирование аудиторий входит в v1.

## Граница v1

- Позиции школьника в устной очереди нет.
- Очный школьник не сдаёт через Student PWA; web-интерфейс учителя в аудитории отложен.
- Teacher не имеет classroom routes; server возвращает `403` и Staff показывает forbidden state.
- Oral task и written-before-oral используют существующие numeric problem types без изменения Telegram semantics.
- `CLASSROOM-01` закрыт: после confirm admin отдельно запускает «Разослать аудитории», проверяет recipient preview и выбирает PWA и/или Telegram. Telegram идёт каждому школьнику в личный диалог существующего бота по server-side mapping; это замена узкого сценария `a02`, а не публикация в group channel и не общий broadcast composer.
- Classroom planner не получает полноценный print UI, постоянный spreadsheet workflow, вместимость или веса. Печать `a11`–`a14` остаётся отдельным legacy workflow до Staff-раздела второй версии; v1 compatibility export не обещается. Назначения выполняются компактными select; drag-and-drop для этого экрана не используется.

## Граница с legacy-печатью и риск расхождения

Текущий операционный процесс сознательно разделяет раннюю персональную рассылку и финальную печать. Между ними ученики меняют режим, поэтому оператор повторно обновляет SQLite, аккуратно сливает `ИзБота`/посещаемость с ручными назначениями, подкручивает план и запускает `a11_spis_from_xls.py` только после final readiness sign-off непосредственно перед печатью.

Это создаёт две разные версии: «что уже разослано» и «что идёт на бумагу». Целевой plan обязан явно хранить confirmed plan version, delivery batch version/time и признак изменившихся, но ещё не разосланных назначений. Он не может скрывать это расхождение авторассылкой: после любой перестановки новая PWA/Telegram delivery выполняется только явным admin-действием.

Пока Staff print-раздел не реализован, Phase 7 не может объявить production cutover аудиторий лишь по факту работы web-плана. Cutover proof должен также доказать воспроизводимую version-bound передачу именно confirmed Staff snapshot в текущий legacy print workflow либо оставить Excel операционным source of truth до второй версии. Формат этого временного handoff не объявляется постоянным spreadsheet workflow и не расширяет v1 UI.

## Миграции и модель данных

Логическая migration: `pwa_support_oral_classroom_plans_banners`.

- `oral_windows` с несколькими sequence numbers (текущий процесс использует три), adapter/view над `zoom_conversation`, `zoom_events`, `zoom_queue`.
- `classrooms` — глобальный каталог с Unicode-normalized unique name, archive/restore, audit и optimistic `version`.
- `classroom_layout_versions` + `classroom_layout_rooms` — event-scoped draft/confirmed/superseded схемы с provenance последних confirmed mappings выбранных групп. Аудитория относится максимум к одной группе; группа может иметь любое число аудиторий.
- `classroom_assignment_plans` + `classroom_assignments` — event-scoped draft/confirmed/stale/superseded планы и snapshot `course_enrollment/group_lesson/group`. `assigned` требует комнату, `reassigning` её не содержит.
- `classroom_assignment_delivery_batches` + recipients — immutable confirmed-plan snapshot для explicit PWA/personal-Telegram send только Student.
- `users.grade`, `users.birthday` и существующая `student_strength` используются как nullable read sources. Расчёт силы остаётся совместимым с `_external_pipelines/a53_calc_rating_new.py`, выполняется versioned analytics job раз в несколько часов, публикует только полный successful run и не получает ручного Staff editor. Этап 7 может читать latest projection; исторические lesson metrics и графики подключаются в этапе 9.
- `group_banners` может создаваться здесь или в этапе 8, но oral-window card остаётся отдельным типом UI.
- `user_changes_log` остаётся неизменяемым legacy source для online/in-person и group history; новый `course_enrollment_events` записывает только реальные переходы. При backfill последовательные одинаковые `G`/`O` значения считаются no-op и схлопываются с отдельными source/no-op/created counts в отчёте. Audit сохраняет catalog/layout/plan mutations и одноразовый import.

Первый production backfill — отдельная одноразовая команда этапа. Она читает текущий Excel-export с колонками `IDd`, `Уровень`, `Аудитория`, сначала формирует dry-run report, затем при явном подтверждении создаёт catalog, effective layout и initial plan. `IDd` здесь является legacy numeric `users.id`, а не Telegram token или новым browser ID. Dry-run показывает неизвестные `IDd`, неизвестные группы, пустые/дублирующиеся после NFKC+casefold комнаты, смешение групп и школьников без назначения. `_external_pipelines` не импортируется в runtime, а исходный файл не становится постоянным source of truth. После apply authoritative source назначений и персональной рассылки — confirmed Staff plan. Legacy print scripts остаются отдельным явно обозначенным процессом до реализации print-раздела второй версии.

## Domain rules

### Каталог

- `name = trim(input)`, пустое значение отклоняется; внутренние пробелы и регистр display-name сохраняются.
- `normalized_name = NFKC(name).casefold()`; `201` остаётся строкой, `Актовый зал` и `актовый зал` конфликтуют.
- Hard delete отсутствует. Rename меняет глобальное отображаемое имя и сохраняет `before/after` в audit. Archive/restore — частые обратимые операции.
- Archive используемой комнаты не меняет прошлые планы. В одной транзакции current plan становится `stale`, layout read model помечает archived reference как invalid, materialize-ится replacement layout/plan draft с затронутыми строками `reassigning`, а публичный read model сразу сбрасывает имя комнаты; restore сам по себе назначения не возвращает. Новую схему нельзя подтвердить, пока archived room не удалена из current mapping.

### Схема по группам

- Новое `in_person_event` виртуально объединяет последние confirmed mappings и assignments каждой выбранной группы, даже если группы относятся к разным курсам/номерам занятий. Неучаствующие группы не копируются.
- Первая правка materialize-ит event draft с `base_version_id`/provenance; дальнейшие изменения требуют ожидаемую `version`.
- Изменение/подтверждение схемы помечает связанный student plan `stale`. Для продолжения нужны preview, пересчёт и новое подтверждение.
- Неиспользованные active rooms допустимы. Числа вроде 6/5/2 — фактические counts комнат по группам, а не ограничения.
- Для каждой группы read model считает всех active in-person школьников выбранного занятия и отдельно уже назначенных; эти числа не являются capacity. Цвет группы приходит из общего level/group token mapping.

### Распределение школьников

- Для каждого очного школьника сначала сохраняется последняя историческая комната для его текущей группы, если она active и входит в current layout; это позволяет вернуть прежнюю аудиторию после возвращения на уровень.
- Остальные назначаются в наименее заполненную комнату группы. Равенство разрешает server natural sort нормализованного имени (цифровые фрагменты сравниваются как числа), затем стабильный classroom ID.
- Group change и online→in-person сразу применяют это правило к школьнику. In-person→online снимает назначение.
- Если допустимых комнат нет, школьник остаётся `reassigning`, Staff получает blocking incident.
- Manual select/move меняет только draft и фиксирует `source=manual`; explicit full recalculation не перезаписывает confirmed history.
- UI не отправляет mutation после каждого select. Изменения накапливаются в account/event/base-version-scoped local draft, переживают reload и отправляются одним batch-save/confirm.
- Выбор комнаты другой группы того же курса требует отдельного подтверждения смены active group. Backend применяет `course_enrollment_events`, legacy mirror в `user_changes_log` на период миграции и assignment атомарно; отмена локального draft ничего не меняет на сервере. Комнаты групп другого курса не являются вариантами этой строки.
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
- Owner-scoped `classroom.assignment.changed` после confirm инвалидирует Student/Family read model без notification delivery. `classroom.assignment.announced` создаётся только explicit admin batch: выбранный PWA-канал создаёт Student in-app/push, Telegram-канал отправляет личное bot message. Family только refetch-ит состояние.
- Delivery preview фиксирует confirmed plan version, recipient snapshot/hash, число изменившихся после прошлого batch назначений и Telegram-unreachable recipients. Любое изменение плана инвалидирует preview; автоматического resend нет.
- Reconnect всегда делает authoritative refetch; событие не является журналом назначения.

Планируемые файлы этапа:

```text
migrations/<timestamp>_pwa_support_oral_classroom_plans_banners.py
models/pwa/classrooms.py
db_methods/pwa/classrooms.py
helpers/pwa/classroom_assignment.py
helpers/pwa/classroom_import.py
helpers/pwa/classroom_delivery.py
apps/pwa_api/classroom_routes.py
pwa_tests/domain/test_classroom_assignment.py
pwa_tests/domain/test_classroom_delivery.py
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
- URL search params: `event`, optional `course/group`, `tab=catalog|groups|students`, `roomStatus=active|archived|all` с runtime validation. Delivery preview открывается из confirmed students plan и не создаёт четвёртую основную вкладку.
- «Каталог»: add/rename, search, active/hidden filter, archive и quick restore; duplicate показывает найденную комнату без потери ввода.
- «По группам»: effective/inherited source, materialize state, строки аудиторий с group select/unassigned, summary фактического числа комнат и пары `очно/распределено` по группе. Цвет — узкий маркер плюс мягкая тонировка границы, не единственный носитель смысла.
- «Школьники»: компактные flex-wrap-карточки комнат, отдельная секция reassigning/unassigned, фамильно-именная сортировка, manual select, поиск с подсветкой/переходом, recalculate, stale warning и confirm.
- Строка школьника: имя, nullable возраст `13.3`, nullable класс, nullable сила 0–10, compact room select и доступ к истории. Заголовок комнаты: assigned count, средний возраст, средний класс и средняя сила; рекомендуемый компактный формат `15 чел. · возраст 13.3 · класс 7.2 · сила 6.8`.
- Массовый сценарий: режим выбора строк с checkbox, sticky action bar, один select аудитории и подтверждение для перехода в другую группу того же курса. Типовой одиночный сценарий не требует входить в bulk mode.
- Любое изменение plan UI сразу сохраняется в local browser draft. Reload восстанавливает его; успешный batch-save/confirm очищает, conflict предлагает сравнить/пересчитать, explicit discard требует подтверждения.
- Student/Family view: `not_applicable | reassigning | assigned`, имя комнаты, время confirm и nullable время последней явной рассылки. Draft layout/plan, delivery destination и другие школьники не видны.
- После confirm отдельный admin-only delivery step показывает recipient/changed/Telegram-unreachable counts, PWA/Telegram checkboxes, immutable preview version и progress/retry. Любое последующее plan change возвращает состояние «есть неразосланные изменения» без auto-send.
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
- Batch move применяет все строки атомарно; переход в другую группу того же курса без confirmation отклоняется и не меняет ни группу, ни аудиторию, а переход между курсами невалиден. История возвращает только confirmed plans.
- Прошлые confirmed layouts/plans не меняют membership/assignment после archive/recalculation текущего урока. Глобальный rename исправляет отображаемое имя и в истории, а прежнее имя остаётся в audit.
- Join secret исключён из caches, Sentry, WS и list payload.
- Mapping oral results к `results`, duplicate import и legacy Zoom history сохраняются.
- One-time Excel dry-run/import проверяется на synthetic committed fixtures с `IDd`, `Уровень`, `Аудитория` и сравнительным report по `a11`. Production-size локальный rehearsal может исходить только из временной копии `db/vmsh.db`, в которой до derivation имена и фамилии заменены Faker-значениями; source DB никогда не меняется, а копия не коммитится.
- Delivery batch проверяется как immutable snapshot: preview hash/version conflict, idempotency, partial channel failure/retry, отсутствие token/chat ID в browser/logs и запрет draft/stale send.
- Narrow Telegram delivery характеризуется против recipient semantics `a02`, но новый runtime не импортирует скрипт. Print parity `a11`–`a14` остаётся proof отдельной второй версии.

### Storybook

- Catalog: active, hidden, duplicate, rename conflict, archive и restore.
- Layout: inherited/effective, materialized draft, unassigned rooms, фактические 6/5/2 комнаты, group colors, `очно/распределено` и optimistic conflict.
- Plan: preview/confirm, stale, отдельная reassigning-секция, empty group, no-room blocking incident, компактные комнаты для 200 школьников, возраст/класс/сила, room averages, fuzzy search+jump, single/bulk select, cross-group confirmation, history и recalculation.
- Local draft: reload restore, explicit discard, successful clear и server-version conflict без потери изменений.
- Student/Family assigned/reassigning/not-applicable; Staff forbidden и mobile layout.
- Admin delivery preview: PWA/Telegram channel selection, recipient/changed/unreachable counts, sending/partial failure/completed, stale preview и повторное явное действие после изменения плана.
- Все stories проходят interaction, a11y error gate, light/dark и принятые viewports; visual diff принят человеком.

### E2E

- Добавить `201` и `Актовый зал`; попытка добавить `АКТОВЫЙ ЗАЛ` получает понятный duplicate conflict.
- Распределить комнаты по группам, пересчитать и подтвердить школьников, проверить немедленный Student/Family refetch без notification; затем admin preview/send PWA+Telegram и отсутствие Family classroom delivery.
- Набрать несколько локальных изменений, перезагрузить страницу, проверить восстановление, выполнить bulk move и отдельно подтвердить cross-group change.
- Найти школьника по фрагменту с опечаткой, перейти к подсвеченной строке и открыть его прошлые подтверждённые аудитории.
- Скрыть используемую комнату, увидеть `reassigning`, пересчитать и подтвердить новую комнату; прошлое очное событие остаётся неизменным.
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
- Student и Family видят один и тот же confirmed room state; персональную PWA/Telegram рассылку после явного admin action получает только Student.
- Изменённое после рассылки назначение явно помечено как неразосланное и никого не уведомляет автоматически.
- В первой версии нет capacity, weights, classroom drag-and-drop, полноценного print/export UI или общего Staff→Telegram publisher. Узкая персональная рассылка аудиторий является отдельным типизированным действием.

Этап 7 завершает classroom domain event, delivery preview/batch contract, recipient policy и foreground in-app state. Durable Web Push/Telegram transport и общая notification delivery matrix проходят инфраструктурный gate этапа 8; это не меняет explicit-send правило и не разрешает Family classroom delivery.

## Пруфы завершения этапа

### Рабочий Staff-контур очного события — 18 августа 2026

- `/staff/classrooms` подключён к реальному каталогу очных событий. Admin
  создаёт и редактирует дату/время, статус и точный набор `group_lesson`, а
  затем без ручной подстановки opaque ID переходит к схеме и распределению.
  Новые события получают читаемый public ID `in-person-YYYY-MM-DD`.
- API `GET/POST /staff/api/v1/in-person-events` и
  `PATCH /staff/api/v1/in-person-events/{event}` использует optimistic version;
  после появления classroom plan состав групп события фиксируется, чтобы не
  подменить основу уже подтверждённых назначений.
- Вкладки «По группам» и «Школьники» работают с SQLite: наследуют последний
  подтверждённый план, сохраняют локальный черновик, поддерживают одиночные и
  массовые select-переносы и подтверждают новый snapshot. Карточки комнат
  компактно показывают count и средние возраст/класс/силу.
- Подтверждение и рассылка остаются двумя действиями. Preview позволяет явно
  выбрать PWA и личный Telegram; черновые перестановки и сохранение события
  никого автоматически не уведомляют.
- Student и Family показывают московские дату/время события и подтверждённую
  аудиторию. Family не получает classroom push/Telegram delivery.
- Исполняемые точки: `apps/pwa_api/classroom_layout_routes.py`,
  `db_methods/pwa/classroom_layouts.py`,
  `vmshpwa/apps/staff/src/classroom-event-page.tsx`,
  `vmshpwa/packages/product/src/classroom-planning.tsx` и
  `vmshpwa/e2e/classroom-catalog.spec.ts`.
- Проверки инкремента: focused HTTP integration **5/5 PASS**; frontend unit
  **121 файлов / 648 PASS**; classroom production E2E **9/9 PASS** в Chromium,
  WebKit и Firefox; lint, typecheck и production build — PASS. Полный Python
  gate: **1763 PASS / 6 skip / 2 unrelated golden-corpus drift failures**;
  committed snapshots не обновлялись.

Промежуточные принятые вертикальные срезы:

- [Phase 7A: постоянный каталог аудиторий](../../../pwa_tests/reports/phase7-classroom-catalog.md);
- [Phase 7B: наследуемая схема аудиторий очного события](../../../pwa_tests/reports/phase7-classroom-layout.md);
- [Phase 7C: распределение школьников](../../../pwa_tests/reports/phase7-classroom-assignments.md);
- [Phase 7C: одноразовый Excel dry-run/import](../../../pwa_tests/reports/phase7-classroom-import.md).

- [x] Все Phase-7 migrations проходят up/down/up и integrity/schema gates;
      synthetic production-size rehearsal подтверждает 1500 очных школьников и
      15 комнат. Реальный owner-reviewed workbook apply остаётся production
      gate, а не частью hermetic suite:
      [`phase7-classroom-scale-and-print-boundary.md`](../../../pwa_tests/reports/phase7-classroom-scale-and-print-boundary.md).
- [x] One-time Excel preview/apply использует synthetic `IDd`, показывает
      blockers/counts/hash, атомарно создаёт plan и сохраняет только компактный
      receipt без строк/имён:
      [`phase7-classroom-import.md`](../../../pwa_tests/reports/phase7-classroom-import.md).
- [x] Online oral + written fallback + Staff result + Student final state:
      [`phase7-oral-e2e.md`](../../../pwa_tests/reports/phase7-oral-e2e.md).
- [x] Catalog normalization/archive/restore/optimistic conflict:
      [`phase7-classroom-catalog.md`](../../../pwa_tests/reports/phase7-classroom-catalog.md).
- [x] Assignment invariants, history, no-room incident, natural-sort balance и
      cross-group confirmation:
      [`phase7-classroom-assignments.md`](../../../pwa_tests/reports/phase7-classroom-assignments.md).
- [x] Fuzzy search, nullable age/grade/automatic strength, independent room
      averages и 1500-row scale входят в assignment/scale proof. Rating job
      parity остаётся источником Phase-9 analytics, а Phase 7 читает latest
      projection.
- [x] Layout/plan/oral local drafts переживают reload; batch single/bulk,
      cross-group confirm, explicit discard/success cleanup и version conflict
      покрыты API/UI/browser slices.
- [x] Historical immutability, stale/reassigning после archive/layout change и
      Teacher `403`:
      [`phase7-classroom-layout.md`](../../../pwa_tests/reports/phase7-classroom-layout.md),
      [`phase7-classroom-assignments.md`](../../../pwa_tests/reports/phase7-classroom-assignments.md).
- [x] Delivery preview/send, immutable recipient snapshot, PWA/Telegram matrix,
      failed-only retry, no-auto-resend, partial report и отсутствие Family
      delivery:
      [`phase7-classroom-delivery-e2e.md`](../../../pwa_tests/reports/phase7-classroom-delivery-e2e.md),
      [`phase8-classroom-telegram-transport.md`](../../../pwa_tests/reports/phase8-classroom-telegram-transport.md),
      [`phase8-classroom-delivery-observability.md`](../../../pwa_tests/reports/phase8-classroom-delivery-observability.md).
- [x] Join secret authorization, explicit reveal и `no-store`:
      [`phase7-oral-windows.md`](../../../pwa_tests/reports/phase7-oral-windows.md).
- [ ] Storybook component/page interactions и a11y зафиксированы в
      [`phase7-consolidated-gates-2026-08-03.md`](../../../pwa_tests/reports/phase7-consolidated-gates-2026-08-03.md),
      но общий visual diff всё ещё требует принятия владельцем; snapshots не
      обновлялись.
- [x] Последний успешный production-build Playwright: classroom **9 PASS** и
      oral **3 PASS** в Chromium/WebKit/Firefox. Повтор 3 августа 2026 года
      заблокирован macOS browser launcher до выполнения assertions и честно не
      считается новым PASS.
- [x] Граница v1 с `a11`–`a14` и персональная recipient semantics зафиксированы:
      Staff plan управляет PWA/Telegram состоянием, внешний workbook остаётся
      print source of truth до второй версии:
      [`phase7-classroom-scale-and-print-boundary.md`](../../../pwa_tests/reports/phase7-classroom-scale-and-print-boundary.md).
- [ ] Реальный operational rehearsal «ранняя рассылка → поздние mode changes →
      новая confirmed version → final print» остаётся обязательным до
      production cutover от workbook. Software flow до новой явной рассылки
      уже покрыт E2E.
- [x] Historical Telegram regression и legacy-compatible Zoom/result behavior
      входят в общий Python/Telegram gate; новый oral path не создаёт второй
      ledger.
- [x] Contracts, API/domain docs, runbook, known limitations и актуальная
      acceptance matrix:
      [`classroom-and-oral-workflow.md`](../../docs/classroom-and-oral-workflow.md),
      [`phase7-consolidated-gates-2026-08-03.md`](../../../pwa_tests/reports/phase7-consolidated-gates-2026-08-03.md).

## Многокурсовый инкремент Phase 7

Classroom layout/assignment plan принадлежит `in_person_event`, которое выбирает concrete group lessons разных курсов и номеров. Новый draft полностью наследует последние confirmed комнаты и student assignments каждой выбранной группы; admin корректирует только изменения. Инвариант «одна аудитория — одна группа» сохраняется.

Дополнительный proof: composition/inheritance API, неучаствующие группы не копируются, номера занятий могут различаться, course collisions дают warning, story `Product/Classrooms--multi-course-inherited-event` и `Pages/Staff--multi-course-classroom-event`.


## Live marking — 9 сентября 2026

Реализованы Staff `/in-person` и новый `/oral`: общий редактор, durable undo,
посещение, атомарный учительский перенос, Zoom-сессии/реакции/похвала и
синхронизация через WS. Решения: `vmshpwa/docs/live-marking.md`;
реализация: `apps/staff/src/live-marking-page.tsx`, `models/pwa/live_marking.py`,
`migrations/0087.pwa_live_marking.sql`.

Gates: 45 focused Python, 21 legacy, 9 production E2E (три браузера), 5 Storybook
с axe и нагрузкой 200×50; TypeScript, targeted ESLint и production build проходят.
Полные наборы: Python 1866 PASS / 6 SKIP / 5 прежних FAIL; frontend 723 PASS /
3 прежних FAIL. Все 8 failures воспроизведены на исходном HEAD.
Исправлена изоляция аналитической БД тестов; возможное влияние ранних прогонов
на прежний общий файл описано в `pwa_tests/reports/live-marking.md` вместе с
логами, ограничениями и мобильными снимками.
10 сентября 2026 владелец разрешил commit и push в текущую ветку `vmshpwa`.


## Компактный live-приём — 10 сентября 2026, проверено

По замечаниям владельца перерабатывается плотность Zoom и мобильного очного
экрана. Полноширинные карточки Zoom отклонены; задачи размещаются сеткой,
условия открываются отдельным действием. На телефоне ФИО ограничено 112 px,
селекторы очного занятия убраны в настройки. Контракт и реализация:
[контракт](../../docs/live-marking.md),
[сетка](../../apps/staff/src/live-marking-grid.tsx),
[страница](../../apps/staff/src/live-marking-page.tsx),
[условие](../../apps/staff/src/live-marking-condition.tsx).
Backend: **11 passed**; Storybook/axe: **6 passed**; Chromium/WebKit/Firefox:
**9 E2E passed** на финальной production-сборке. TypeScript, ESLint, Prettier,
Ruff прошли. Снимки mobile/desktop/light/dark просмотрены;
[отчёт и доказательства](../../../pwa_tests/reports/live-marking-compact.md).
Визуальное принятие владельцем остаётся открытым.
10 сентября владелец разрешил commit и push этого изменения в `vmshpwa`.
