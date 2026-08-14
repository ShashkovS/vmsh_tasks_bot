# Матрица поддержки content compiler

Этот документ фиксирует реализованную границу Phase 2B. Авторитетные продуктовые
правила находятся в [LaTeX/content pipeline](latex-content-pipeline.md), а
критерии закрытия всего этапа — в
[плане Phase 2](../dev/development-plan/06-phase-2-content.md). Текущий срез не
реализует HTTP upload/publication UI, не доказывает live S3 roundtrip,
production backfill или реальную отправку в Telegram.

## Вход и безопасность

| Возможность                        | Состояние      | Реализация и доказательство                                                                                                                                        |
| ---------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| UTF-8, UTF-8 BOM и Windows-1251    | Поддерживается | Raw bytes и их SHA-256 сохраняются отдельно от нормализованного Unicode; CRLF нормализуется только для разбора.                                                    |
| Позиционные diagnostics            | Поддерживается | File, one-based line/column и Unicode offset принадлежат каждому AST node и diagnostic.                                                                            |
| Ограниченный разбор                | Поддерживается | Размер source, глубина групп, число nodes и размер TikZ ограничены; seeded malformed-input corpus проверяет детерминированность.                                   |
| Неизвестные команды и окружения    | Fail closed    | Получают явный error diagnostic и блокируют последующую публикацию.                                                                                                |
| TeX file/output/dynamic primitives | Запрещены      | `input`, `openout`, `write`, `directlua`, `catcode` и родственные команды обнаруживаются и внутри TikZ; shell не вызывается.                                       |
| Canonical logical paths            | Поддерживается | Source name обязан быть ограниченным NFKC-stable relative POSIX path без `..`, controls, backslash и aliases. Asset reference не может выйти из logical namespace. |

## Семантическое представление

| Конструкция                                      | Canonical AST                                                                               | Browser derivative                                                                              | Telegram Rich                                        |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| Условие, подсказка, ответ, решение               | Отдельные ветки одного problem node                                                         | Выбирается ровно один разрешённый material kind; condition не содержит соседних secret branches | То же правило выбора применяется до рендера          |
| Paragraph, heading, strong, emphasis, code, link | Typed nodes                                                                                 | Versioned JSON nodes                                                                            | Strict allowlisted tags/attributes                   |
| Inline/display math                              | Raw LaTeX math node                                                                         | Inline math и отдельная formula node для client KaTeX                                           | `<tg-math>` и `<tg-math-block>`                      |
| Подпункты и ordered/unordered lists              | Typed recursive blocks                                                                      | Typed recursive blocks                                                                          | Структурные list tags                                |
| Таблицы                                          | Rows/cells                                                                                  | До 200 строк и 20 колонок; превышение отклоняется без обрезки                                   | До 20 колонок по Bot API limits                      |
| `\объявление` и `\важноеОбъявление`              | Typed announcement block (`regular`/`important`) с рекурсивными children                    | Существующий `callout`: спокойный `note` либо акцентный `theorem` с меткой «Важно»              | Отдельный `aside` либо `blockquote` с меткой «Важно» |
| External figures                                 | Logical name, alt, optional known hash                                                      | `missing` либо explicit published asset descriptor; SVG остаётся внешним URL                    | Только безопасный public HTTP(S) media URL           |
| TikZ                                             | Figure node с effective source/hash: контекстные declarations, inline и positional wrappers | После converter — внешний sanitized SVG asset                                                   | После converter — совместимая media derivative       |
| Legacy print-layout                              | Не становится семантикой                                                                    | Игнорируется либо даёт warning                                                                  | Не переносится как presentation markup               |

Corpus-driven compatibility для архива 2024–2025 дополнительно сохраняет
содержимое declaration-style `{\it …}`, `{\bf …}`, `{\tt …}`, `\makebox`,
`\verb`, `\textsuperscript`, `\underline` и `\overline`. `multicols`
линеаризуется, `multline*` становится display math, `table` сохраняет вложенную
таблицу, а `\putthere{…}{…}{TikZ}` отбрасывает только позиционирование.
Таблица с самостоятельными рисунками разворачивается в последовательность
figure blocks с warning, включая `resizebox` внутри ячеек. Несколько
`tikzpicture` в одном `righttikz[w]`/`lefttikz[w]` сохраняются одним asset;
непарный print-only `center` восстанавливает вложенный TikZ до semantic boundary.
Это bounded adapters известных конструкций, а не
исполнение пользовательских TeX-определений.

