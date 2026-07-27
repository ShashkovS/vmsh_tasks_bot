# Матрица поддержки content compiler

Этот документ фиксирует реализованную границу Phase 2B. Авторитетные продуктовые
правила находятся в [LaTeX/content pipeline](latex-content-pipeline.md), а
критерии закрытия всего этапа — в
[плане Phase 2](../dev/development-plan/06-phase-2-content.md). Текущий срез не
реализует HTTP upload/publication UI, не доказывает live S3 roundtrip,
production backfill или реальную отправку в Telegram.

## Вход и безопасность

| Возможность | Состояние | Реализация и доказательство |
| --- | --- | --- |
| UTF-8, UTF-8 BOM и Windows-1251 | Поддерживается | Raw bytes и их SHA-256 сохраняются отдельно от нормализованного Unicode; CRLF нормализуется только для разбора. |
| Позиционные diagnostics | Поддерживается | File, one-based line/column и Unicode offset принадлежат каждому AST node и diagnostic. |
| Ограниченный разбор | Поддерживается | Размер source, глубина групп, число nodes и размер TikZ ограничены; seeded malformed-input corpus проверяет детерминированность. |
| Неизвестные команды и окружения | Fail closed | Получают явный error diagnostic и блокируют последующую публикацию. |
| TeX file/output/dynamic primitives | Запрещены | `input`, `openout`, `write`, `directlua`, `catcode` и родственные команды обнаруживаются и внутри TikZ; shell не вызывается. |
| Canonical logical paths | Поддерживается | Source name обязан быть ограниченным NFKC-stable relative POSIX path без `..`, controls, backslash и aliases. Asset reference не может выйти из logical namespace. |

## Семантическое представление

| Конструкция | Canonical AST | Browser derivative | Telegram Rich |
| --- | --- | --- | --- |
| Условие, подсказка, ответ, решение | Отдельные ветки одного problem node | Выбирается ровно один разрешённый material kind; condition не содержит соседних secret branches | То же правило выбора применяется до рендера |
| Paragraph, heading, strong, emphasis, code, link | Typed nodes | Versioned JSON nodes | Strict allowlisted tags/attributes |
| Inline/display math | Raw LaTeX math node | Inline math и отдельная formula node для client KaTeX | `<tg-math>` и `<tg-math-block>` |
| Подпункты и ordered/unordered lists | Typed recursive blocks | Typed recursive blocks | Структурные list tags |
| Таблицы | Rows/cells | До 200 строк и 20 колонок; превышение отклоняется без обрезки | До 20 колонок по Bot API limits |
| External figures | Logical name, alt, optional known hash | `missing` либо explicit published asset descriptor; SVG остаётся внешним URL | Только безопасный public HTTP(S) media URL |
| TikZ | Отдельный figure node с source/hash | После converter — внешний sanitized SVG asset | После converter — совместимая media derivative |
| Legacy print-layout | Не становится семантикой | Игнорируется либо даёт warning | Не переносится как presentation markup |

Internal Python `DocumentAst` содержит все ветки и source spans и никогда не
является API payload. Browser wire — только строгий
[`WebContentDocument v1`](../packages/contracts/src/content.ts); preview до
сохранения имеет `revisionId: null`, а public read contract требует канонический
revision ID. Совместная синтетическая fixture находится в
[`python-compiler-preview.v1.json`](../packages/contracts/fixtures/content/python-compiler-preview.v1.json)
и одновременно проверяется Python и Zod tests. Raw/generated HTML остаётся
диагностическим preview, а не основным browser wire contract.

## Assets и внешний toolchain

- TikZ converter использует фиксированный argv `pdflatex -no-shell-escape` →
  `pdf2svg`, isolated temporary files, timeout и redacted failures.
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

До полного закрытия Phase 2 остаются:

- compiler/repository service и HTTP orchestration с immutable revisions и derivatives;
- live test-S3 content-asset roundtrip и reconciliation/cleanup orphan objects;
- Staff diagnostics/missing-assets/preview/publication/rollback UI;
- independent group publication windows и historical lessons 1–38 backfill;
- opt-in real Telegram Rich Message lifecycle;
- representative PDF comparison, Storybook visual approval и browser E2E.
