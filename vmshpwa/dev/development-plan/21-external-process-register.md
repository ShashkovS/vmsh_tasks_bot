# Реестр внешних процессов и недельных операций

Статус: Phase 0, baseline на 27 июля 2026 года. Машиночитаемый источник —
[`external-process-register.v1.json`](../../../pwa_tests/fixtures/external-process-register.v1.json),
его структура и ссылки проверяются
[`test_external_process_register.py`](../../../pwa_tests/test_external_process_register.py).

## Для чего нужен реестр

Это не предложение немедленно переписать все скрипты. Реестр фиксирует реальный
операционный граф до миграции: кто запускает действие, что служит входом, куда
оно пишет, как заметить частичный сбой, можно ли повторить запуск и чем
восстанавливаться. Пока целевой этап не доказал parity, recovery и явно
подтверждённый cutover, активный legacy-путь остаётся рабочим.

У каждого machine-process отдельно записаны `invocation` и
`upstreamProcessIds`. Если точное имя Telegram-команды, interpreter или внешний
sender отсутствуют в snapshot, реестр говорит об этом прямо: неизвестное имя не
подменяется выдуманной командой. Поля `inputs`–`recovery` описывают только
наблюдаемое текущее поведение. Будущие preview, audit, immutable receipts,
Family accounts и versioned revisions находятся только в `target`.

Реестр различает пять текущих состояний:

- `active_external` — используемый внешний скрипт или workflow;
- `active_automated` — используемая автоматическая/транзитивная операция;
- `manual_digital` — ручная операция в Telegram, почте, таблице или другом UI;
- `manual_physical` — печать, помещения, бумага, сканер и педагогическая работа;
- `legacy_reference` — материал другого проекта или исторический corpus: его
  изучают, но не импортируют в production.

Формулировки «Phase N» и «post-v1» описывают следующего владельца, а не
разрешение выключить старый путь. Времена ниже — наблюдаемый исторический
baseline конца прошлого сезона. В целевом продукте расписания принадлежат курсу
и группе; ни одно время не становится глобальной константой.

Отдельное поле `transitionState` классифицирует путь переноса:

- `legacy_bridge` — текущий внешний/ручной контур сохраняется параллельно и не
  имеет обещанного cutover в первой версии;
- `v1_cutover` — внутренний владелец и доказательства cutover входят в этапы
  1–11 первой версии;
- `later_internalization` — владелец и gate названы, но перенос сознательно
  назначен после первой версии.

Это не runtime-статус: `v1_cutover` не означает, что перенос уже выполнен.

## Текущий legacy-контур и целевая граница

На baseline 27 июля 2026 года математические TeX/PDF, инструкции, сканы и
рабочие копии примерно двух десятков Python-скриптов живут в общей
Dropbox-папке. Публикации в нескольких ученических и преподавательских
Telegram-каналах/группах в основном выполняются вручную либо через admin-команды
действующего бота. Старый сайт обновляется скриптами по FTP и редко требует
ручного доступа. Бот работает на отдельном сервере с общей SQLite; её резервные
копии несколько раз в день уходят к другому провайдеру. Это текущая
архитектура, а не описание уже существующих Staff API, versioned publication
records или Family provisioning.

Целевые Staff/PWA-процессы появляются только после доказательств соответствующей
фазы. Dropbox может остаться authoring source, Telegram и бот — параллельными
каналами, а старые scripts/site выключаются только отдельным подтверждённым
cutover.

## Границы приватности и доказательств

- `logs/events.jsonl` и его dated rotations содержат события двух настоящих
  рабочих недель и подтверждают weekly orchestration, письменную очередь,
  oral/Zoom и массовые действия. Это закрытый characterization source. Реестр
  хранит только путь-класс `logs` и агрегаты: JSONL payload с настоящими
  идентификаторами не копируется.
- Экспорт Telegram и workbook используются как закрытый characterization input.
  Имена, адреса, токены, `chat_id`, bucket names и message payload в реестр не
  переносятся.
- `_external_pipelines` — snapshot, а не production dependency. Скрипты читаются
  как спецификация observable behavior; новый код получает собственные fixtures
  и тесты.
- Dropbox, Google, FTP, production SQLite, бот, почта и Zoom не вызываются из
  unit/E2E. Разрешённые live integration используют только отдельные test
  resources и собственный префикс запуска.

Отдельный privacy-safe проход по полю `event` всех `logs/events.jsonl*` (без
чтения остальных значений в отчёт) подтвердил масштаб именно тех контуров,
которые есть в register: 11 078 выборов задачи, 7 503 тестовых ответа, 2 131
письменная сдача, 2 362 начала письменной проверки, 1 949 verdict, 3 338 Zoom
webhook/queue events, 214 admin commands, 58 завершённых broadcast, 19 data sync
и 540 смен групп. Эти числа — characterization corpus, не SLO и не пользовательская
статистика.

