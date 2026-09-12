# Инвентаризация Google loader и границы cutover

Этот документ фиксирует весь текущий Google Sheets loader, его реальные точки
запуска и состояние замены. Он описывает наблюдаемый код, а не объявляет
production cutover. Общий план отказа находится в
[roadmap отказа от Google](google-migration-roadmap.md), а требования этапа — в
[Phase 10](../dev/development-plan/14-phase-10-admin-and-google-exit.md).

## Единственная точка подключения

[`SpreadsheetLoader`](../../helpers/loader_from_google_spreadsheets.py)
открывает одну таблицу по `google_sheets_key` и читает шесть листов. Первые две
строки каждого листа отбрасываются, оставшиеся строки сопоставляются колонкам по
позиции. [`FromGoogleSpreadsheet`](../../models/spreadsheets.py) нормализует
значения и вызывает существующие SQLite-методы. Отдельного фонового sync нет.

Google может быть вызван только legacy Telegram-контуром:

- startup [`apps/tg_bot.py`](../../apps/tg_bot.py) настраивает loader и вызывает
  `update_from_google_if_db_is_empty`; автоматическая загрузка происходит только
  если в SQLite нет ни одного преподавателя;
- Telegram-команды из
  [`handlers/admin_handlers.py`](../../handlers/admin_handlers.py) запускают
  полное либо доменное обновление вручную;
- прямой запуск
  [`helpers/loader_from_google_spreadsheets.py`](../../helpers/loader_from_google_spreadsheets.py)
  только читает таблицу и печатает количества строк.

PWA app factory, unit-тесты и E2E этот модуль не импортируют и credentials не
читают. `update_all` выполняет листы последовательно в порядке «Группы»,
«Задачи», «Школьники», «Учителя», `_BotUIMsgs`, `_BotSettings`; общей транзакции
между листами нет. Поэтому legacy-команда может оставить частично обновлённую
базу и не считается rollback-механизмом.

## Лист «Задачи»

**Текущий владелец и запуск.** `SpreadsheetLoader.get_problems` вызывается
`FromGoogleSpreadsheet.update_problems` из Telegram-команд `/update_problems`
и `/up`; также входит в `/update_all` и bootstrap пустой базы.

**Позиционные колонки.** `group_id`, `lesson`, `prob`, `item`, `title`,
`prob_text`, `prob_type`, `ans_type`, `ans_validation`, `validation_error`,
`cor_ans`, `cor_ans_checker`, `wrong_ans`, `congrat`.

**Нормализация и side effects.** Пустые строки пропускаются; обязательны
`group_id` и известный `prob_type`; `ans_type` проверяется для тестовой задачи;
непустой `ans_validation` должен компилироваться как regex. Запись выполняется
UPSERT в legacy `problems` по `(group_id, lesson, prob, item)`, затем обновляются
lesson projection и legacy `problems.synonyms`.

**Новая замена.** Staff `/staff/content` использует
[`problem_import_routes.py`](../../apps/pwa_api/problem_import_routes.py) для
XLSX preview/apply/rollback и
[`content_routes.py`](../../apps/pwa_api/content_routes.py) для matching,
metadata grid и независимой публикации condition/hint/solution. Импорт
course-scoped и не склеивает synonym candidates автоматически.

**Golden/parity.** Реальный workbook и защищённая копия SQLite дали 1813
`unchanged`, ноль diagnostics и ноль необъяснённых различий. Точный вход,
hashes и DB diff зафиксированы в
[`phase10-problem-workbook-replacement.md`](../../pwa_tests/reports/phase10-problem-workbook-replacement.md)
и
[`phase10-problem-import-parity.md`](../../pwa_tests/reports/phase10-problem-import-parity.md).

**Cutover и rollback.** Software gate пройден, production owner gate не пройден.
До объявления даты source of truth остаётся legacy workflow. После одного
полного реального недельного цикла Staff становится write path; rollback одной
Staff-операции выполняется endpoint
`POST /staff/api/v1/problem-imports/{receiptPublicId}/rollback`. В период
наблюдения аварийный возврат к Google — только явная owner-команда
`/update_problems` после backup и просмотра Staff/legacy diff; автоматического
fallback нет. Credentials для этого домена удаляются только вместе с последним
из остальных пяти Google loader.

## Лист «Школьники»

**Текущий владелец и запуск.** `SpreadsheetLoader.get_students` вызывается
`FromGoogleSpreadsheet.update_students` из `/update_students`, `/us`,
`/update_all` и bootstrap пустой базы.

**Позиционные колонки.** `surname`, `name`, `token`, `group_id`, `online`,
`grade`, `birthday`, `allowed_groups`.

