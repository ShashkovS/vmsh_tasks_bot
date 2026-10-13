# Phase 2E: problem review frontend contract proof

Дата проверки: 28 июля 2026 года.

Это промежуточный contract/client gate сопоставления задач и metadata review.
Он дополняет backend proof
[`phase2-problem-review-api.md`](phase2-problem-review-api.md), но ещё не
закрывает production Staff workflow, Storybook или content E2E.

## Реализованная граница

- `packages/contracts/src/content-api.ts` валидирует bounded строгие ответы и
  mutation payload для full-batch matching и condition metadata grid.
- Поддержаны ровно все 23 исторических `ANS_TYPE` и четыре `PROB_TYPE`.
  Test требует answer type; non-test не может случайно сохранить скрытые поля
  проверки ответа.
- Canonical identities, candidate IDs и matched problem IDs проверяются на
  уникальность до HTTP. `insert_new`/`omit` не принимают входной legacy ID,
  `auto_position`/`manual_match` требуют его.
- Единственный legacy integer `problemId` остаётся Staff-only переходной
  границей. Student/Family contracts его не экспортируют в свои ресурсы.
- `packages/content/src/content-client.ts` реализует GET/PUT matching и
  metadata grid, передаёт exact `If-Match`, проверяет JSON через Zod и требует
  совпадения body `etag` с HTTP `ETag`.
- Добавлены стабильные TanStack Query keys и abort-aware query hooks.

## Проверки

```text
tsc --noEmit -p packages/contracts/tsconfig.json
tsc --noEmit -p packages/content/tsconfig.json
PASS

vitest run --project unit \
  packages/contracts/src/content-api.test.ts \
  packages/content/src/content-client.test.ts
24 passed

eslint <четыре затронутых TypeScript-файла>
git diff --check -- <затронутые файлы>
PASS
```

Тесты покрывают все answer types, противоречивые и повторные match, безопасную
нормализацию пустых optional fields, точные URL/PUT body/`If-Match`, строгий
response parse и рассинхронизацию header/body ETag. Сеть, Telegram, Google и
production credentials не используются.

## Оставшаяся работа

- production Staff workflow с восстановлением несохранённого черновика;
- matching/manual/insert/omit и metadata interaction stories;
- `409` refresh/compare UX и понятные field diagnostics;
- production-build Playwright upload → match → metadata → publish.
