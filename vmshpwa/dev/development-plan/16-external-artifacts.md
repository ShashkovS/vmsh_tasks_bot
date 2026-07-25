# Исторические артефакты и стратегия совместимости

## Главное правило

`_vmsh_examples` и `_external_pipelines` — входы для анализа и тестов, но не место разработки PWA. Их нельзя молча править, импортировать как production-package или объявлять устаревшими без сравнительного отчёта. Все реально используемые еженедельные скрипты остаются рабочими до полного переноса соответствующего процесса в Staff/PWA.

## `_vmsh_examples`: golden corpus

Сейчас каталог содержит примеры условий/решений нескольких уроков и уровней, а также JSON-темы. Встречаются:

- исходники с явной Windows Cyrillic/CP1251 encoding;
- пользовательские LaTeX macros;
- TikZ, `includegraphics`, таблицы, перечисления, подпункты и геометрия;
- совмещённые source-файлы с условиями и решениями;
- JSON вида `results[].problem_id` + `topics[]`.

Планируемый test manifest: `vmshpwa/fixtures/content/golden-manifest.yaml`. Он не копирует исходники, а ссылается на них относительными путями и фиксирует:

- ожидаемую encoding и source SHA-256;
- season/lesson/level и вид документа;
- ожидаемые позиции задач и итог явно подтверждённого сопоставления между revisions;
- ожидаемое число задач, изображений и diagnostics;
- допустимые и недопустимые warning codes;
- snapshot paths производной canonical AST/JSON;
- ручной visual approval для PWA, Telegram preview и PDF; обязательный минимум — три листка одного уровня.

Golden snapshots должны быть структурными и небольшими. Большие HTML/PDF/WebP не коммитятся без причины; для них хранятся hash, dimensions и screenshot/visual evidence.

## `_external_pipelines`: карта замены

| Артефакт                             | Историческая ответственность                | Новый владелец                                        | Этап и proof                                 |
| ------------------------------------ | ------------------------------------------- | ----------------------------------------------------- | -------------------------------------------- |
| `a00_update_db.py`                   | Получение/копирование production DB         | deployment/backup runbook, не UI                      | Этап 11: dry-run backup/restore              |
| `a01_school_to_conduit.py`           | Перенос школьных данных в ведомости         | Staff import/export service                           | Этап 10: parity report                       |
| `a02_welcome_aud.py`                 | Telegram-сообщения об аудитории по `IDd`    | legacy Telegram adapter; Staff не заменяет отправку в v1 | Этап 7: characterization, без cutover     |
| `a11_spis_from_xls.py`               | `IDd`/уровень/аудитория, списки и TeX/PDF   | одноразовый classroom dry-run/import; печатный раздел Staff во второй версии | Этап 7 и отдельная фаза print |
| `a12_dum_tex_files.py`               | Условия, решения, teacher/conduit documents | content compiler                                      | Этап 2: golden corpus                        |
| `a13_print_per_aud_conds_tex.py`     | Печатные материалы по аудиториям            | будущий classroom print command                       | Вторая версия                                |
| `a14_zall_auds_pdf.py`               | PDF по уровню/аудитории                     | PDF derivative и будущий print UI                     | Этап 2; UI во второй версии                  |
| `a16_html_from_tex.py`               | LaTeX → исторический HTML                   | новый parser/compiler                                 | Этап 2: characterization + visual comparison |
| `a16_topics_to_html.py`              | Темы задач → HTML                           | metadata/topics renderer                              | Этап 2/10                                    |
| `a17_upload_to_website.py`           | FTP-публикация                              | S3 storage + publication records                      | Этап 2                                       |
| `a18_conduit_recognition.py`         | OCR/слияние ведомостей                      | будущие Staff import diagnostics                      | После первой версии                          |
| `a19_from_excel_into_bot_via_api.py` | Импорт oral/school marks                    | будущий Staff bulk result import                      | После первой версии                          |
| `a20_подсказки.py`                   | Извлечение подсказок                        | content compiler                                      | Этап 2                                       |
| `a21*`                               | Графики и отчёты                            | statistics read models/visx                           | Этап 9/10                                    |
| `a22*`                               | Email-операции                              | отдельная admin-задача                                | Вторая–третья версия                         |
| `a23*`                               | Метки сложности                             | metadata grid/import                                  | Этап 10                                      |
| `a52*`                               | Teacher statistics                          | Staff statistics                                      | Этап 9/10                                    |
| `a53*`                               | Rating/complexity calculations              | аналитический job с версионированным алгоритмом       | Этап 9/10                                    |
| `a54*`                               | Violin/report                               | Student/Family/Staff statistics                       | Этап 9                                       |
| `edt_tasks_parser.py`                | Более новый parser/TikZ/assets/S3           | источник характеристик нового compiler                | Этап 2                                       |
| `mathimg_endpoints.py`               | HTTP image conversion                       | server fallback adapter                               | Этапы 2/5                                    |
| `mathimg_service.py`                 | Hash, SVG/WebP, ImageMagick/HEIC, S3        | media conversion service внутри существующего backend | Этапы 2/5                                    |
| `routes.py`, `tokens.py`             | Signed-cookie + refresh patterns            | reference для auth, без прямого копирования секретов  | Этап 1                                       |

## Правило characterization

Перед заменой скрипта:

1. Выбрать 3–10 репрезентативных inputs, включая самый сложный реальный пример.
2. Зафиксировать текущий observable output: структура, ключевые числа, filenames, hashes или screenshots.
3. Описать намеренные расхождения нового результата.
4. Сделать новый unit/integration test независимым от запуска исторического скрипта.
5. Один раз выполнить сравнительный report и приложить его к proof этапа.
6. Не удалять старый operational path, пока владелец продукта не подтвердит parity/cutover.

Первый Google cutover относится к листам «Задачи» и «Старые» файла `_external_pipelines/ВМШ 2025-26, информация для бота ВМШ — prod.xlsx`. Surveys, email и очный импорт результатов не входят в первую версию.

## Одноразовый перенос аудиторий

Для первого запуска этап 7 получает отдельный import tool, но не постоянный Excel/Google workflow. Исторические `a11_spis_from_xls.py` и `a02_welcome_aud.py` используются только для понимания observable input/output.

Минимальный вход: колонки `IDd`, `Уровень`, `Аудитория` текущего Excel-export. До любой записи dry-run обязан показать:

- число строк и уникальных школьников;
- неизвестные/дублирующиеся `IDd`;
- неизвестные группы/уровни;
- пустые имена аудиторий и конфликты после trim + Unicode NFKC + casefold;
- комнаты, в которых вход смешивает разные группы;
- очных школьников без аудитории;
- предлагаемый catalog, effective layout и initial assignment plan с counts по группам/комнатам.

Apply принимает hash именно просмотренного входа и dry-run report, выполняется транзакционно и пишет audit/import report. Повтор с тем же hash либо безопасно возвращает прежний receipt, либо явно останавливается как уже применённый. Сформированные комнаты не получают capacity/weight из исторических counts. После cutover catalog/layout/plan редактируются только Staff API, а Telegram-рассылка по `a02` продолжает жить отдельно до собственного решения о переносе.

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
