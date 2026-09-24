# Исторические артефакты и стратегия совместимости

## Главное правило

`_vmsh_examples` и `_external_pipelines` — входы для анализа и тестов, но не место разработки PWA. Их нельзя молча править, импортировать как production-package или объявлять устаревшими без сравнительного отчёта. Все реально используемые еженедельные скрипты остаются рабочими до полного переноса соответствующего процесса в Staff/PWA.

Текущий production-контур по-прежнему состоит из общей Dropbox-папки с TeX/PDF/скриптами, ручных Telegram-каналов и групп, отдельного Telegram-бота с общей SQLite, автоматически обновляемого по FTP старого сайта и межпровайдерных backups. Описание нового Staff/PWA-владельца ниже является target, а не свидетельством, что versioning, preview, audit либо cutover уже существуют.

`db/vmsh.db` остаётся неизменяемым локальным source. Если исторический pipeline нужно характеризовать на production-size данных, сначала создаётся изолированная временная копия; до derivation все имена и фамилии `users` в ней заменяются Faker-значениями. Копия не коммитится и не становится E2E seed. Реальные tokens, contacts, message bodies и другие чувствительные поля из неё не переходят в committed fixtures или reports.

## `_vmsh_examples`: golden corpus

Сейчас каталог содержит примеры условий/решений нескольких уроков и уровней, а также JSON-темы. Встречаются:

- исходники с явной Windows Cyrillic/CP1251 encoding;
- пользовательские LaTeX macros;
- TikZ, `includegraphics`, таблицы, перечисления, подпункты и геометрия;
- совмещённые source-файлы с условиями и решениями;
- JSON вида `results[].problem_id` + `topics[]`.

Канонический test manifest: `vmshpwa/fixtures/content/golden-manifest.json`. Он не копирует исходники, а ссылается на них относительными путями и фиксирует:

- ожидаемую encoding и source SHA-256;
- season/lesson/level и вид документа;
- ожидаемые позиции задач и итог явно подтверждённого сопоставления между revisions;
- ожидаемое число задач, изображений и diagnostics;
- допустимые и недопустимые warning codes;
- snapshot paths производной canonical AST/JSON;
- ручной visual approval для PWA, Telegram preview и PDF; обязательный минимум — три листка одного уровня.

Golden snapshots должны быть структурными и небольшими. Большие HTML/PDF/WebP не коммитятся без причины; для них хранятся hash, dimensions и screenshot/visual evidence.

## `_external_pipelines`: карта замены