**Нормализация и side effects.** Строка принудительно получает Student type,
пустое отчество и `chat_id = NULL`; grade преобразуется в integer, режим — через
legacy decoder с fallback в online, `allowed_groups` нормализуется в
semicolon-строку. Если active group не входит в allowed groups, выбирается
первая разрешённая группа. `users` UPSERT-ится по token, затем Student state
переводится в `GET_TASK_INFO`.

**Новая замена.** Staff directory уже поддерживает индивидуальное и небольшое
пакетное создание web-входа, Family link/account lifecycle и course enrollment
editing через
[`admin_account_routes.py`](../../apps/pwa_api/admin_account_routes.py) и
[`admin_enrollment_routes.py`](../../apps/pwa_api/admin_enrollment_routes.py).
Первичный import новых школьников теперь разделён на Student account batch,
Family account batch и отдельный per-course enrollment batch
`login, course, allowed_groups`. Preview показывает active group: первая
доступная группа по `groups.sort_order`, затем по short code и legacy
`group_id`; порядок ячеек TSV на выбор не влияет.

**Golden/parity.** Hermetic HTTP proof отдельно показывает create/skip,
collision логинов, invalid token и course enrollment; реальные credentials не
попадают в proof:
[`phase1-course-enrollment-batch-2026-08-03.md`](../../pwa_tests/reports/phase1-course-enrollment-batch-2026-08-03.md).
Production import остаётся owner-run действием.

**Cutover и rollback.** Статус `legacy bridge`. `/update_students` остаётся
ручным recovery path до production rehearsal нового импорта. Cutover и удаление
Google credentials для этого листа запрещено удалять до доказанного repeatable
apply/rollback нового batch workflow и owner-run cutover rehearsal.

## Лист «Учителя»

**Текущий владелец и запуск.** `SpreadsheetLoader.get_teachers` вызывается из
`/update_teachers`, `/ut`, `/update_all` и bootstrap пустой базы.

**Позиционные колонки.** `surname`, `name`, `middlename`, `token`, `online`,
`group_id`, `allowed_groups`.

**Нормализация и side effects.** Строка получает Teacher type; `chat_id`, grade
и birthday очищаются; mode и allowed/active group нормализуются так же, как у
Student. `users` UPSERT-ится по token. Текущий импорт не моделирует отдельные
course/group capabilities и не пишет новый audit.

**Новая замена.** Course/group scopes уже меняются атомарно через
[`staff_access_routes.py`](../../apps/pwa_api/staff_access_routes.py), однако
создание и импорт самих Teacher identities пока не имеют полного Staff
preview/apply workflow.

**Golden/parity.** Нужен синтетический набор create/update/revoke с проверкой
teacher `403`, course-wide/group scopes и сохранением Telegram linkage. До него
нет основания отключать лист.

**Cutover и rollback.** Статус `legacy bridge`. Текущий ручной recovery —
`/update_teachers`; он не откатывает отдельную строку. Новый cutover требует
импорт identities, scoped diff, audit и отдельную процедуру отзыва доступа.

## Лист «Группы»

**Текущий владелец и запуск.** `SpreadsheetLoader.get_groups` вызывается из
`/update_groups`, `/ug`, `/update_all` и bootstrap пустой базы. После импорта
Telegram router заново регистрирует команды переключения групп.

**Позиционные колонки.** `group_id`, `short_code`, `broadcast_code`,
`tg_command`, `public_name`, `conditions_url`, `tasks_header_template`,
`switch_message`, `sort_order`, `is_active`, `is_default`,
`allow_self_switch`, `is_system`, `score_weight`.

**Нормализация и side effects.** Обязательны уникальные `group_id`,
`short_code`, `tg_command` и `broadcast_code`; boolean/integer/float значения
имеют явные defaults. Legacy `groups` UPSERT-ится по `group_id`, отсутствующие
в листе группы не удаляются.

**Новая замена.** Course/group catalog CRUD находится в
[`admin_course_routes.py`](../../apps/pwa_api/admin_course_routes.py), schedule
inheritance — в
[`admin_schedule_routes.py`](../../apps/pwa_api/admin_schedule_routes.py), а
course/group Telegram destinations — в
[`telegram_binding_routes.py`](../../apps/pwa_api/telegram_binding_routes.py).
Это покрывает новую многокурсовую модель, но ещё не является field-by-field
заменой legacy bot-only полей `broadcast_code`, `tg_command`,
`conditions_url`, `tasks_header_template` и `switch_message`.

**Golden/parity.** Нужен mapping report: какие legacy поля становятся course,
group, schedule или Telegram binding, а какие остаются compatibility data для
бота. Проверка обязана сохранить legacy `group_id` и не создавать cross-course
collision по одному short code.

**Cutover и rollback.** Статус `parallel/partial`. Staff catalog уже рабочий,
но `/update_groups` остаётся recovery path для Telegram-only полей. Полный
cutover возможен только после mapping report, повторной регистрации bot commands
из нового источника и production rehearsal.