## Внешние системы

Машинный реестр задаёт только классы credentials, без значений:

- общая Dropbox-папка — TeX/PDF, сканы, инструкции и рабочие копии скриптов;
- Telegram bot плюс отдельные каналы/группы — личные действия, публикации и
  обсуждения;
- Google Sheets и локальные Excel-кондуиты — legacy configuration/import;
- esz и email sender — регистрация и письма;
- FTP/public site — старое web-представление условий и статистики;
- production host, общая SQLite и отдельный backup provider;
- Zoom и YouTube;
- школьные аудитории, принтер и сканер;
- локальный Python/LaTeX/Image/PDF toolchain;
- S3-compatible storage для целевого media pipeline.

## Активные процессы: поддержка и регистрация

### `support-email` — ответы на почту

- Владелец и запуск: организатор, при каждом входящем вопросе, постоянно.
- Вход/выход и side effect: письмо с контекстом → ответ; история остаётся во
  внешнем mailbox.
- Повтор/сбой/recovery: повтор — новое уточнение; неотправленное письмо или
  повторное обращение показывают сбой; восстановление через исходный thread.
- Следующий владелец: `post-v1-support`; email остаётся параллельным каналом,
  пока не появится надёжный internal inbox.

### `support-sos` — SOS-вопросы

- Владелец и запуск: преподаватели/организаторы, в течение активной недели.
- Вход/выход и side effect: общий либо problem-scoped вопрос → ответ в Telegram.
- Повтор/сбой/recovery: ответы дополняют историю; непросмотренный вопрос или
  send error возвращается в работу.
- Следующий владелец: Phase 6, PWA/Staff thread с Telegram adapter.

### `support-community-chat` — группа школьников и родителей

- Это ручное живое общение, а не очередь продукта. Исправление публикуется
  отдельным сообщением либо осознанным edit.
- Решение: `retain-parallel`; PWA не заменяет сообщество.

### `newcomer-applications` — сбор заявок

- Администратор несколько раз в неделю выгружает esz, сохраняет Excel и
  добавляет заявки из отдельной таблицы детей без московской прописки.
- Результат — объединённый кандидатский список; повтор требует дедупликации по
  исходным заявкам. Восстановление — отбросить непринятый merge и собрать снова.
- Следующий владелец: Phase 10 Staff import с dry-run.

### `newcomer-account-provision` — legacy-аккаунт школьника

- Текущий legacy-путь вручную создаёт логин и Telegram-токен-пароль школьника и
  пишет строку в лист `Школьники`. Family account сейчас этим действием не
  создаётся.
- Повтор без сверки существующего пользователя запрещён: он может неожиданно
  ротировать доступ. До импорта ошибку исправляют в листе; после импорта или
  рассылки требуется явная ротация и повтор следующих шагов.
- Только целевой Staff batch Phase 1 + Phase 10 создаёт одновременно Student и
  связанный отдельный Family account, audit и безопасный receipt.

### `newcomer-bot-import` — загрузка пользователей в бота

- Admin-команда переносит legacy sheet в общую SQLite.
- Проверки: import counts, уникальность и выборочная попытка входа. Повтор должен
  обновлять, а не создавать дубликаты.
- Следующий владелец: Phase 10 Staff batch API поверх общей доменной логики.

### `newcomer-credentials-mailing` — письма с доступом

- Вход: проверенный provisioning batch, адреса и вручную актуализированная
  инструкция. Side effect: персональные письма с данными доступа.
- Повторяется только failed/явно выбранным адресатам; при подозрении на раскрытие
  сначала ротируется token.
- Следующий владелец: `post-v1-email`, с preview, recipient snapshot и audit.

## Подготовка занятия, контент и публикация

### `attendance-reminder` — режим школа/дистант

За 1–2 дня администратор делает личный broadcast. Повторная массовая рассылка
возможна только после нового preview. Phase 7/8 заменяет её delivery batch по
участникам выбранного `in_person_event`.

### `teacher-availability` — участие преподавателей

Опрос в teacher chat и последующая рассылка остаются `manual_digital`. Staff
workflow отложен в `post-v1-staffing`; отсутствие ответа выясняется людьми.

### `content-authoring` — TeX, решения и математическое ревью

Ответственные пишут файлы в Dropbox, публикуют для преподавателей и вносят
правки в рабочие файлы. История текущего процесса зависит от Dropbox history и
переписки, а готовность подтверждается явной отмашкой ответственного; отдельной
domain revision и publication audit здесь пока нет. Phase 2 принимает versioned
upload, но Dropbox может оставаться authoring source.

### `lesson-calendar-config` — `cur_les` и даты

