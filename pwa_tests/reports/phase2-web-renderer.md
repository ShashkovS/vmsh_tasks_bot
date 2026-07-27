# Phase 2 browser content renderer proof

Дата проверки: 27 июля 2026 года.

Это доказательство одного вертикального инкремента этапа 2, а не закрытие всего этапа.

## Реализованная граница

- Production/read contract: `vmshpwa/packages/contracts/src/content.ts::webContentDocumentSchema`; persisted `revisionId` обязателен.
- Pre-persistence compiler preview: отдельный `webContentPreviewDocumentSchema` со строго `revisionId: null`.
- Shared Python→TypeScript fixture: `vmshpwa/packages/contracts/fixtures/content/python-compiler-preview.v1.json`; condition projection не содержит sibling `answer`, `hint` или `solution` branches.
- До recursive Zod parsing выполняется iterative bound: JSON depth 32, block depth 16, 20 000 nodes, 1 000 000 text characters.
- Основной renderer: `SemanticMathDocument`; compatibility string path: `MathHtml` через explicit semantic allowlist и DOMPurify `DocumentFragment`.
- KaTeX: main thread, `output=htmlAndMathml`, `trust=false`, `maxSize=20`, `maxExpand=1000`; ошибка одной формулы показывает local source fallback.
- Figure: external root-relative/credential-free HTTPS SVG/WebP/PNG/JPEG, единый canvas+image transform, buttons, keyboard `+/-/0`, pinch/pan, alt/caption и missing/load-error fallback.

## Security cases

Focused fixtures отклоняют целиком, без показа безопасно выглядящего остатка:

- `script` и inline event handler;
- `style` attribute;
- inline `svg`;
- `form`/`input`;
- `javascript:` link;
- `data:` image;
- произвольный semantic class.

Contract tests также отклоняют unknown raw block, duplicate problem ordinal, патологическую вложенность, превышение text budget, insecure/protocol-relative/credential-bearing asset URL.

## Storybook contract

Source: `vmshpwa/packages/content/src/math-document.stories.tsx`.

- `product-mathematical-document--semantic-document`;
- `product-mathematical-document--client-ka-te-x`;
- `product-mathematical-document--long-sheet`;
- `product-mathematical-document--responsive-table`;
- `product-mathematical-document--unsafe-html-rejected`;
- `product-mathematical-document--invalid-formula`;
- `product-mathematical-document--missing-asset`;
- `product-mathematical-document--zoom-canvas`;
- `product-mathematical-document--dark-theme`.

`zoom-canvas` проверяет focusable labelled region, keyboard zoom/reset, pinch gesture и общий transformed canvas. `responsive-table` доказывает фактический overflow и keyboard-focusable scroll region.

## Проверки

Из `vmshpwa/`:

```text
./node_modules/.bin/tsc --noEmit -p packages/contracts/tsconfig.json
./node_modules/.bin/tsc --noEmit -p packages/content/tsconfig.json
PASS

./node_modules/.bin/eslint <all touched content/contract TypeScript files> --max-warnings=0
./node_modules/.bin/stylelint packages/content/src/content.css
PASS

./node_modules/.bin/vitest run --project unit \
  packages/contracts/src/content.test.ts \
  packages/content/src/sanitizer.test.ts \
  packages/content/src/math-document.test.tsx
3 files / 33 tests PASS

./node_modules/.bin/vitest run --config vitest.storybook.config.ts \
  packages/content/src/math-document.stories.tsx
Chromium: 1 file / 9 stories PASS; addon-a11y runs in error mode

git diff --check -- <increment paths>
PASS
```

No visual snapshot was created or updated.

## Оставшиеся gates

- aiohttp response schema and persisted revision/asset resolver wiring;
- Student/Staff page integration and replacement of the older product prototype figure adapter;
- real content corpus, PDF and Telegram-rich derivative comparison;
- storage/S3 delivery and CSP/Trusted Types browser E2E;
- Student/Family KaTeX precache measurement and later font subsetting;
- manual mobile-light/desktop/dark visual approval before snapshot update.
