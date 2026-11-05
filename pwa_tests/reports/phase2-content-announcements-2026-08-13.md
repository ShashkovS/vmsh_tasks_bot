# Phase 2 content announcements

Инкремент добавляет семантическую поддержку русских парных команд объявления
без выполнения `newlistok.sty` и без изменения публичного
`WebContentDocument v1`.

## Реализация

- `helpers/pwa/content/{model,parser}.py`: `AnnouncementNode`, AST schema v2,
  bounded парный разбор и blocking positional diagnostics;
- `helpers/pwa/content/{web_document,renderers}.py`: note/theorem projection,
  safe compatibility HTML и Telegram `aside`/`blockquote`;
- `vmshpwa/packages/content/src/{math-document,content.css}*`: семантический
  DOM, responsive light/dark styling и Storybook/DOM coverage;
- `vmshpwa/e2e/content-publication.spec.ts`: настоящий Staff upload/preview →
  publish → Student read с обоими видами объявления.

## Границы

- поддерживаются только `\объявление…\кобъявление` и
  `\важноеОбъявление…\кважноеОбъявление`;
- английские команды остаются explicit unsupported;
- schema БД и browser wire не меняются; terminal invalid revision не
  пересобирается, для повторной загрузки создаётся новая immutable revision.

## Проверка

- Python compiler/Telegram: **92 PASS** — positive AST/web/compatibility
  HTML/Telegram cases, role isolation, exact line/column diagnostics and
  unsupported English aliases;
- content/contract Vitest: **37 PASS**; Storybook interaction tests:
  **10 PASS**; content + contracts `tsc`, ESLint, Stylelint, Ruff and
  formatting checks: **PASS**;
- shared `WebContentDocument v1` fixture passes the existing Zod schema;
  golden characterization remains **30/30** sources, **334** problem nodes,
  **0** errors and one expected legacy-layout warning;
- announcement publication E2E passes in **Chromium, WebKit and Firefox**:
  synthetic upload has no diagnostics, both blocks appear in Staff preview
  and the published Student page, and rollback remains operational;
- all production PWA builds performed by the E2E runner: **PASS**.

The complete frontend unit run produced **612 PASS / 11 FAIL**. The failures
are confined to auth/session/search tests and do not touch the content
packages. The complete `content-publication.spec.ts` run produced the three
green announcement publication cases above; its three neighbouring
lesson-creation cases stop earlier on an unrelated strict Playwright selector
for the `Курс` label.

Implementation anchors: `helpers/pwa/content/parser.py`,
`helpers/pwa/content/web_document.py`,
`vmshpwa/packages/content/src/content.css`,
`pwa_tests/domain/test_content_compiler.py` and
`vmshpwa/e2e/content-publication.spec.ts`.