| Артефакт                                                                                                | Историческая ответственность                                                                                                                  | Новый владелец                                                                    | Этап и proof                                        |
| ------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | --------------------------------------------------- |
| `a00_dates.py`                                                                                          | Ручной номер текущего занятия и календарь school/Zoom/written дат                                                                             | season/lesson windows в Staff + scheduler                                         | Этапы 2/7/10: schedule parity                       |
| `a00_update_db.py`                                                                                      | Получение/копирование production DB; текущий restore имеет неатомарное окно между `.temp` и завершением `executescript`                       | deployment/backup runbook, не UI; не считать текущий swap безопасным              | Этап 11: verified restore и atomic publish          |
| `a01_school_to_conduit.py`                                                                              | Выгрузка текущего mode/group/strength и посещаемости из SQLite в ведомость через clipboard                                                    | Staff statistics/classroom legacy bridge до отдельного print/export cutover       | Этапы 7/9/10 и последующий print/export cutover     |
| `a02_welcome_aud.py`                                                                                    | Генерация Telegram-команд персональной рассылки аудиторий по `IDd`                                                                            | v1 Staff classroom delivery batch: preview + explicit PWA/personal Telegram send  | Этап 7: recipient/message parity и cutover          |
| `a03_tempate_for_bot.py`                                                                                | Разбор LaTeX-структуры задач и подготовка TSV-строк листа «Задачи»                                                                            | content compiler + task metadata grid                                             | Этапы 2/10: structural/TSV parity                   |
| `a11_spis_from_xls.py`                                                                                  | Excel-аудитории, barcode/кондуиты, списки на двери/этаж и PDF                                                                                 | Отдельный legacy print workflow; будущий Staff print service                      | Operational legacy в v1; cutover во второй версии   |
| `a12_dum_tex_files.py`                                                                                  | Условия, решения, teacher/conduit documents                                                                                                   | content compiler; teacher/conduit print derivatives завершаются print-фазой       | Этап 2 + отдельная фаза print                       |
| `a13_print_per_aud_conds_tex.py`                                                                        | Печатные материалы по аудиториям                                                                                                              | будущий classroom print command                                                   | Вторая версия                                       |
| `a14_zall_auds_pdf.py`                                                                                  | Сборка тиражей условий, кондуитов, teacher edition и прошлых решений по аудиториям                                                            | PDF derivatives + будущая print orchestration                                     | Этап 2 corpus; полный cutover во второй версии      |
| `a16_html_from_tex.py`                                                                                  | LaTeX → исторический HTML                                                                                                                     | новый parser/compiler                                                             | Этап 2: characterization + visual comparison        |
| `a16_topics_to_html.py`                                                                                 | Темы задач → HTML                                                                                                                             | metadata/topics renderer                                                          | Этап 2/10                                           |
| `a17_upload_to_website.py`                                                                              | FTP-публикация старого публичного сайта                                                                                                       | legacy bridge в v1; будущий internal publisher старого сайта либо отдельный отказ | После первой версии; не объявлять cutover в этапе 2 |
| `a18_conduit_recognition.py`                                                                            | OCR/слияние ведомостей; требует отсутствующий в snapshot `plus_reader.plus_reader`                                                            | будущие Staff import diagnostics                                                  | После первой версии                                 |
| `a19_from_excel_into_bot_via_api.py`                                                                    | Импорт oral/school marks                                                                                                                      | будущий Staff bulk result import                                                  | После первой версии                                 |
| `a20_подсказки.py`                                                                                      | Извлечение подсказок                                                                                                                          | content compiler                                                                  | Этап 2                                              |
| `a21_create_plots.py`, `a21_create_zall_plots.py`                                                       | Личные/групповые rolling-strength PNG из `temp_student_visits` и `temp_result_*`                                                              | versioned analytics snapshots + visx                                              | Этап 9: numerical/visual parity                     |
| `a22_create_mails.py`                                                                                   | Подготовка email-артефактов; требует отсутствующий PII/credential workbook `Заявки и пароли 2025-2026.xlsx`, внешний sender также отсутствует | только обезличенный replay; отдельная admin-задача                                | Вторая–третья версия                                |
| `a23_mark_compl_in_html.py`                                                                             | Встраивание solved/total difficulty markers в HTML старого сайта через FTP                                                                    | statistics read model + будущий publisher старого сайта; в v1 legacy bridge       | Этап 9 parity; cutover вместе со старым сайтом      |
| `a52_teacher_stats.py`                                                                                  | Ретрооценка времени проверки и запись `results.check_time_spent_sec`                                                                          | review event timing + versioned analytics repair command                          | Этапы 6/10: parity без ad-hoc ALTER                 |
| `a53_calc_rating_new.py`                                                                                | Problem complexity, latest student strength, best level и rolling lesson metrics                                                              | аналитический job с versioned full-run snapshots; latest projection для classroom | Этапы 7/9/10                                        |
| `a54_upd_report.py`                                                                                     | Violin и problem statistics HTML поверх временных таблиц                                                                                      | Student/Family/Staff read models и charts                                         | Этап 9                                              |
| `edt_tasks_parser.py`                                                                                   | Более новый parser/TikZ/assets/S3                                                                                                             | источник характеристик нового compiler                                            | Этап 2                                              |
| `mathimg_endpoints.py`                                                                                  | HTTP image conversion                                                                                                                         | server fallback adapter                                                           | Этапы 2/5                                           |
| `mathimg_service.py`                                                                                    | Hash, SVG/WebP, ImageMagick/HEIC, S3                                                                                                          | media conversion service внутри существующего backend                             | Этапы 2/5                                           |
| `routes.py`, `tokens.py`                                                                                | Signed-cookie + refresh patterns                                                                                                              | reference для auth, без прямого копирования секретов                              | Этап 1                                              |
| `viewwrittensols.html`, `viewwrittensols.js`, `_viewwrittensols_helpers.js`, `_viewmailings_helpers.js` | Idea-only фрагменты письменной проверки/просмотра из другого проекта; не VMШ runtime                                                          | новый Phase 6 review/thread UI по собственным контрактам                          | Этап 6                                              |
| `ВМШ 2025-26, информация для бота ВМШ — prod.xlsx`                                                      | Legacy Google export; лист `Задачи` с `prob_type`, `ans_type`, validation/checker/messages                                                    | characterization для metadata grid и первого Google cutover                       | Этапы 4/10                                          |
| `ChatExport_2026-07-25/result.json`                                                                     | Экспорт канала за несколько месяцев: длинные text posts, entities, links и historical media                                                   | news fixture corpus; будущие условия расширяются до полного Rich Message text     | Этапы 2/8                                           |

