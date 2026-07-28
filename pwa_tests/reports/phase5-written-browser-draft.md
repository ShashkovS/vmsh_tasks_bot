# Phase 5E — browser photo pipeline and durable written draft

Дата проверки: 2026-07-28.
Revision реализации: `d3b29f2`.

## Проверяемый результат

- `apps/student/src/image-compression.ts` создаёт одноразовый Vite worker,
  ограничивает ожидание, завершает worker при success/fallback/abort и принимает
  только непустой WebP с обеими сторонами не больше 1920 px.
- `apps/student/src/workers/image-compression.worker.ts` учитывает EXIF
  orientation через `createImageBitmap`, уменьшает длинную сторону до 1920 и
  возвращает явный server fallback при невозможности decode/WebP/canvas.
- `packages/offline/src/written-submission-draft.ts` немедленно хранит текст,
  порядок страниц и resumable server IDs в namespaced `localStorage`, а WebP
  или временный source для server fallback — в owner-scoped Dexie table
  `writtenDraftPhotos`.
- Перезапуск store восстанавливает текст, бинарные страницы и порядок. Потерянная
  или повреждённая половина записи сверяется и очищается; чужой owner, другой
  runtime instance и другая revision не становятся текущим черновиком.
- При ошибке записи `localStorage` добавленный IndexedDB blob компенсирующе
  удаляется. Logout/session expiry/account switch удаляют бинарные страницы
  владельца вместе с остальным offline cache.
- Максимум — 10 страниц. Исходный файл не сохраняется после успешного client
  WebP; он временно остаётся только при явном server fallback и должен быть
  удалён после будущего server receipt.

## Автоматические доказательства

- Focused browser/offline suite:
  `apps/student/src/image-compression.test.ts`,
  `packages/offline/src/written-submission-draft.test.ts`,
  `packages/offline/src/authentication-store.test.ts`,
  `packages/offline/src/database.test.tsx` — **28 PASS**.
- `make pwa-lint` — PASS.
- `make pwa-typecheck` — PASS.
- `make pwa-test` — frontend **45 files / 344 PASS**; Python PWA
  **1215 PASS / 3 intentional skips / 1 existing SymPy warning**.
- `make pwa-build` — PASS; Student и Family `injectManifest` service workers
  собраны. Production MSW не включался.
- `git diff --check` для файлов инкремента — PASS.

## Что этот proof ещё не доказывает

- Canonical Student composer пока не вызывает новый boundary, поэтому отдельный
  worker chunk и thumbnail lifecycle должны быть доказаны следующим browser
  vertical/E2E, а не фактом общей production-сборки.
- Resumable multi-step outbox (create → photos → reorder → submit), реальный
  aiohttp transport, reload E2E, live test S3, post-submit replacement,
  reassignment/backfill и visual owner gate остаются открыты.
- Storybook snapshots не менялись.
- Telegram, Google, NATS, live S3 и `db/vmsh.db` этим инкрементом не
  использовались.
