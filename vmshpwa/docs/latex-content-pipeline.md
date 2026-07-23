# LaTeX и content pipeline

## Единственный источник

Условие, подсказка и решение хранятся как версионируемый LaTeX source. Безопасный HTML для web, Telegram Rich Message HTML, SVG/WebP для рисунков и PDF для печати — воспроизводимые производные конкретной версии source и toolchain. Ручное редактирование производного HTML/PDF запрещено.

Новый parser/converter использует опыт `_external_pipelines/a16_html_from_tex.py` и `edt_tasks_parser.py`, но не копирует их как непрозрачный скрипт. LaTeX сначала превращается в нормализованное document representation с явными math/asset/list/table nodes, а затем — в channel-specific output.

## Web и Telegram renderers

Web HTML сохраняет исходные LaTeX expressions в безопасных math nodes. KaTeX работает на клиенте с HTML+MathML output; его CSS и fonts собираются Vite и входят в precache Student/Family. Текущий полный набор увеличивает precache примерно до 1.4 MiB; после стабилизации корпуса нужно оставить необходимые web-форматы/subsets с regression-набором реальных формул. Выделение/copy helper и интерактивное меню формул отключены, но assistive semantics не удаляются.

Telegram renderer создаёт HTML для Bot API 10.1+ `sendRichMessage`: inline math становится `<tg-math>`, display math — `<tg-math-block>`, а headings, lists, tables, details, quotations и media проходят строгий Telegram allowlist. Это отдельный dialect и не передаётся в legacy `sendMessage(parse_mode=HTML)`. Pipeline проверяет Telegram limits (characters, blocks, nesting, media и table columns) до публикации.

## Загрузка урока

Материалы разделены по уровню. Условия и решения загружаются отдельными файлами, по одному или массовым набором; решения могут появиться позже. Импорт проходит стадии:

1. upload и content hash;
2. parse/normalize без публикации;
3. поиск команд, задач, подпунктов, ссылок и assets;
4. diagnostics с точной позицией и severity;
5. сопоставление недостающих изображений;
6. generation preview: web, Telegram и print PDF;
7. редактирование метаданных;
8. approval и атомарная публикация выбранного уровня;
9. immutable version/audit и возможность rollback.

Два preview обязательны до публикации: Student web с настоящим client KaTeX и Telegram Rich Message/media. PDF отдельно проверяется как печатный артефакт. Staff может показать preview готового PDF, но печать всегда выполняется PDF pipeline, а не browser print CSS.

## Задачи и метаданные

Задача получает stable ID, lesson, level, display number, title, kind (test/written/oral), answer input type, deadline rules, hint/solution visibility и checker configuration. Одинаковое нормализованное название внутри урока создаёт кандидата `synonym-group`, но объединение подтверждает человек.

Staff metadata grid работает как spreadsheet: keyboard navigation, multi-select, bulk edit и TSV copy/paste с dry-run diagnostics. Ошибка одной строки не должна незаметно применить остальные.

Исторические типы тестовых ответов представлены явными схемами UI: свободный текст, число/выражение, один вариант, несколько вариантов и прочие реально встречающиеся checker contracts. `cor_ans_checker` редактируется trusted admin, сохраняет нынешнюю exec-совместимость и имеет tests/diff/audit/rollback.

## Assets

Библиотека content-addressed: binary hash определяет object key, одинаковые assets переиспользуются. Source хранит логическое имя и связь с hash. Pipeline предлагает match по имени/hash/preview; недостающие assets показывает отдельным blocking списком и никогда не заменяет пустой картинкой.

TikZ компилируется контролируемым toolchain в отдельный SVG object в S3 и подходящие print/Telegram производные. SVG не инлайнится в HTML. Для каждого рисунка сохраняются alt/описание, dimensions и provenance. Zoomable figure открывает изображение без потери доступной подписи. Реализация наследует проверенные операции `mathimg_service.py`: content hash, `pdflatex`, PDF→SVG и S3 upload.

## Версии и откат

Публикация и rollback выполняются независимо для каждого уровня и типа материала. Уже отправленная submission всегда ссылается на версию условия, которую видел ученик. Новая версия может потребовать уведомление, отмену автопроверки и явный recheck; эти эффекты показываются до подтверждения.