Таблица описывает не только scope v1, но и конечного владельца процесса. Допустимы три состояния: `legacy bridge` (скрипт всё ещё выполняет production side effect), `parallel parity` и `internal owner/cutover`. Формулировка «после первой версии» не закрывает строку: у неё остаются named owner, вход/выход, критерий parity и дата следующего решения.

Этап 0 дополняет таблицу operational register без секретов: кто и как запускает процесс, откуда берётся `cur_les`, какие файлы/листы/таблицы он читает, куда пишет, можно ли повторить запуск и как восстановиться после частичного результата. Это особенно важно для цепочек `a00_dates → a01/a02/a11–a14`, `a53 → a21/a23/a54` и `a12/a16 → a17`: отдельные файлы не являются независимыми workflow.

Такой реестр зафиксирован в [реестре внешних процессов и недельных операций](21-external-process-register.md). Его машиночитаемая версия — [`external-process-register.v1.json`](../../../pwa_tests/fixtures/external-process-register.v1.json), а полноту путей, полей и связей проверяет [`test_external_process_register.py`](../../../pwa_tests/test_external_process_register.py). Времена в нём являются историческим baseline, а не новой глобальной настройкой: целевое расписание остаётся независимым для каждого курса и группы.

Реестр отдельно хранит фактический способ запуска, upstream-processes и состояние перехода. Если команда или зависимость отсутствует в snapshot, это остаётся известным gap. В частности, scripts аудиторий читают отдельный рабочий кондуит через `z_helpers.XLS_CONDUIT_NAME`: переданный workbook `ВМШ 2025-26, информация для бота ВМШ — prod.xlsx` содержит листы конфигурации бота и не подменяет листы `Аудитории`/`Итог`.

Закрытые `logs/events.jsonl` и dated rotations за две настоящих рабочие недели используются как characterization source для последовательностей, частоты и типов событий. Ни payload, ни идентификаторы из них в fixtures этого реестра не копируются.

`logs/selected.jsonl`, `logs/cnt.py` и их Git history по решению владельца пока остаются в закрытом репозитории. Это разрешение на хранение исходного corpus, а не на повторную публикацию: производные документы и тестовые данные по-прежнему должны быть агрегированными либо синтетическими.

При ручном анализе логов допустимы только privacy-safe выводы: имена event-типов, counts, порядок внутри обезличенного flow и aggregate timing. Строки JSONL, `trace_id`/`flow_id`, Telegram/user/chat IDs, тексты, ответы и пути вложений не вставляются в docs, issue, Storybook, snapshots и committed test fixtures. Синтетический fixture строится по выведенному shape, а не псевдонимизацией реальной строки.

## Что именно характеризуется в task metadata

- `a03_tempate_for_bot.py` даёт структуру level/lesson/problem/item и initial task kind, но не заменяет ручное ревью metadata.
- `title` должен быть коротким для кнопок, но достаточно точно идентифицировать задачу. Исторически равные title в одном занятии склеивали результаты; target сужает это до admin-confirmed synonym candidate внутри одного `course_lesson` и не сливает concrete rows.
- Пустой `ans_validation` означает default regex типа; custom value — `fullmatch` по `student_answer.strip()`. Для `SELECT_ONE` поле хранит `;`-separated visible labels.
- `validation_error` называет искомую величину/порядок и по возможности даёт пример. `wrong_ans` отвечает за валидный неверный ответ, `congrat` — за верный; оба могут быть context-specific.
- `cor_ans` поддерживает один или много `;`-separated правильных ответов. `cor_ans_checker` — редкий trusted-admin checker; его фактическая execution boundary — [`handlers/student_handlers.py`](../../../handlers/student_handlers.py) (`is_py_func`, `GLOBALS_FOR_TEST_FUNCTION_CREATION`, `run_py_func_checker`), а не один из `_external_pipelines`. До рефакторинга Phase 4 фиксирует наблюдаемое поведение на синтетическом positive/negative/error/cache corpus; реальные checker strings и ответы не попадают в committed fixtures или Student/Family contracts. Restricted globals не объявляются sandbox.

