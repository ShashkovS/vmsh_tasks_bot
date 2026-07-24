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
6. generation preview: web и Telegram; PDF derivative проверяется regression-тестом, а print UI относится ко второй версии;
7. редактирование метаданных;
8. approval и атомарная публикация выбранного уровня;
9. immutable version/audit и возможность rollback.

Два preview обязательны до публикации: Student web с настоящим client KaTeX и Telegram Rich Message/media. Print/admin pipeline сознательно перенесён во вторую версию; до него три листка одного уровня из `_vmsh_examples` всё равно сравниваются в PWA, Telegram и PDF.

## Задачи и метаданные

Обязательного ID в LaTeX нет. Parser получает задачи и решения по порядку и сопоставляет их с legacy `problems`; изменение числа/структуры требует отдельного Staff reconciliation до publication. Внутренний problem record содержит lesson, level, ordinal/item, title, kind, answer input type и checker configuration. Одинаковое название создаёт кандидата synonym-group, который подтверждает admin.

LaTeX в Staff не редактируется. Metadata grid содержит название, task type, answer type, validation/wrong/congratulation messages и optional topic tags; поддерживает keyboard navigation и batch table upload. Ошибочные строки импорта пропускаются и попадают в явный report.

Все исторические форматы ответов сохраняются. Invalid-format не расходует attempt, после правильного ответа можно отправлять снова, а все ответы остаются в истории. `cor_ans_checker` редактируется trusted admin; тестовые examples желательны, но не блокируют publication. Пока checker не настроен, ответ получает pending status и позже проходит admin `problem_recheck`.

## Assets

Библиотека content-addressed: binary hash определяет object key, одинаковые assets переиспользуются. Source хранит логическое имя и связь с hash. Pipeline предлагает match по имени/hash/preview; недостающие assets показывает отдельным blocking списком и никогда не заменяет пустой картинкой.

TikZ компилируется контролируемым toolchain в отдельный SVG object в S3 и подходящие print/Telegram производные. SVG не инлайнится в HTML. Для каждого рисунка сохраняются alt/описание, dimensions и provenance. Zoomable figure открывает изображение без потери доступной подписи. Реализация наследует проверенные операции `mathimg_service.py`: content hash, `pdflatex`, PDF→SVG и S3 upload.

## Версии и откат

Публикация может быть scheduled и выполняется независимо по уровню/типу. Student, который открывал прежнее условие, видит заметный update marker; teacher review показывает последнюю опубликованную версию. Скрытие занятия убирает его из Student UI как неопубликованное. Старый публичный сайт пока обновляется внешними скриптами и не входит в этот pipeline.