## Лист `_BotUIMsgs`

**Текущий владелец и запуск.** `SpreadsheetLoader.get_ui_messages` вызывается
из `/update_ui_messages`, `/update_all` и bootstrap пустой базы.

**Позиционные колонки.** `key`, `value`.

**Side effects.** Непустые пары UPSERT-ятся в `z_ui_messages` по key с новым
`change_ts`; отсутствующие keys не удаляются. В текущей production-size базе
есть 215 keys. Значения являются локализуемыми Telegram/UI-текстами, а не PWA
content publications.

**Новая замена.** В v1 тексты остаются hardcoded/versioned code resources и не
получают Staff editor. В v2 вводятся i18n resources и admin-настройка текстов
для доступных языков.

**Cutover и rollback.** Статус `legacy bridge`. Recovery — повторный
`/update_ui_messages`; построчного rollback и удаления нет. Cutover v1 требует
characterization используемых keys и явного code mapping, а не нового editor.

## Лист `_BotSettings`

**Текущий владелец и запуск.** `SpreadsheetLoader.get_bot_settings` вызывается
из `/update_bot_settings`, `/update_all` и bootstrap пустой базы. Команда после
записи сообщает, что для применения некоторых значений требуется restart.

**Позиционные колонки.** `key`, `value`.

**Side effects.** Непустые пары UPSERT-ятся в `z_settings` по key с новым
`change_ts`; отсутствующие keys не удаляются. В текущей production-size базе
наблюдаются семь keys: `game_mode`, `prev_problems_mode`, `rate_limit`,
`reg_mode`, `result_mode`, `save_sol_mode`, `verdict_mode`.

**Новая замена.** Backend storage и admin-only typed GET/PUT реализованы для
четырёх course-owned keys: `verdict_mode`, `result_mode`,
`prev_problems_mode`, `rate_limit`. API использует полные enum-значения,
optimistic version и атомарный audit; неизвестный key/value блокируется.
`reg_mode` остаётся глобальным legacy onboarding до отдельного отказа от
регистрации через bot, game не входит в v1. `save_sol_mode` удаляется без
replacement: новый pipeline всегда хранит content и submissions в S3. Staff UI
и compatibility read Telegram adapter ещё не реализованы.

**Cutover и rollback.** Статус `parallel/partial`. Recovery — исправить значение
и повторить `/update_bot_settings`, затем при необходимости перезапустить bot.
Cutover проходит только после Staff UI, compatibility read Telegram adapter,
production mapping первого курса и owner rehearsal.

## Полная загрузка `/update_all`

`/update_all` не является седьмым источником данных: это последовательная
композиция шести loader выше. Её нельзя использовать после доменного cutover,
потому что она без preview перезапишет уже перенесённый домен Google-данными.
Команда теперь имеет простой fail-closed guard
`allow_google_update_all` в legacy JSON config:

- до первого доменного cutover значение остаётся `true` и историческое
  поведение не меняется;
- при первом подтверждённом частичном cutover владелец deploy-конфига ставит
  `false` и перезапускает Telegram contour;
- `FromGoogleSpreadsheet.update_all()` проверяет guard **до** чтения Google и
  любых записей SQLite;
- Telegram `/update_all` сообщает об отказе и не перерегистрирует команды
  групп;
- отдельные `/update_problems`, `/update_students`, `/update_teachers`,
  `/update_groups`, `/update_ui_messages` и `/update_bot_settings` остаются
  явными recovery-командами до cutover соответствующего домена.

Guard намеренно является одним boolean, а не новым registry/table: после
первого частичного cutover любая композиция всех шести листов уже небезопасна.
Он также запрещает автоматический empty-DB bootstrap через `update_all`; после
cutover пустую production SQLite следует восстанавливать из backup, а не
собирать частично из устаревшей Google-таблицы.

Операционные условия guard:

1. PWA не вызывает `/update_all` и не загружает Google.
2. До первого cutover `allow_google_update_all=true` означает только сохранение
   legacy behavior, а не автоматический rollback.
3. После первого cutover deployment не продолжается, пока в service config не
   зафиксировано `allow_google_update_all=false`.
4. Перед отдельным ручным recovery создаётся SQLite backup и записывается,
   какой именно домен будет затронут.

Исполняемое доказательство:
[`phase10-google-bulk-cutover-guard-2026-08-03.md`](../../pwa_tests/reports/phase10-google-bulk-cutover-guard-2026-08-03.md).

## Удаление credentials

Service-account JSON и `google_sheets_key` общие для всех шести листов. Поэтому
успех task-settings cutover сам по себе не позволяет удалить credentials.
Удаление допустимо только когда каждый лист имеет внутреннего owner, green
parity/rehearsal, рабочий rollback и подтверждённую дату cutover. До этого
credentials остаются только в legacy Telegram startup; PWA deploy/test контур
их не читает.