Полный целевой контракт полей описан в [LaTeX/content pipeline](../../docs/latex-content-pipeline.md#семантика-legacy-метаданных-которую-нельзя-потерять).

## Границы idea-only review prototype

`viewwrittensols.html`/`.js` и вспомогательные view-files показывают идеи multi-exam filters, deep-link, image preloading/navigation, canvas-аннотаций, zoom/rotate/undo/redo/autosave, comment/verdict controls, suspicion mark и correction ошибочной task binding. `_viewmailings_helpers.js` даёт идею сериализуемых filters и изолированного preview.

Это не acceptance-by-copy. Phase 6 отдельно решает, какие идеи принять, и перереализует их на своих contracts. Не копируются endpoints, API state, score scale, HTML/sanitization assumptions, raw colors, localStorage keys и зависимости. Набор для проверки ВМШ должен доказать thread/evidence/lease/visibility/synonym семантику независимо от этих файлов.

Legacy `written_tasks_discussions` и `results` не дают достоверной связи message → конкретный review round. Historical backfill сохраняет весь материал единым хронологическим thread с provenance и не приписывает сообщения последнему verdict. Исходные results остаются самостоятельными историческими результатами; точные round links появляются только у новых операций после cutover.

Owner decision для первого MVP уже: 40 531 discussion rows без payload означают
Telegram-hosted images, которые нельзя восстановить через Bot API. Их не
материализуем и не показываем placeholder. Новый учебный год начинается почти с
пустой submission history; летом новый flow проверяется на лояльных учениках.

Банк изображений условий переносится иначе: отдельный admin script загружает в
content-addressed S3 несколько тысяч assets, пишет dry-run/receipt и допускает
повторный запуск. Сначала pipeline проходит end-to-end на новых занятиях 39–41,
после чего исторические материалы можно загрузить отдельным debugging batch.

## Правило characterization

Перед заменой скрипта:

1. Выбрать 3–10 репрезентативных inputs, включая самый сложный реальный пример.
2. Зафиксировать текущий observable output: структура, ключевые числа, filenames, hashes или screenshots.
3. Описать намеренные расхождения нового результата.
4. Сделать новый unit/integration test независимым от запуска исторического скрипта.
5. Один раз выполнить сравнительный report и приложить его к proof этапа.
6. Не удалять старый operational path, пока владелец продукта не подтвердит parity/cutover.

Первый Google cutover относится к листам «Задачи» и «Старые» файла `_external_pipelines/ВМШ 2025-26, информация для бота ВМШ — prod.xlsx`. Surveys, email и очный импорт результатов не входят в первую версию.

Для листа `Задачи` characterization фиксирует как минимум колонки `level`, `lesson`, `prob`, `item`, `title`, `prob_text`, `prob_type`, `ans_type`, `ans_validation`, `validation_error`, `cor_ans`, `cor_ans_checker`, `wrong_ans`, `congrat` и исторические значения `Тест`, `Письменно`, `Письменно<-Устно`. Новый grid показывает отдельные dropdown task/answer type и сохраняет прямоугольную TSV copy/paste; migration явно переводит hybrid в canonical oral с письменной сдачей.

## Одноразовый перенос аудиторий

Для первого запуска этап 7 получает отдельный import tool, но не постоянный Excel/Google workflow. Исторические `a11_spis_from_xls.py` и `a02_welcome_aud.py` используются как characterization и, до переноса печати/Telegram delivery, как legacy consumers отдельного workbook, путь к которому reference-копия `z_helpers.py` передаёт через `XLS_CONDUIT_NAME`. Рабочий workbook остаётся внешним. После Staff apply scripts не должны продолжать читать независимо изменяемую старую копию.

Минимальный вход: колонки `IDd`, `Уровень`, `Аудитория` одноразового export именно из этого кондуита, а не из workbook листов `Задачи`/`Старые`. `IDd` — legacy numeric `users.id`; barcode не содержит Telegram token и сам по себе не требует ротации credential. До любой записи dry-run обязан показать:

- число строк и уникальных школьников;
- неизвестные/дублирующиеся `IDd`;
- неизвестные группы/уровни;
- пустые имена аудиторий и конфликты после trim + Unicode NFKC + casefold;
- комнаты, в которых вход смешивает разные группы;
- очных школьников без аудитории;
- предлагаемый catalog, effective layout и initial assignment plan с counts по группам/комнатам.

Apply принимает hash именно просмотренного входа и dry-run report, выполняется транзакционно и пишет audit/import report. Повтор с тем же hash либо безопасно возвращает прежний receipt, либо явно останавливается как уже применённый. Сформированные комнаты не получают capacity/weight из исторических counts. После cutover catalog/layout/plan редактируются только Staff API. `a02` заменяется типизированным classroom delivery batch из confirmed plan: recipient preview, explicit PWA/Telegram selection, immutable snapshot и no-auto-resend. `a11`–`a14` остаются отдельным legacy print workflow до Staff print-раздела второй версии; v1 compatibility export для них не обещается.

## Риски, которые обязаны попасть в тесты

- CP1251/UTF-8 detection и недопустимая потеря кириллицы.
- Нестандартные macros и команды, которые parser не знает.
- TikZ compilation timeout, missing LaTeX package и invalid SVG.
- `includegraphics` с отсутствующим, повторным или переименованным asset.
- Повторный asset с тем же content hash.
- Большой raster, HEIC, orientation и server-side WebP fallback.
- Расхождение порядка/числа задач между новой LaTeX revision, решением, JSON topics и SQLite; такое изменение требует явного Staff-сопоставления.
- Частичная публикация: condition есть, solution ещё нет.
- Telegram-rich output, который превышает лимит или использует неподдерживаемую конструкцию.
- PDF, который собрался, но визуально обрезал таблицу/рисунок.
- Аудитория, которая стала дубликатом только после Unicode NFKC + casefold, либо историческая комната со школьниками разных групп.

## Что не является совместимостью

- Совпадение только количества задач.
- Snapshot огромной строки HTML без semantic assertions.
- Успешный exit code при diagnostics уровня error.
- Ручной просмотр одного простого файла.
- Production import из `_external_pipelines` «на первое время» без владельца и срока удаления.

## Многокурсовые characterization references

- `_external_pipelines/a53_calc_rating_new.py` задаёт текущую методику weighted score/strength. Phase 9 сначала характеризует её на concrete group sheets, затем выбирает best group занятия; формулу нельзя пересказывать по памяти.
- Исторические tasks/results используются, чтобы доказать: synonym merge/split не меняет IDs и исходные строки, а один logical result может учитываться в нескольких group-sheet projections.
- Telegram exports и production workbook показывают legacy group/channel mapping для Phase 11 backfill. Они не становятся runtime dependency и не разрешают переписать legacy Telegram paths.
- `_vmsh_examples` дополняется только synthetic manifest ожиданий; исходные артефакты остаются неизменяемым golden corpus.

## Уточнения текущего snapshot

- В `_external_pipelines` теперь присутствуют reference-копии `z_CONSTS.py`, `z_helpers.py` и `z_cpdf.py`. Их наличие помогает читать зависимости, но не доказывает воспроизводимость Dropbox runtime или разрешение импортировать helpers в production PWA.
- `plus_reader.plus_reader` не требуется текущим v1: зависящий от него OCR кондуитов отложен. В `_external_pipelines` также добавлены reference-копии `mega_floor_lists.tex`, `per_aud_lists.tex` и `prev_conduit_template.tex`; полный рабочий `tex_templates` tree, остальные templates, Dropbox roots и внешний mail sender остаются внешними зависимостями соответствующих legacy/post-v1 процессов.
- После фактических переименований текущими именами считаются `a13_print_per_aud_conds_tex.py`, `a22_create_mails.py` и `a23_mark_compl_in_html.py`; `a15_print_per_aud_conds_html.py`, `a21_create_mails.py` и `a22_mark_compl_in_html_new.py` — только исторические названия из старого описания.
