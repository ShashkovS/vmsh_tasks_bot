# Этап 10. Администрирование данных, bulk workflows и отказ от Google

## Результат

Admin из Staff импортирует Excel, создаёт/правит пользователей и task settings, показывает отчёт об ошибочных строках и полностью заменяет workflow листов «Задачи»/«Старые». Остальные Google/external scripts продолжают работать до отдельного полного cutover своего процесса.

Дизайн-контракт этапа: [dense tables, metadata/publication controls, Staff admin pages и Storybook stories](18-design-implementation-map.md#phase-10-design).

## Объём Staff

- Users: search/filter, create/edit любого поля кроме `id`, block/archive, group, allowed groups, online mode, family account/link, credential/token reset workflow. Hard delete отсутствует.
- Groups/season: active/default/system flags, display/order, score weight, self-switch policy, fourth/future levels; per-group Telegram channel ID/title/enabled/verified state. Bot token не находится в group row или browser payload; verification выполняет backend.
- Teacher permissions by group/capability.
- Два независимых account batch flow с TSV/CSV copy-paste и preview:
  Student — surname, name, optional patronymic/birth date/grade, login и
  Telegram-token password; Family — name, login/password, comma-separated
  emails и child logins. Login conflict получает предложенный случайный `-NN`.
  Valid rows применяются, invalid rows перечисляются в receipt.
- Отдельный enrollment batch `login, course, allowed_groups` назначает доступ к
  одному курсу за запуск; тот же flow повторяется для дополнительных курсов.
  Active group выбирается не по порядку ячеек TSV, а как первая доступная группа
  по `groups.sort_order`, затем стабильно по short code и legacy `group_id`.
  Новое зачисление начинается online. Первое зачисление также синхронизирует
  единственные legacy `users.group_id/allowed_groups`, чтобы Telegram-бот
  продолжал работать; дополнительные курсы эти поля не перезаписывают.
- Task metadata TSV grid and version conflicts, включая отдельный task type (`test|written|oral`), answer type и checker trusted-admin surface. Task/answer type редактируются dropdown-ячейками, но прямоугольная TSV copy/paste работает так же, как в Google Sheets. Legacy `Письменно<-Устно` при migration явно отображается в canonical oral с доступной письменной сдачей.
- Grid/import сохраняет точную семантику `title`, `prob_type`, `ans_type`, `ans_validation`, `validation_error`, `cor_ans`, `cor_ans_checker`, `wrong_ans`, `congrat`. `cor_ans` может содержать много `;`-separated допустимых ответов; `SELECT_ONE.ans_validation` — список видимых labels, а для остальных типов непустое поле — regex override. Import preview различает пустое значение, inherited/default и явно заданный текст.
- Title должен оставаться коротким для Student/Telegram UI, но отличать задачу. Equal-title rows в одном `course_lesson` показываются как synonym candidates с impact preview; import не склеивает их автоматически и никогда не связывает разные курсы/занятия.
- Publication UI не имеет общего action «опубликовать уровень»: condition, hint и solution публикуются, планируются и откатываются независимо по каждому уровню.
- Несохранённые правки users/task metadata/import mapping сохраняются в account/entity/base-version-scoped `localStorage`; reload и server conflict не теряют их. После successful apply/receipt draft очищается.
- Credential email в v1 отправляют внешние скрипты по сохранённым plaintext
  provisioning values и Family email list; Staff mail sender не входит в v1.
  Импорт очных/устных результатов из `a19` и печатные spreadsheet flows
  откладываются на последующие версии.
- Surveys не переносятся. Email workflow относится ко второй/третьей версии. Export пользователей в первой версии не нужен.
- Staff statistics/audit of writes and imports. Teacher continues to have no broadcasts/classrooms/audit.

## Migration and compatibility

Logical migration: `pwa_normalized_groups_imports` plus only measured indexes/read models.

Potential tables:

- `data_imports(id, public_id, kind, source_asset_id, state, mapping_json, diagnostics_json, created_by, created_at, applied_at, version)`;
- `data_import_rows(id, import_id, row_number, natural_key, input_json, normalized_json, state, error_codes_json, applied_object_type/id)`;
- normalized group membership/allowed group table only after choosing source of truth;
- audit events from phase model.

Never delete `allowed_groups`, legacy settings or Google path in the same deploy that first introduces new UI. Первой заменяется загрузка task settings из листов «Задачи» и «Старые» файла `_external_pipelines/ВМШ 2025-26, информация для бота ВМШ — prod.xlsx`. Используется expand → dual-read/write/report → cutover → cleanup.

## Google replacement matrix

Для каждого current Google loader/import:

1. Owner and invocation path.
2. Sheet columns/types/validation/defaults.
3. Domain table/readers/writers affected.
4. Staff screen or file import replacement.
5. Golden input and expected DB diff.
6. Parallel-run report on protected production SQLite copy; DB/WAL/SHM хранятся и запускаются только в изолированном локальном окружении.
7. Cutover flag and rollback command.
8. Date after which credential/import is removed from startup/deploy.

Reference doc: `vmshpwa/docs/google-migration-roadmap.md`. Первая replacement matrix подробно покрывает листы «Задачи»/«Старые» и вызывающие их скрипты. `a00_dates`, `a01`, `a02`, `a03`, `a11`, `a18`, `a19`, `a23`, `a52–a54` могут остаться legacy bridge после v1, но для каждого уже названы конечный внутренний owner, вход/выход, parity gate и следующий этап решения; «не в v1» не означает «навсегда внешний».

## Security

- `cor_ans_checker` editor admin-only, clear trusted-code warning, full revision/audit/diff and optional stored examples. Сохраняется нынешняя trusted-admin `exec` модель; отсутствие examples не блокирует урок, а недонастроенные ответы получают pending и последующую admin-перепроверку.
- Bulk import никогда не принимает type/role/permission silently по неизвестному value.
- Uploads имеют явные ограничения размера/типа; TSV paste интерпретирует ячейки как данные и не исполняет spreadsheet formulas.
- Historic migration 0038/other embedded credentials are audited and removed/rotated by separate security procedure; docs/fixtures never reproduce them.
- PII exports require explicit action and are absent from Sentry/normal logs.

## Tests

- Import parser/normalization per row, duplicate natural keys, partial invalid, encoding and TSV copy/paste as data.
- Metadata characterization: короткие/equal titles, blank/custom validation, visible `SELECT_ONE` labels, multi-answer `cor_ans`, contextual messages, checker revisions и exact dry-run diff против legacy workbook.
- Valid-row apply is repeatable/idempotent; invalid rows do not block valid ones and получают понятный report.
- Permissions matrix all routes/mutations; audit before/after without secrets.
- Telegram destination: canonical Bot API ID round-trip, >32-bit/negative IDs, duplicate channel rejection, missing admin/post permission, optimistic conflict и audit старого/нового destination без token.
- Differential reports vs current Google/external pipeline on the protected production-size copy.
- 1500 students metadata/users grid virtualization and search performance.
- Storybook dense Staff pages desktop + mobile essential review; import diagnostics/conflicts/forbidden.
- Admin draft persistence: reload, account isolation, optimistic conflict, explicit discard и cleanup after apply.
- Playwright upload → preview → apply → use changed student/group in Student; Google/Telegram network blocked.

## Критерии приёмки

- Листы «Задачи» и «Старые» имеют полный Staff/UI/import replacement, named owner и подтверждённый cutover; остальные Google workflows остаются явно перечисленными legacy paths.
- App factory/deploy не загружает Google settings for PWA; legacy bot path can remain explicitly enabled.
- Dry-run diff объясняет каждое создаваемое/изменяемое/пропущенное значение.
- Валидные строки импортируются, невалидные пропускаются и перечисляются в отчёте; пропущенная строка не оставляет частично записанных данных.
- Permission changes вступают в силу и отзывают доступ/session according policy.
- Каждый active course/group binding имеет verified canonical destination и явный purpose; news inheritance/material target replacement не используют глобальный fallback, а изменение binding не переписывает binding/chat/message IDs исторических публикаций.
- Reload/обновление SPA не теряет несохранённые правки grid/import; новый server version не перезаписывается молча.
- Cutover обратим и имеет parity report; при rollover автоматически переносятся только teachers, остальные данные импортируются заново.

## Пруфы завершения этапа

Промежуточный proof управления уже существующими Student/Family-аккаунтами:
[`pwa_tests/reports/phase10-account-lifecycle-2026-07-30.md`](../../../pwa_tests/reports/phase10-account-lifecycle-2026-07-30.md).
Создание, привязка, отзыв связи и Staff UI Family-аккаунтов подтверждены
отдельными отчётами:
[`backend/API`](../../../pwa_tests/reports/phase10-family-account-backend.md) и
[`frontend/Storybook/E2E`](../../../pwa_tests/reports/phase10-family-account-ui.md).
Они не закрывают создание Student-аккаунта, bulk import и остальные gates этапа.
Индивидуальное создание Student web-входа из уже существующего legacy-пользователя
подтверждено в
[`phase10-student-account-creation.md`](../../../pwa_tests/reports/phase10-student-account-creation.md):
Staff передаёт только логин, а backend хеширует текущий токен общего с Telegram-ботом
аккаунта. Production E2E создаёт аккаунт для отдельного unprovisioned Student и
входит с этим токеном через настоящий Student login. Directory предлагает
канонический login по фамилии и дню рождения только при отсутствии коллизии;
collision/invalid identity остаются явным ручным решением. Небольшие ежедневные
пачки создаются из Staff через тот же одиночный API; выбранные строки переживают
reload в account-scoped `localStorage`, а частичные ошибки не теряют выбор.
Storybook: `Pages/Staff--student-account-batch-creation`; production E2E:
`Admin creates a small Student account batch and keeps selection across reload`.
Первая рабочая версия searchable Staff audit подтверждена в
[`phase10-staff-audit.md`](../../../pwa_tests/reports/phase10-staff-audit.md):
реальный `/staff/audit`, admin-only API, request ID, безопасный before/after,
стабильный cursor и транзакционные события account/family/enrollment/problem-import.
Storybook: `Pages/Staff/Audit--SearchableTimeline`, `--EmptySearch`; production E2E
проверяет admin/teacher во всех трёх браузерах. Полное покрытие остальных Staff
mutations явно оставлено следующим audit-инкрементом и не маскируется этим proof.
Следующий audit-инкремент добавил транзакционные `course.created/updated` и
`group.created/updated`; отдельный rollback-test доказывает, что каталог не
сохраняется без соответствующей audit-строки. Следующий инкремент добавил
`telegram_binding.created/updated/disabled/draft_restored/verified`, включая
старый/новый destination без bot token и атомарный rollback при сбое audit.
Следующий инкремент добавил атомарные `problem_synonym.merged/split`: audit хранит
компактное резюме, а детальная membership-history остаётся источником истины;
rollback-test не допускает частично сохранённого объединения. Расписания и прочие
Staff writes всё ещё перечислены в proof как открытые. Для расписаний атомарная
точка пока находится внутри старого `PwaContentRepository`, поэтому второй
неатомарный audit-write сознательно не добавлен.
Следующий инкремент добавил атомарный `staff_scope.replaced`: компактный audit
показывает старый и новый набор публичных course/group IDs, а append-only
`staff_scopes` остаётся полной историей. Rollback-test не допускает grant/revoke
без audit-строки.
Первый course-scoped Staff statistics slice подтверждён в
[`phase10-staff-statistics.md`](../../../pwa_tests/reports/phase10-staff-statistics.md):
реальный `/staff/statistics` читает последний завершённый immutable analytics
snapshot, ограничивает teacher действующими `staff_scopes` и отдаёт только
анонимные агрегаты без student IDs и позиции ребёнка в группе. Storybook:
`Pages/Staff/Statistics--HistoricalCourse`, `--NoCompletedRun`; production-build
E2E прошёл в Chromium, WebKit и Firefox. Это не закрывает live submission/
pending counters, teacher workload, oral/reach и scheduler расчёта — они явно
остаются следующими статистическими инкрементами Phase 10.
Рабочая Staff-сводка подтверждена в
[`phase10-staff-dashboard.md`](../../../pwa_tests/reports/phase10-staff-dashboard.md):
`/staff/` больше не показывает prototype counters, а читает scoped логические
кейсы проверки, ожидающие вопросы, независимые публикации, устные окна и
admin-only ошибки рассылки аудиторий. Storybook:
`Pages/Staff/Dashboard--CurrentWeek`, `--TeacherScoped`,
`--NoCurrentLessons`; production-build E2E прошёл в Chromium, WebKit и Firefox.
Сводка не вводит отдельный read-model и не закрывает полный teacher workload или
операционное принятие Google cutover.

Полный software-path замены листов «Задачи»/«Старые» подтверждён сводным proof
[`phase10-problem-workbook-replacement.md`](../../../pwa_tests/reports/phase10-problem-workbook-replacement.md):
course-scoped XLSX preview, понятные diagnostics, advisory synonym candidates,
явный apply, idempotent receipt, guarded rollback, Staff interaction и
production-build Playwright. Differential rehearsal настоящего workbook против
изолированной копии `db/vmsh.db` получил 1813 `unchanged` и ноль расхождений.
Это закрывает реализацию task-settings import, но не подменяет владельческое
подтверждение cutover после реального недельного цикла. Software workflow
первичного bulk import новых школьников также состоит из трёх
отдельных preview/apply batch: Student accounts, Family accounts и per-course
enrollment. Владельческая summer rehearsal и внешняя email-рассылка
остаются deployment-действиями, а не скрытой частью apply.

- [x] Revision/migrations for problem import: `0074.pwa_problem_import_receipts`;
      up/down/up, integrity и rollback подтверждены в
      [`phase10-problem-import-apply.md`](../../../pwa_tests/reports/phase10-problem-import-apply.md).
- [x] Google replacement matrix перечисляет все шесть листов, ручные команды,
      SQLite side effects, состояние новой замены и rollback/cutover boundary:
      [`google-loader-inventory-and-cutover.md`](../../docs/google-loader-inventory-and-cutover.md).
      Структурный regression-test:
      [`test_google_loader_inventory.py`](../../../pwa_tests/test_google_loader_inventory.py).
- [x] `/update_all` fail-closed после первого частичного cutover: один legacy
      config boolean проверяется до Google read/SQLite write, handler не выполняет
      побочные действия, а отдельные доменные recovery-команды остаются доступны.
      Proof:
      [`phase10-google-bulk-cutover-guard-2026-08-03.md`](../../../pwa_tests/reports/phase10-google-bulk-cutover-guard-2026-08-03.md).
- [x] Protected production-copy task-workbook parity:
      [`phase10-problem-import-parity.md`](../../../pwa_tests/reports/phase10-problem-import-parity.md)
      и [JSON](../../../pwa_tests/reports/phase10-problem-import-parity.json):
      1813 unchanged, zero diagnostics; source DB unchanged.
- [x] Task metadata field-by-field parity and synonym candidates without
      physical rewrite:
      [`phase10-problem-workbook-replacement.md`](../../../pwa_tests/reports/phase10-problem-workbook-replacement.md).
- [x] Hermetic users/groups/family/permissions preview/apply: три отдельных
      account/enrollment batch, включая group order и legacy Telegram sync,
      подтверждены в
      [`phase1-course-enrollment-batch-2026-08-03.md`](../../../pwa_tests/reports/phase1-course-enrollment-batch-2026-08-03.md).
      Owner-run summer/production rehearsal и внешняя email-рассылка всё ещё
      выполняются отдельно.
- [x] Problem import security/idempotency/transaction tests:
      [`phase10-problem-import-apply.md`](../../../pwa_tests/reports/phase10-problem-import-apply.md).
- [x] Admin local draft reload/isolation/conflict/cleanup tests: Family-form
      reload/isolation/secret exclusion/cleanup подтверждены в
      [`phase10-family-account-ui.md`](../../../pwa_tests/reports/phase10-family-account-ui.md);
      metadata grid account/revision scope, reload, `409`, explicit discard и
      receipt cleanup — в
      [`phase10-metadata-grid-drafts-2026-08-03.md`](../../../pwa_tests/reports/phase10-metadata-grid-drafts-2026-08-03.md).
      Upload bytes по-прежнему требуют повторного выбора файла: бинарный upload не
      маскируется текстовым `localStorage`-черновиком.
- [x] 1500-row performance + SQL plans:
      [`phase10-directory-performance.md`](../../../pwa_tests/reports/phase10-directory-performance.md).
- [ ] Storybook dense admin states/a11y/visual approval: `<ids/paths>`.
- [x] Problem-workbook Playwright: preview в Chromium/Firefox/WebKit, reversible
      mutation в одном browser над общей seeded SQLite; Google/Telegram network не
      используется. См.
      [`phase10-problem-workbook-replacement.md`](../../../pwa_tests/reports/phase10-problem-workbook-replacement.md).
- [ ] Cutover/rollback/security credential runbook and acceptance: `<paths/issues/name/date>`.

Backend typed replacement `_BotSettings` реализован отдельным промежуточным
инкрементом: migration `0077`, четыре однозначно course-owned enum, admin-only
GET/PUT, optimistic ETag и атомарный audit. Глобальный `reg_mode`, исключённая
game и удалённый `save_sol_mode` не протаскиваются в course JSON. Staff UI,
Telegram compatibility read и production backfill/cutover остаются открыты.
Proof:
[`phase10-course-runtime-settings-backend-2026-08-03.md`](../../../pwa_tests/reports/phase10-course-runtime-settings-backend-2026-08-03.md).

## Многокурсовый инкремент Phase 10

Staff получает полный каталог CRUD/archive курсов и групп, enrollment/access/scopes, schedule overrides, Telegram bindings и synonym impact preview. Google replacement imports становятся course-aware и не используют один глобальный level context.

Дополнительный proof: optimistic conflicts, duplicate codes only within course, teacher `403`, import dry-run/rollback и stories `Product/Staff-admin--course-and-group-catalog`, `--independent-schedules`, `--telegram-bindings`.
