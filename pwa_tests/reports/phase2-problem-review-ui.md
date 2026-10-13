# Phase 2E: Staff problem review UI proof

Дата проверки: 28 июля 2026 года.

Это промежуточный production-UI gate между успешно собранной LaTeX revision и
публикацией. Он не закрывает bulk upload, PDF preview и production-build
content E2E.

## Реализованный поток

- `ProblemMatching` показывает каждую canonical задачу и требует явного
  решения: позиционное совпадение, существующая задача, новая задача или
  пропуск. Неполный batch не отправляется.
- `ProblemReviewWorkflow` связывает visual component с реальным
  `ContentApiClient`, использует server ETag и сохраняет matching/metadata
  drafts отдельно для `groupLessonId + revisionId`.
- Условие после matching открывает полную spreadsheet-like metadata grid:
  название, четыре task type, все 23 answer type и все исторические сообщения/
  checker fields. Hint/solution после matching переиспользуют metadata условия.
- Непроверенные legacy-строки могут содержать пустое название и старые
  противоречивые значения, чтобы администратор мог их открыть и исправить.
  Mutation и уже reviewed response остаются строгими.
- Matching и metadata drafts восстанавливаются из Staff-namespaced
  `localStorage` после remount/reload. При `409` локальная работа остаётся, а
  интерфейс сообщает о необходимости сверить новую серверную версию.
- Кнопки публикации становятся доступны только после серверного matching gate;
  для условия дополнительно требуется metadata gate.

## Storybook proof

- `product-staff-data--problem-matching-batch`;
- `pages-staff-content-publication--match-then-review-metadata`;
- `pages-staff-content-publication--hint-needs-only-structural-matching`;
- `pages-staff-content-publication--matching-draft-survives-reload`;
- `pages-staff-content-publication--metadata-draft-survives-reload`.

Targeted browser run двух story-файлов: **14 PASS**. В прогоне также повторно
проверены upload/preview/publication, missing-assets recovery, rollback,
расписание и publication conflict.

## Технические проверки

```text
tsc --noEmit -p packages/contracts/tsconfig.json
tsc --noEmit -p packages/product/tsconfig.json
tsc --noEmit -p apps/staff/tsconfig.json
PASS

eslint <затронутые contracts/product/staff files>
PASS

vitest run --project unit \
  packages/contracts/src/content-api.test.ts \
  packages/content/src/content-client.test.ts
24 passed

vitest run --config vitest.storybook.config.ts \
  apps/staff/src/content-page.stories.tsx \
  packages/product/src/staff-data.stories.tsx
14 passed

apps/staff: tsr generate + vite build
PASS
```

Visual snapshots не обновлялись. Новые mobile-light/desktop состояния требуют
ручного просмотра владельцем до закрытия design gate.

## Оставшаяся работа Phase 2

- production-build Playwright upload → matching → metadata → publish;
- owner visual approval и только затем snapshot baseline;
- Staff-openable generated PDF и bulk upload;
- полноценный UI field diagnostics из server details, если backend начнёт
  возвращать точный cell path для cross-row ошибок.