[`a00-dates`](#карта-файлов) сейчас задаёт глобальные значения для всей цепочки.
Менять их посреди частично выполненного запуска нельзя. Phase 2/7/10 переносит
их в course/group schedule и materialized lesson windows с preview.

### `production-db-mirror` — свежая локальная SQLite

[`a00-update-db`](#карта-файлов) создаёт remote dump/archive, загружает его,
переименовывает текущую локальную DB в `.temp`, затем создаёт новую DB сразу по
рабочему пути и выполняет dump через `executescript`. Это **не атомарная
замена**: между rename и завершением restore рабочая DB отсутствует либо
частично заполнена. Единственный описанный success marker — финальное `Done!`;
до него потребители не должны открывать результат. При ошибке сначала
отбрасывают неполную новую DB и вручную возвращают `.temp`, а не запускают
скрипт повторно вслепую. Phase 11 должен дать отдельные snapshot/restore/
analytics commands с настоящим atomic publish после проверки кандидата.

### `analytics-refresh` — derived metrics

[`a52-teacher-stats`](#карта-файлов), [`a53-rating`](#карта-файлов) и
[`a54-report`](#карта-файлов) меняют локальную копию: время проверки,
`problem_complexity`, `student_strength`, временные таблицы и HTML report.
Целевой Phase 9 публикует только целиком завершённый versioned analytics run;
частичные таблицы не становятся API dependency.

### `task-template-generation` — TeX → TSV

Фактический файл переданного snapshot —
[`a03-task-template`](#карта-файлов), то есть опечатанное имя
`a03_tempate_for_bot.py`. Он объединяет структуру задач всех уровней,
пишет placeholders и заменяет clipboard. После вставки повтор требует сначала
убрать/сверить прошлый диапазон. Phase 2/10 переносит это в compiler и
metadata-grid draft.

### `task-metadata-import` — названия, ответы и checker

Администратор вручную заполняет `prob_type`, `ans_type`, validation,
`cor_ans`/`cor_ans_checker`, тексты ошибки и поздравления, затем запускает bot
import. Текущий путь полагается на историю Google Sheet, ответ команды и ручную
выборочную сверку; diff-preview и versioned revision ещё отсутствуют. Одинаковое
название внутри занятия — historical synonym signal. Phase 2/4/10 требует typed
grid, всех исторических answer families, preview diff, versioned trusted checker
и rollback.

Ручное ревью имеет предметную семантику, а не только проверку «не пусто»:

- `title` достаточно точно идентифицирует задачу, но остаётся коротким для кнопки; равное имя было historical synonym signal, но в target лишь создаёт admin-confirmed candidate в одном `course_lesson`;
- custom `ans_validation` заменяет default regex типа и делает `fullmatch` по trimmed answer; для `SELECT_ONE` это `;`-separated visible labels;
- `validation_error` называет искомую величину/порядок и по возможности даёт пример; `wrong_ans` и `congrat` отвечают за неверный и верный ответ после валидации;
- `cor_ans` может перечислять много верных ответов через `;`; optional `cor_ans_checker` остаётся trusted-admin code с version/diff/audit и compatibility tests.

### `print-content-derivatives` — teacher/print документы

[`a12-print-derivatives`](#карта-файлов) создаёт TeX/PDF и чистит временные
файлы. Ошибка компиляции либо visual defect блокирует печать; recovery — удалить
только generated set и пересобрать из той же source revision. Canonical PDF
derivative входит в Phase 2, classroom packaging — `post-v1-print`.

### `previous-results-print` — прошлые результаты по аудиториям

[`a13-previous-results`](#карта-файлов) соединяет classroom mapping, локальную DB
и прошлое занятие. Повтор допустим только на том же DB/plan snapshot либо как
новая явно маркированная версия. Полный владелец — `post-v1-print`.

### `print-pack-assembly` — тиражи

[`a14-print-pack`](#карта-файлов) проверяет свежесть counts, удаляет старые
generated packs и собирает одно-/двусторонние наборы. Неверный pack не печатают;
его пересобирают из confirmed plan. Полный владелец — `post-v1-print`.

### `web-content-render` — TeX → HTML/SVG/WebP

[`a16-html`](#карта-файлов) читает CP1251 TeX, компилирует TikZ, выбирает assets
и строит локальный preview. Missing asset, compile failure или непринятый visual
review блокируют FTP. Phase 2 заменяет скрипт canonical AST и несколькими
детерминированными renderers.

### `topic-html-render` — темы задач

[`a16-topics`](#карта-файлов) меняет HTML по problem mapping. Повтор проверяется
normalized diff; recovery — исходный HTML. Phase 2/10 делает темы versioned
problem metadata.

### `legacy-site-publish` — FTP

[`a17-site-upload`](#карта-файлов) заменяет production files. Success требует не
только отсутствия FTP error, но и ручного просмотра настоящей страницы.
Recovery — загрузка предыдущего accepted artifact set. В v1 это legacy bridge;
cutover старого сайта принимается отдельно.

### `lesson-publish-open` — условия и начало сдачи

Channel post, личная рассылка ссылок, состояние intake и автоматическое открытие
сайта — четыре отдельных эффекта. Каждый проверяется отдельно; повтор broadcast
требует preview. Phase 2/8 делает их per-group actions и Telegram bindings.

### `hints-publish` — подсказки

[`a20-hints`](#карта-файлов) извлекает подсказки из TeX; дальше редактор отдельно
публикует пост и reminder. Phase 2/8 хранит отдельную hint revision/schedule и
не связывает её с condition/solution.

### `cutoff-and-solutions` — дедлайн и решения

Это два разных процесса. Перенос публикации решения не двигает deadline;
изменение deadline требует собственного preview и подтверждения. Исторические
времена расходятся между сезонами, поэтому target хранит окна как данные группы.

### `quantik-post` и `online-review-session`

- `quantik-post`: редактор вручную публикует статью по теме в середине недели;
  Phase 8 зеркалит create/edit/delete в PWA.
- `online-review-session`: расписание, два напоминания за 10 минут, Zoom-разбор,
  запись, YouTube upload и публикация ссылки. PWA заменяет announcements, но не
  проведение занятия и не video hosting.

## Аудитории и очный контур

### `classroom-conduit-sync`

[`a01-school-conduit`](#карта-файлов) дважды заменяет clipboard: сначала
`ИзБота`, после Enter — `Посещаемость`. После ручных правок нельзя бездумно
повторно вставлять диапазон. Скрипт и следующие classroom scripts читают
отдельный рабочий Excel-кондуит через runtime symbol `XLS_CONDUIT_NAME` из
отсутствующего `z_helpers`; это **не** workbook
`ВМШ 2025-26, информация для бота ВМШ — prod.xlsx`, где находятся листы бота.
Phase 7/9/10 заменяет clipboard typed read models.

### `classroom-plan-excel`

Администратор наследует старые допустимые комнаты, распределяет остаток в
наименее заполненные, сохраняет лист `Итог` того же отдельного кондуита и
проверяет: у очных есть аудитория, комната не смешивает группы. Phase 7 переносит это в versioned
`in_person_event` plan с local draft recovery.

### `classroom-delivery`

[`a02-welcome-aud`](#карта-файлов) группирует строки по комнате и печатает
`/broadcast_html`; администратор вручную отправляет личное сообщение каждому
школьнику. Текущий скрипт не создаёт immutable delivery batch: до отправки
оператор вручную просматривает напечатанные команды. Целевой Staff action сначала
показывает preview, затем по выбору отправляет PWA и/или personal Telegram. После
черновой перестановки ничего не уходит автоматически.

### `classroom-print-lists`

[`a11-classroom-lists`](#карта-файлов) запускают строго перед печатью. Success —
не только «Всё готово!», но и visual check плюс совпадение counts с последним
сохранённым workbook. Между ранней рассылкой и печатью оператор при необходимости
обновляет данные, аккуратно сливает изменения, подкручивает назначения и получает
явный readiness sign-off. В v1 скрипт остаётся active; Staff print — отдельная
следующая версия.

Ранняя рассылка и final print могут законно опираться на разные версии плана. Поэтому cutover не доказан, пока либо печать не строится из конкретной confirmed Staff version, либо Excel не остаётся явно операционным source of truth. Staff показывает delivery version и неразосланные изменения; он не притворяется, что Telegram, Excel и бумага всегда совпадают.

### `teacher-room-assignment`

Организатор вручную сопоставляет преподавателей с комнатами и сообщает результат
в teacher chat. Это отдельный `post-v1-staffing` workflow, а не часть назначения
школьников.

### `physical-preparation`, `physical-session`, `physical-close-scan`

- `physical-preparation`: распечатать и развесить списки, подготовить комнаты,
  условия и папки, провести разбор преподавателей, встретить участников;
- `physical-session`: провести занятие и заполнить бумажные кондуиты;
- `physical-close-scan`: убрать комнаты, собрать главные кондуиты, отсортировать,
  проверить комплектность и отсканировать.

Эти процессы остаются `manual_physical`. Цифровой продукт должен давать им
однозначный confirmed snapshot и печатные производные, а не изображать, что
заменяет людей.

### `zoom-oral-window`

Ручной workflow открывает remote mode, публикует инструкцию, рассылает личные
приглашения, проверяет присутствие преподавателей и планирует закрытие. Phase 7
делает group-specific window state и Staff oral administration; Telegram/Zoom
остаются adapters.

## После очного занятия и после проверки

### `conduit-recognition`

[`a18-conduit-ocr`](#карта-файлов) создаёт распознанный Excel/debug output.
Результат обязательно выборочно проверяется; scan hash остаётся immutable input.
Snapshot не запускается сам по себе: он импортирует отсутствующий модуль
`plus_reader.plus_reader`, а также общие helpers. Staff import diagnostics —
`post-v1-results-import`.

### `school-results-import`

[`a19-results-import`](#карта-файлов) переносит проверенный Excel через API в
общую систему. Целевой import обязан иметь dry-run, source hash, row keys,
receipt и recovery частичного запуска.

### `bot-results-refresh`

После import admin-команда обновляет представления школьников. Целевой Student
read model обновляется owner-scoped invalidation/refetch; Telegram остаётся
параллельным projection.

### `post-review-mailing`

[`a21-personal-plots`](#карта-файлов) и [`a22-mails`](#карта-файлов) строят
персональные графики, workbook/templates и передают их внешнему sender. Генерация
также читает отдельный чувствительный workbook
`Кондуиты/Заявки и пароли 2025-2026.xlsx`: лист `Данные` содержит ФИО ребёнка,
пароль и email. Файл отсутствует в snapshot, не должен копироваться в
репозиторий и нужен только для privacy-safe historical replay. Генерация
повторяема на том же snapshot; отправка повторяется только failed recipients.
Полный mailing UI — после v1.

### `legacy-site-statistics`

[`a23-site-stats`](#карта-файлов) делает FTP read-modify-write исторических HTML.
Численная часть переезжает в Phase 9, а вывод старого сайта отключается только
после отдельного cutover.

### `statistics-publications`

[`a21-group-plots`](#карта-файлов), [`a54-report`](#карта-файлов) и ручные SQL
дают разные посты ученикам и преподавателям. Каждый пост сверяется с complete
analytics run. Student/Family никогда не получают маркер ребёнка на групповом
распределении.

### `production-backups`

Production DB несколько раз в день копируется к другому провайдеру; deploy также
имеет pre/post backup. Это сохраняется как operations-owned process. Phase 11
закрывается только реальным restore rehearsal с измеренными RPO/RTO, а не
наличием файла с похожим именем.

## Reference-only процессы

- `reference-media-pipeline`: [`ref-edt-parser`](#карта-файлов),
  [`ref-mathimg-endpoints`](#карта-файлов), [`ref-mathimg-service`](#карта-файлов)
  задают идеи TikZ/SVG/WebP/S3 для Phase 2/5, но не импортируются runtime.
- `reference-written-review`: [`ref-written-html`](#карта-файлов),
  [`ref-written-js`](#карта-файлов), [`ref-written-helpers`](#карта-файлов) и
  [`legacy-mailing-view`](#карта-файлов) — только идеи проверки/просмотра из
  другого проекта для Phase 6: filters/search, deep-link, image navigation/preload,
  canvas annotation/zoom/rotate/undo/redo/autosave, comment/verdict controls,
  suspicion/task-reassignment controls и isolated mailing preview; ни один файл не
  является VMШ runtime-кодом, sanitizer или API contract.
- `reference-auth`: [`ref-auth-routes`](#карта-файлов) и
  [`ref-auth-tokens`](#карта-файлов) — паттерн cookies/refresh для Phase 1.
- `reference-mailing-ui`: [`legacy-mailing-core`](#карта-файлов),
  [`legacy-mailing-editor`](#карта-файлов), [`legacy-mailing-view`](#карта-файлов),
  [`legacy-email-templates`](#карта-файлов) — reference для post-v1 editor.
- `news-characterization`: [`telegram-news-corpus`](#карта-файлов) — закрытый
  structural corpus Phase 8, не runtime source и не источник текста для docs.
- `legacy-workbook-config`: [`legacy-workbook`](#карта-файлов) остаётся active
  upstream до Phase 10 cutover листов «Задачи»/«Старые».

## Точный runbook недели

Машинный ID: `weekly-operations-historical`. Повторы одного процесса ниже
намеренны: например, production DB обновляют до аудиторий, перед импортом очных
результатов и после письменной проверки.

### Постоянно и при появлении новичков

1. Ответить на email (`support-email`).
2. Ответить на SOS (`support-sos`).
3. Ответить в общей группе (`support-community-chat`).
4. Несколько раз в неделю выгрузить esz и сохранить Excel
   (`newcomer-applications`).
5. Добавить отдельные немосковские заявки (`newcomer-applications`).
6. Создать legacy-логины/пароли школьников и строки user sheet
   (`newcomer-account-provision`); Family accounts появятся только в target.
7. Загрузить пользователей admin-командой (`newcomer-bot-import`).
8. Обновить текст и разослать доступы (`newcomer-credentials-mailing`).

### До занятия

9. За 1–2 дня напомнить о режиме (`attendance-reminder`).
10. Собрать участие преподавателей и разослать приглашения
    (`teacher-availability`).
11. Заранее написать, сверстать, решить и согласовать задачи
    (`content-authoring`).
12. В день занятия первым действием обновить номер/даты
    (`lesson-calendar-config`).
13. Получить DB и дождаться финального `Done!` (`production-db-mirror`).
14. Вставить `ИзБота` и `Посещаемость` (`classroom-conduit-sync`).
15. Согласовать комнаты и сохранить распределение (`classroom-plan-excel`).
16. Просмотреть и выполнить личную рассылку (`classroom-delivery`).
17. Получить явную отмашку ответственного о готовности вариантов
    (`content-authoring`).
18. Запустить фактический `a03_tempate_for_bot.py` и создать TSV-заготовку
    (`task-template-generation`).
19. Заполнить metadata и импортировать задачи (`task-metadata-import`).
20. Если за прошедшие после рассылки часы изменились статусы, снова получить DB
    и дождаться `Done!` (`production-db-mirror`).
21. Вручную слить свежие строки `ИзБота`/`Посещаемость`, не затирая назначения
    (`classroom-conduit-sync`).
22. Подкрутить изменившиеся назначения, сохранить workbook и получить явный
    readiness sign-off (`classroom-plan-excel`).
23. Только после sign-off пересобрать списки непосредственно перед печатью
    (`classroom-print-lists`).
24. Собрать content/teacher/conduit derivatives
    (`print-content-derivatives`).
25. Собрать прошлые результаты по комнатам (`previous-results-print`).
26. Сверить counts и собрать тиражи (`print-pack-assembly`).
27. Собрать web HTML/assets (`web-content-render`).
28. Добавить topics при наличии (`topic-html-render`).
29. Загрузить сайт и проверить реальную страницу (`legacy-site-publish`).
30. Назначить преподавателей (`teacher-room-assignment`).

### Открытие, очная и Zoom-части

31. Исторически около 16:00 отдельно опубликовать условия, разослать ссылки,
    открыть intake и проверить сайт (`lesson-publish-open`).
32. Распечатать/развесить/разложить материалы и встретить участников
    (`physical-preparation`).
33. Провести очное занятие (`physical-session`).
34. Для Zoom открыть режим, дать инструкции, разослать приглашения, проверить
    преподавателей и запланировать close (`zoom-oral-window`).
35. После очного убрать комнаты, проверить кондуиты и отсканировать
    (`physical-close-scan`).

### После очного и в течение недели

36. Распознать скан и выборочно проверить Excel (`conduit-recognition`).
37. Обновить DB перед import (`production-db-mirror`).
38. Импортировать очные результаты (`school-results-import`).
39. Обновить bot projections (`bot-results-refresh`).
40. В середине недели опубликовать статью (`quantik-post`).
41. В историческую субботу добавить/опубликовать подсказки и reminder
    (`hints-publish`).
42. По независимому расписанию сначала закрыть intake, затем отдельно
    опубликовать решения (`cutoff-and-solutions`).

### После проверки и онлайн-разборы

43. Обновить DB и analytics (`production-db-mirror`).
44. Создать и отправить письма (`post-review-mailing`).
45. Обновить markers старого сайта (`legacy-site-statistics`).
46. Опубликовать разные сводки ученикам и учителям
    (`statistics-publications`).
47. Для каждого онлайн-разбора актуализировать анонс, напомнить за 10 минут,
    провести/записать, загрузить и опубликовать ссылку
    (`online-review-session`).
48. Независимо от недели контролировать межпровайдерные backups
    (`production-backups`).

## Точный legacy-runbook аудиторий

Машинный ID: `classroom-assignment-legacy-detail`.

1. Обновить `a00_dates.py`.
2. Скопировать кондуит занятия N−1 в N, если копии ещё нет.
3. Запустить `a00_update_db.py`; продолжать только после `Done!`.
4. Открыть кондуит текущего занятия.
5. Запустить `a01_school_to_conduit.py`: вставить первый clipboard в
   `ИзБота!A2`, вернуться в скрипт, нажать Enter, вставить второй в
   `Посещаемость`.
6. На листе `Аудитории` актуализировать комнаты.
7. На листе `Итог` отсортировать: `Скрыть` в обратном порядке, затем `Ауд`,
   `Уровень`, `Фамилия`, `Имя`.
8. Очистить аудиторию у строк с `Скрыть = 1`.
9. Вернуть допустимую прошлую аудиторию тем, кто пропускал либо недавно менял
   уровень.
10. Остальных распределить в наименее заполненные допустимые аудитории.
11. Сохранить файл и проверить инварианты до рассылки.
12. Запустить `a02_welcome_aud.py`, просмотреть сгенерированные команды и только
    затем выполнить персональную рассылку через бота.
13. Если до печати прошло время или изменились статусы, снова запустить
    `a00_update_db.py` и принять refresh только после `Done!`.
14. Снова запустить `a01_school_to_conduit.py` и вручную слить изменившиеся
    строки `ИзБота`/`Посещаемость`, не затирая назначения аудиторий.
15. Подкрутить изменения, сохранить workbook и получить явное подтверждение
    ответственного: все очные распределены, группы не смешаны, именно эта версия
    готова к печати.
16. Непосредственно перед печатью запустить `a11_spis_from_xls.py` только на
    версии, прошедшей readiness sign-off.

В Staff эти действия превращаются в inherited plan → local draft → preview →
confirm → отдельный delivery batch. Правка после рассылки никогда автоматически
не уведомляет школьников.

## Карта файлов

Все прямые script/reference файлы `_external_pipelines` плюс Telegram JSON
входят в fixture ровно один раз. Media-файлы экспорта намеренно представлены
одним corpus item, чтобы реестр не копировал message metadata.

| ID | Файл | Текущая классификация | Целевой этап |
| --- | --- | --- | --- |
| `a00-dates` | `_external_pipelines/a00_dates.py` | active external | Phase 2/7/10 |
| `a00-update-db` | `_external_pipelines/a00_update_db.py` | active external | Phase 11 |
| `a01-school-conduit` | `_external_pipelines/a01_school_to_conduit.py` | active external | Phase 7/9/10 |
| `a02-welcome-aud` | `_external_pipelines/a02_welcome_aud.py` | active external | Phase 7 |
| `a03-task-template` | `_external_pipelines/a03_tempate_for_bot.py` | active external | Phase 2/10 |
| `a11-classroom-lists` | `_external_pipelines/a11_spis_from_xls.py` | active external | post-v1 print |
| `a12-print-derivatives` | `_external_pipelines/a12_dum_tex_files.py` | active external | Phase 2/post-v1 print |
| `a13-previous-results` | `_external_pipelines/a13_print_per_aud_conds_tex.py` | active external | post-v1 print |
| `a14-print-pack` | `_external_pipelines/a14_zall_auds_pdf.py` | active external | post-v1 print |
| `a16-html` | `_external_pipelines/a16_html_from_tex.py` | active external | Phase 2 |
| `a16-topics` | `_external_pipelines/a16_topics_to_html.py` | active external | Phase 2/10 |
| `a17-site-upload` | `_external_pipelines/a17_upload_to_website.py` | active external | post-v1 old site |
| `a18-conduit-ocr` | `_external_pipelines/a18_conduit_recognition.py` | active external | post-v1 result import |
| `a19-results-import` | `_external_pipelines/a19_from_excel_into_bot_via_api.py` | active external | post-v1 result import |
| `a20-hints` | `_external_pipelines/a20_подсказки.py` | active external | Phase 2/8 |
| `a21-personal-plots` | `_external_pipelines/a21_create_plots.py` | active external | Phase 9/post-v1 email |
| `a21-group-plots` | `_external_pipelines/a21_create_zall_plots.py` | active external | Phase 9 |
| `a22-mails` | `_external_pipelines/a22_create_mails.py` | active external | post-v1 email |
| `a23-site-stats` | `_external_pipelines/a23_mark_compl_in_html.py` | active external | Phase 9/post-v1 old site |
| `a52-teacher-stats` | `_external_pipelines/a52_teacher_stats.py` | active automated | Phase 6/9 |
| `a53-rating` | `_external_pipelines/a53_calc_rating_new.py` | active automated | Phase 7/9 |
| `a54-report` | `_external_pipelines/a54_upd_report.py` | active automated | Phase 9 |
| `ref-edt-parser` | `_external_pipelines/edt_tasks_parser.py` | reference | Phase 2 |
| `ref-mathimg-endpoints` | `_external_pipelines/mathimg_endpoints.py` | reference | Phase 2/5 |
| `ref-mathimg-service` | `_external_pipelines/mathimg_service.py` | reference | Phase 2/5 |
| `ref-auth-routes` | `_external_pipelines/routes.py` | reference | Phase 1 |
| `ref-auth-tokens` | `_external_pipelines/tokens.py` | reference | Phase 1 |
| `legacy-mailing-core` | `_external_pipelines/_crtmailings_helpers.js` | reference | post-v1 email |
| `legacy-mailing-editor` | `_external_pipelines/_mailing_editor_helpers.js` | reference | post-v1 email |
| `legacy-mailing-view` | `_external_pipelines/_viewmailings_helpers.js` | idea-only reference for written review and mailing view | Phase 6/post-v1 email |
| `legacy-email-templates` | `_external_pipelines/edtemailtemplates.js` | reference | post-v1 email |
| `ref-written-html` | `_external_pipelines/viewwrittensols.html` | reference | Phase 6 |
| `ref-written-js` | `_external_pipelines/viewwrittensols.js` | reference | Phase 6 |
| `ref-written-helpers` | `_external_pipelines/_viewwrittensols_helpers.js` | reference | Phase 6 |
| `telegram-news-corpus` | `_external_pipelines/ChatExport_2026-07-25/result.json` | private reference corpus | Phase 8 |
| `legacy-workbook` | `_external_pipelines/ВМШ 2025-26, информация для бота ВМШ — prod.xlsx` | active external/private characterization | Phase 10 |

## Внешние зависимости, которых нет в snapshot

Machine-register хранит их в `knownExternalDependencies`; отсутствующий путь не
маскируется repository artifact:

- `legacy-python-support-modules`: `z_CONSTS.py`, `z_helpers.py`, `z_cpdf.py`;
- `canonical-conduit-workbook`: отдельный workbook, разрешаемый в runtime через
  `z_helpers.XLS_CONDUIT_NAME`; его листы `Аудитории`, `Итог`, `ИзБота` и
  `Посещаемость` не относятся к переданному workbook бота;
- `plus-reader`: `plus_reader.plus_reader`, обязательный для
  `a18_conduit_recognition.py`;
- `tex-template-tree`: рабочая папка `tex_templates` и связанные Dropbox
  templates;
- `external-mail-sender`: фактически используемый sender/скрипт после генерации
  email-артефактов;
- `registration-credentials-workbook`: отдельный
  `Кондуиты/Заявки и пароли 2025-2026.xlsx`, который читает
  `a22_create_mails.py`; это PII/credential-bearing input, поэтому для replay
  допустима только специально обезличенная фикстура без настоящих паролей и
  адресов.

Для каждого указаны реальные consumer process IDs и существующие evidence files.
Место зависимостей спрашивается в
[`20-implementation-questions.md`](20-implementation-questions.md#где-находятся-отсутствующие-зависимости),
а безопасный test bundle — в
[отдельном вопросе](20-implementation-questions.md#можно-ли-подготовить-обезличенный-комплект).

## Известные границы baseline

1. Snapshot не содержит `z_CONSTS`, `z_helpers`, `z_cpdf`,
   `plus_reader.plus_reader`, `tex_templates`, canonical Dropbox roots,
   workbook из `XLS_CONDUIT_NAME`, чувствительный registration credentials
   workbook и внешний mail sender. Поэтому наличие Python-файла не доказывает
   воспроизводимость полного production-run.
2. В устном описании сохранились исторические имена `a02_tempate_for_bot`,
   `a15_print_per_aud_conds_html`, `a21_create_mails` и
   `a22_mark_compl_in_html_new`, тогда как данный snapshot содержит
   `a03_tempate_for_bot.py`, `a13_print_per_aud_conds_tex.py`,
   `a22_create_mails.py` и `a23_mark_compl_in_html.py`. Реестр использует
   фактические пути snapshot; live filenames нужно подтвердить в
   [вопросе о скриптах](20-implementation-questions.md#какие-скрипты-используются-сейчас).
3. Исторические времена cutoff/solution расходятся. Это не разрешается выбором
   одной «правильной» константы: Phase 2 импортирует/задаёт расписание отдельно
   для каждой группы.
4. Для backups известен ожидаемый результат, но в репозитории нет полного
   service/retention/restore runbook.

Неразрешённые пункты вынесены в
[`20-implementation-questions.md`](20-implementation-questions.md); они не
мешают characterization, но блокируют соответствующий production cutover.

## Acceptance этого реестра

- JSON валиден, имеет version 1 и уникальные process/artifact/system IDs.
- У каждого процесса есть owner, явный `invocation`, явные
  `upstreamProcessIds`, `transitionState`, trigger/schedule, inputs,
  outputs/side effects, credential classes, rerun, failure detection, recovery,
  source paths и target phase/decision/gate.
- Current-поля не обещают target-only Family provisioning, immutable receipts,
  versioned revisions, preview или audit.
- Внешние dependencies имеют уникальные IDs, известных consumers, существующие
  evidence paths и ссылку на настоящий заголовок вопроса.
- Все repository-relative source paths существуют.
- Все прямые `_external_pipelines` scripts/references учтены ровно один раз по
  пути, даже если один idea-only файл относится к нескольким reference-process;
  новые либо дублированные файлы ломают тест до осознанной классификации.
- Каждый runbook имеет непрерывную нумерацию и ссылается только на известные
  процессы.
- Markdown содержит ID каждого process, artifact и runbook.
- Fixture не содержит IP, Telegram API URL/token, `chat_id` или скопированные
  JSONL payload.
