# Phase 5E–5F — browser photo pipeline, durable draft and Student delivery

Дата проверки: 2026-07-28.
Revisions реализации: `d3b29f2`, `4e835ec`, `2158398`.

## Проверяемый результат

- [`image-compression.ts`](../../vmshpwa/apps/student/src/image-compression.ts)
  создаёт одноразовый Vite worker, ограничивает ожидание, завершает worker при
  success/fallback/abort и принимает только непустой WebP с обеими сторонами не
  больше 1920 px. Production build содержит отдельный
  `image-compression.worker-*.js` chunk.
- [`image-compression.worker.ts`](../../vmshpwa/apps/student/src/workers/image-compression.worker.ts)
  учитывает EXIF orientation через `createImageBitmap`, уменьшает длинную
  сторону до 1920 и возвращает явный server fallback при невозможности
  decode/WebP/canvas.
- [`written-submission-draft.ts`](../../vmshpwa/packages/offline/src/written-submission-draft.ts)
  немедленно хранит текст, порядок страниц и resumable server IDs в namespaced
  `localStorage`, а WebP или временный source для server fallback — в
  owner-scoped Dexie table `writtenDraftPhotos`.
- Реальный WebKit показал, что сохранение `File`/`Blob` в IndexedDB может
  завершаться `UnknownError`. Новые writers поэтому сохраняют переносимый
  `ArrayBuffer`, а Blob восстанавливается только на preview/upload boundary;
  чтение старых Blob-записей остаётся совместимым.
- Перезапуск store восстанавливает текст, бинарные страницы и порядок. Потерянная
  или повреждённая половина записи сверяется и очищается; чужой owner, другой
  runtime instance и другая revision не становятся текущим черновиком.
- При ошибке записи `localStorage` добавленные IndexedDB bytes компенсирующе
  удаляются. Logout/session expiry/account switch удаляют бинарные страницы
  владельца вместе с остальным offline cache.
- [`student-written-submission.tsx`](../../vmshpwa/apps/student/src/student-written-submission.tsx)
  подключён к настоящей focused task page для письменных и устных задач. Он
  показывает preview страниц, сохраняет текст и порядок до подтверждения,
  допускает максимум 10 страниц, блокирует редактирование queued evidence и
  продолжает тот же тред после предыдущей проверки.
- Durable outbox выполняет строго resumable цепочку
  create → upload → optional reorder → submit. Для одной страницы лишний
  reorder не отправляется; receipt очищает `localStorage`, Dexie bytes и outbox
  только после server confirmation. Offline queue автоматически продолжается
  при возврате связи.
- Shared [`SubmissionComposer`](../../vmshpwa/packages/product/src/submission-composer.tsx)
  не оставляет активных контролов у замороженного queued draft. Кнопка поворота
  attachment не показывается, если product boundary не предоставляет реальное
  действие.
- E2E gateway закрывает upstream socket, но не вызывает `close()` у downstream,
  чей WebSocket upgrade оборвался до `prepare()`. Это устраняет ложные ошибки
  при переходе браузера offline.

## Автоматические доказательства

- `make pwa-lint` — **PASS**.
- `make pwa-typecheck` — **PASS**.
- `make pwa-build` — **PASS**; Student и Family `injectManifest` service
  workers собраны, Student содержит отдельный compression-worker chunk,
  production MSW не включался.
- Полный frontend unit checkpoint — **47 файлов / 359 PASS**.
- Полный Python PWA checkpoint — **1215 PASS / 3 intentional skips / 1
  existing SymPy warning**.
- Focused E2E gateway regression — **17 PASS**.
- Storybook browser mode — **38 файлов / 188 PASS**, включая interaction story
  `product-submission--queued` с addon-a11y в режиме `error`.
- Production-build Playwright
  `Phase 5: a written draft with a photo survives reload and resumes exactly once`
  — **3/3 PASS** в Chromium, WebKit и Firefox. Сценарий использует настоящий
  aiohttp, отдельную seeded SQLite и filesystem media adapter, без MSW.
- E2E доказывает: admin публикует письменную задачу; Student вводит текст и
  фото; client создаёт WebP; reload восстанавливает draft; offline submit не
  делает сетевых writes; reconnect выполняет ровно один create, upload и submit;
  серверный thread содержит submitted text и WebP evidence.
- `git diff --check` для инкремента — **PASS**.

## Что этот proof ещё не доказывает

- Post-submit pre-review replacement как отдельная атомарная операция,
  legacy backfill/reassignment и Staff review относятся к следующим
  инкрементам.
- Live test S3 upload/read/public-GET/delete уже разрешён владельцем, но этим
  browser checkpoint не выполнялся: E2E намеренно остаётся hermetic на
  filesystem adapter.
- Owner visual gate для focused Student composer ещё не принят; visual
  snapshots не обновлялись.
- Telegram, Google, NATS, live S3 и `db/vmsh.db` этим инкрементом не
  использовались.
