# Phase 2: real content corpus в Storybook

Дата проверки: 27 июля 2026 года.

Статус инкремента: три настоящих листка одного уровня связаны с точными
PWA/Telegram-производными и reference PDF. Visual snapshots не обновлялись;
финальное визуальное принятие владельцем всего Phase 2 остаётся отдельным gate.

## Corpus и воспроизводимость

В приёмку входят условия для начинающих занятий 39, 40 и 41 из
`_vmsh_examples`. Для каждого входа
[`content_story_corpus.py`](../../vmshpwa/scripts/content_story_corpus.py):

1. читает точные bytes `usl-<lesson>-n.tex` и reference PDF;
2. компилирует condition тем же `compile_latex`, который использует HTTP API;
3. запрещает fixture при compiler error или отсутствующей производной;
4. сохраняет source/PDF SHA-256, typed `WebContentDocument v1` и точный
   Telegram Rich HTML с renderer version/hash;
5. в режиме `check` отказывает при отсутствующем или устаревшем fixture.

Committed fixtures:

- [`lesson-39-n.v1.json`](../../vmshpwa/packages/contracts/fixtures/content/golden/lesson-39-n.v1.json);
- [`lesson-40-n.v1.json`](../../vmshpwa/packages/contracts/fixtures/content/golden/lesson-40-n.v1.json);
- [`lesson-41-n.v1.json`](../../vmshpwa/packages/contracts/fixtures/content/golden/lesson-41-n.v1.json).

Каждый документ содержит 11 задач. TypeScript boundary
[`goldenContentComparisonFixtureSchema`](../../vmshpwa/packages/contracts/src/content.ts)
повторно валидирует hashes, material kind и весь typed web document до рендера.

## Storybook и найденное расхождение

Story
[`Product/Mathematical document/Real corpus--Lessons 39–41 · PWA, Telegram and PDF`](../../vmshpwa/packages/content/src/golden-corpus.stories.tsx)
даёт выбор занятия и три представления:

- PWA — `SemanticMathDocument` с client KaTeX;
- Telegram Rich — browser preview и раскрываемый точный HTML без
  `dangerouslySetInnerHTML`;
- PDF — импортированный Vite reference artifact из `_vmsh_examples`.

Ручная light-проверка выполнена на desktop и mobile 390 px. Она обнаружила две
реальные ошибки, которые были исправлены до фиксации proof:

- длинные SHA-256 создавали горизонтальный scroll на 390 px — metadata card
  теперь переносит непрерывные строки;
- print-header macros оставляли в AST четыре source newline, а старый HTML
  renderer превращал их в высокий `<p><br/>…</p>` перед Telegram-условием.
  [`renderers.py`](../../helpers/pwa/content/renderers.py) теперь пропускает
  layout-only whitespace paragraph одинаково для web/Telegram HTML и не
  удаляет math/code или видимый текст.

После исправлений `documentElement.scrollWidth == clientWidth == 390`, Telegram
preview начинается с раздела задач и содержит 5 KaTeX-формул для занятия 41.
PWA, Telegram и встроенный reference PDF занятия 41 осмотрены вручную; PDF
показывает исходный одностраничный листок без отдельного browser print renderer.

## Автоматические проверки

```console
.venv/bin/ruff check \
  helpers/pwa/content/renderers.py \
  pwa_tests/domain/test_content_compiler.py \
  vmshpwa/scripts/content_story_corpus.py \
  pwa_tests/test_content_story_corpus.py
# All checks passed!

.venv/bin/pytest -q -n0 \
  pwa_tests/domain/test_content_compiler.py \
  pwa_tests/test_content_story_corpus.py
# 37 passed

vitest run --config vitest.config.ts packages/contracts/src/content.test.ts
# 21 passed

vitest run --config vitest.storybook.config.ts \
  packages/content/src/golden-corpus.stories.tsx
# 1 passed, addon-a11y error mode
```

Также прошли focused Prettier check и strict typecheck пакетов `contracts` и
`content`. Визуальные baselines намеренно не менялись.

## Оставшиеся границы

- Owner visual approval трёх вкладок и всех трёх занятий ещё не записан.
- Текущий реальный corpus условий 39–41 не содержит таблиц или рисунков;
  таблица, missing/available SVG/TikZ и zoom отдельно покрыты typed component
  stories. Нельзя утверждать, что reference corpus доказал то, чего в исходных
  файлах нет.
- Сравнение generated PDF нового pipeline с reference PDF и staging toolchain
  относится к оставшимся Phase-2/Phase-11 gates; здесь показан именно
  repository reference PDF.