Символ замены `U+FFFD` является отдельной blocking-ошибкой повреждённого
источника; сотни команд из утраченных букв не выдаются как независимые
`unknown_macro`. Одиночный `\` также имеет отдельную позиционную диагностику.

Internal Python `DocumentAst` содержит все ветки и source spans и никогда не
является API payload. Browser wire — только строгий
[`WebContentDocument v1`](../packages/contracts/src/content.ts); preview до
сохранения имеет `revisionId: null`, а public read contract требует канонический
revision ID. Совместная синтетическая fixture находится в
[`python-compiler-preview.v1.json`](../packages/contracts/fixtures/content/python-compiler-preview.v1.json)
и одновременно проверяется Python и Zod tests. Raw/generated HTML остаётся
диагностическим preview, а не основным browser wire contract.

Объявления распознаются только по русским парным командам
`\объявление…\кобъявление` и
`\важноеОбъявление…\кважноеОбъявление`. Незакрытые, несовпадающие, пустые,
вложенные и лишние завершающие команды дают blocking positional diagnostic;
TeX-определения из `newlistok.sty` compiler не исполняет.

## Assets и внешний toolchain

- TikZ converter использует фиксированный argv `pdflatex -no-shell-escape` →
  `pdf2svg`, isolated temporary files, timeout и redacted failures.
- Effective TikZ source формирует
  [`helpers/pwa/content/tikz.py`](../../helpers/pwa/content/tikz.py): explicit
  `% addToTikz`, dependency-scoped macros/constants/styles/libraries и layout
  wrapper входят в hash; comments, document tail и невызванные macro bodies —
  нет. Static standalone preparation не запускает toolchain.
- Raster converter принимает bounded input, уменьшает изображение до 1920 px и
  сохраняет только WebP; исходный HEIC/JPEG/PNG не является производной для
  хранения.
- SVG проходит allowlist sanitizer: запрещены scripts, event handlers,
  external/data URLs, unsafe CSS и чрезмерные размеры/число nodes.
- Converter сам не имеет storage side effects. Unit-tested
  [`ContentAssetService`](../../helpers/pwa/content/asset_service.py) соединяет
  его с общим `ObjectStorage`, content-addressed key, immutable media row и
  revision attachment; 5/5 service tests доказывают content-addressed key,
  retry и порядок storage → repository → attachment. Live test-S3 roundtrip,
  cleanup/reconciliation после DB/attach failure и HTTP orchestration остаются
  отдельными gates.

Локальный synthetic smoke с настроенным
`/Users/sergeyshashkov/bin/pdflatex` доказывает реальную цепочку TikZ → PDF →
SVG и raster → WebP. Конкретный machine path не входит в revision/provenance и
не должен попадать в публичные diagnostics.

## Telegram dialect

Renderer и validator закреплены на проверенном 27 июля 2026 dialect Telegram
Bot API 10.2 `sendRichMessage`, а не на legacy `sendMessage(parse_mode=HTML)`.
Поддерживаются документированные inline/block tags, named и numeric entities,
anchors/references, lists, quotations, tables, details, maps, media,
collage/slideshow и Telegram math. Custom-emoji `<img>` остаётся inline;
остальные media blocks валидируются отдельно. Links/attributes/nesting и
структурные children проверяются строгим allowlist.

Перед send проверяются точные границы: 32 768 UTF-8 characters, 500 blocks,
nesting 16, 50 media и 20 table columns. Boundary tests покрывают значения
ровно на лимите и на единицу больше. Renderer version, dialect и применённые
limits входят в derivative metadata; live отправка в test channel остаётся
отдельным opt-in proof.

## Golden corpus и известные ограничения

[`phase2-content-compiler.md`](../../pwa_tests/reports/phase2-content-compiler.md)
воспроизводится из единственного manifest
[`golden-manifest.json`](../fixtures/content/golden-manifest.json). Текущий
результат: 30/30 TeX sources, 334 problem nodes, 0 structural failures и одно
ожидаемое warning о legacy print-layout. PDF/JSON входят в общий manifest gate,
но этим pure compiler не разбираются.

Полный owner-local corpus 2024–2025 проверяется воспроизводимым
[`content_archive_diagnostics.py`](../scripts/content_archive_diagnostics.py).
Текущий результат и все оставшиеся line/column diagnostics находятся в
[`phase2-content-archive-2024-2025-errors.md`](../../pwa_tests/reports/phase2-content-archive-2024-2025-errors.md);
архив и его симлинк в report не копируются и не изменяются.

Полная рекурсивная проверка двух owner-local архивов выполняется
[`content_archive_recursive_diagnostics.py`](../scripts/content_archive_recursive_diagnostics.py)
строго по маскам `usl-??-?.tex` / `usl-??-?-sol.tex`. Файлы с буквальным
`U+FFFD` исключаются и перечисляются отдельно; роль `solution` назначается
только суффиксу `-sol`. Текущий полный позиционный результат находится в
[`phase2-content-archive-all-errors.md`](../../pwa_tests/reports/phase2-content-archive-all-errors.md).
Legacy `picture` остаётся warning и непрозрачным блоком до конвертации в TikZ.
Общие print-layout wrappers (`npcopy`, box/minipage/table wrappers, layout
registers) не исполняются и не дублируют semantic problems. Локальные языки
рисунков, домино и динамический `csname` сознательно не добавлены в dialect.

До полного закрытия Phase 2 остаются:

- compiler/repository service и HTTP orchestration с immutable revisions и derivatives;
- live test-S3 content-asset roundtrip и reconciliation/cleanup orphan objects;
- Staff diagnostics/missing-assets/preview/publication/rollback UI;
- independent group publication windows и historical lessons 1–38 backfill;
- opt-in real Telegram Rich Message lifecycle;
- representative PDF comparison, Storybook visual approval и browser E2E.
