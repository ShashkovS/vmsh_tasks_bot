# LaTeX и content pipeline

## Единственный источник

Условие, подсказка и решение хранятся как версионируемый LaTeX source. HTML для web, SVG/WebP для рисунков, PNG для Telegram и PDF для печати — воспроизводимые производные конкретной версии source и toolchain. Ручное редактирование производного HTML/PDF запрещено.

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

Два preview обязательны до публикации: student web и Telegram message/media. PDF отдельно проверяется как печатный артефакт. Печать всегда выполняется pipeline-ом PDF.

## Задачи и метаданные

Задача получает stable ID, lesson, level, display number, title, kind (test/written/oral), answer input type, deadline rules, hint/solution visibility и checker configuration. Одинаковое нормализованное название внутри урока создаёт кандидата `synonym-group`, но объединение подтверждает человек.

Staff metadata grid работает как spreadsheet: keyboard navigation, multi-select, bulk edit и TSV copy/paste с dry-run diagnostics. Ошибка одной строки не должна незаметно применить остальные.

Исторические типы тестовых ответов представлены явными схемами UI: свободный текст, число/выражение, один вариант, несколько вариантов и прочие реально встречающиеся checker contracts. `cor_ans_checker` редактируется trusted admin, сохраняет нынешнюю exec-совместимость и имеет tests/diff/audit/rollback.

## Assets

Библиотека content-addressed: binary hash определяет object key, одинаковые assets переиспользуются. Source хранит логическое имя и связь с hash. Pipeline предлагает match по имени/hash/preview; недостающие assets показывает отдельным blocking списком и никогда не заменяет пустой картинкой.

TikZ компилируется контролируемым toolchain в SVG для web и подходящие print/Telegram производные. Для каждого рисунка сохраняются alt/описание, dimensions и provenance. Zoomable figure открывает изображение без потери доступной подписи.

## Версии и откат

Публикация и rollback выполняются независимо для каждого уровня и типа материала. Уже отправленная submission всегда ссылается на версию условия, которую видел ученик. Новая версия может потребовать уведомление, отмену автопроверки и явный recheck; эти эффекты показываются до подтверждения.
