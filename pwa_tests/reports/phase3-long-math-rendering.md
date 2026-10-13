# Phase 3H — длинный математический документ и KaTeX budget

Дата: 2026-07-28

Revision: `f787a64`

## Проверяемый результат

Storybook содержит воспроизводимый browser stress-сценарий, собранный из
зафиксированного golden corpus `_vmsh_examples`:

- условия начинающих занятий 39, 40 и 41 берутся из тех же strict fixtures,
  которыми сравниваются PWA, Telegram Rich и reference PDF;
- четыре независимые копии трёх листков образуют **132 задачи** и **56
  клиентских формул KaTeX**;
- каждый повтор — самостоятельное JSON-дерево: fixture проходит тот же
  `WebContentDocument v1`, что и настоящий API payload;
- дополнительно включён один корректный descriptor SVG с недоступным URL;
  ошибка загрузки обязана оставить явный fallback, alt и подпись.

Source integrity composition привязана к
`vmshpwa/fixtures/content/golden-manifest.json` с SHA-256
`ea05ba31c0d425819088d50998d85ba35fc5b4deb233dc5ef553fb57c391bf82`.
Исходные corpus-файлы не менялись.

## Политика performance-gate

`Product/Mathematical document/Performance--Long real corpus render budget`
не измеряет загрузку Storybook/Vite и не выдаёт результат за универсальный SLO.
После явного запуска story считает время через `performance.now()` от React
state transition до момента, когда все 56 `MathExpression` вышли из состояния
`pending`.

Автоматический предел **2500 мс** — намеренно мягкий catastrophic-regression
gate для локального Chromium browser mode. Он должен ловить зависание,
неограниченное раскрытие KaTeX или случайную квадратичную работу, но не падать
из-за небольшого разброса времени на разных Mac. Точное измерение каждого
запуска видно непосредственно в story; структурные инварианты проверяются
независимо от времени.

Текущий browser run прошёл за **672 мс полного story test time**, включая
interaction и структурные проверки; собственное измерение рендера уложилось в
2500 мс. Нельзя сравнивать 672 мс как чистое время React/KaTeX с будущими
запусками: это только верхняя граница длительности данного test case.

## Реализация и автоматические проверки

- fixture и recursive formula counter:
  `vmshpwa/packages/content/src/long-document-performance-fixture.ts`;
- unit-инварианты corpus workload:
  `long-document-performance-fixture.test.ts`;
- browser harness и interaction:
  `long-document-performance.stories.tsx`;
- Storybook ID:
  `product-mathematical-document-performance--long-real-corpus-budget`.

Проверено:

```text
content TypeScript + scoped ESLint
PASS

long-document-performance-fixture.test.ts + math-document.test.tsx
2 files / 7 PASS

long-document-performance.stories.tsx
Chromium browser mode: 1 file / 1 PASS
addon-a11y: error gate enabled
full story test time: 672 ms

make pwa-lint + make pwa-typecheck + make pwa-build
PASS

make pwa-test
35 TypeScript files / 285 PASS
Python PWA: 1101 PASS / 3 skip / 1 existing SymPy warning

make pwa-storybook-test
37 files / 183 PASS; addon-a11y error gate enabled
```

Interaction отдельно доказывает:

- ровно 132 `.vmsh-problem` sections;
- ровно 56 `data-math-state="rendered"` и ни одной invalid formula;
- завершение до аварийного бюджета;
- load-error SVG переходит в «Рисунок недоступен», а подпись остаётся;
- никакие visual snapshots не создаются и не обновляются.

## Границы доказательства

- Это regression gate основного потока, а не обещание одинакового времени на
  всех поддерживаемых устройствах.
- Реальные Student routes и offline cache проверены Phase 3G; здесь изолируется
  именно renderer, чтобы сеть/SQLite/service worker не маскировали регрессию.
- Ручной mobile-light/desktop visual owner gate остаётся открытым. После его
  принятия Phase 3 можно считать завершённым.
