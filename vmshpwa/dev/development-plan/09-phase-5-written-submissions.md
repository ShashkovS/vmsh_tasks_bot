# Этап 5. Письменная сдача, media pipeline и offline outbox

## Результат

Школьник создаёт одну логическую отправку из текста и до 10 фотографий, видит сжатие/порядок/загрузку, может уйти offline и позже безопасно дослать. Работа появляется у teacher только целиком. До первого review lock её можно изменить/удалить с подтверждением; после начала проверки можно добавлять новый материал в тред, но не переписывать исходную entry. После review evidence immutable.

Дизайн-контракт этапа: [composer, attachments, sync/offline states, written-task page и Storybook stories](18-design-implementation-map.md#phase-5-design).

## Модель данных

Migration: `pwa_submission_threads_entries_assets`.

Таблицы: `submission_threads`, `submission_entries`, `submission_attachments`,
`submission_entry_replacements`,
`submission_material_reassignments`, `submission_material_reassignment_items`,
`media_assets`, `idempotency_records`.
Lazy/batch backfill `written_tasks_discussions`; legacy IDs сохраняются.
Публичный object key следует agreed pattern и не содержит имени школьника.

До review lock замена реализуется как новая draft entry и одна атомарная
операция `POST /student/api/v1/thread-entries/{newEntryId}/replace`. Она
проверяет optimistic versions старой entry, новой entry и thread; прежнюю entry
переводит в `deleted`, новую — в `submitted`, а append-only
`submission_entry_replacements` сохраняет обе ссылки и idempotency key.
Вложения и их object keys остаются привязаны к своим исходным entry; физического
слияния или перезаписи evidence нет.

Owner-confirmed core позволяет teacher перенести одно или несколько выбранных
сообщений/фотографий и показывает их Student в целевой истории. Безопасный
implementation default добавляет scoped admin, source/target preview и
post-review correction. `submission_material_reassignments` — append-only header,
который хранит школьника, исходный/целевой thread и `problem_id`, actor, server
time, request ID и причину. `submission_material_reassignment_items` перечисляет выбранные
`entry_text|attachment`: одно UI-действие может включать один или несколько
текстов/фотографий, не пряча IDs в JSON. Файл, сообщение, исходный ID и уже
зафиксированный review evidence не переписываются и не копируются: меняется
только текущая проекция истории. Школьник видит выбранный материал в треде
целевой задачи с ненавязчивой пометкой «Перенесено преподавателем»;
техническая исходная привязка остаётся в audit/provenance. Существующий verdict
автоматически не переносится и не пересчитывается.

## Client media pipeline

- Accept camera/gallery common formats; detect actual MIME, orientation and dimensions.
- Worker downsizes longest side to 1920 and encodes WebP. Начальное quality выбирается один раз по реальному photo corpus так, чтобы текст оставался читаемым; выбранное значение и размеры fixtures фиксируются в proof этапа, жёсткого product-лимита bytes нет.
- Original intentionally not stored. EXIF/GPS is stripped by decoded re-encode; это проверяется тестом, а не предполагается.
- HEIC: client conversion if reliably supported; otherwise original HEIC временно находится только в local outbox/stream and server fallback produces final WebP. Raw server temporary is deleted after commit/failure cleanup.
- UI states: selected → compressing progress → queued offline → uploading → server accepted → retry/error → locked.
- Ordering buttons up/down; optimized for 1–2 pages; no DnD dependency.
- Cancel/retry/reload must not orphan a visible entry or duplicate asset.

## Server/storage pipeline

- Streaming multipart limits per file/request; MIME sniffing, decompression-bomb and pixel bounds.
- File adapter in unit/agent/E2E; `aioboto3` adapter для opt-in local integration и production. Выделенный test bucket сейчас Beget, production target — Hetzner; `s3_url`, `s3_region`, `s3_bucket_name`, `s3_access_key`, `s3_secret_key` берутся только из соответствующего test/production credential file без provider default в PWA config. Live test дополнительно сверяет pinned endpoint/bucket fingerprint. PWA loader извлекает только storage allowlist и не делает Telegram/Google credentials обязательными.
- Server fallback использует общий converter config: `magick_path='magick'` для decode/orientation/HEIC и `cwebp_path='cwebp'` для WebP, с разрешением через service `PATH`, optional absolute override и fail-fast capability probe. Pipeline не вызывает shell и не принимает произвольные flags из upload metadata.
- Write sequence: validate → temporary object → conversion/verify hash → final key → SQLite transaction → cleanup. Compensation job finds stale temporary objects.
- Public GET URL is long/unguessable; upload and list still require auth.
- Submission entry становится видима атомарно только после всех выбранных файлов; failed attachment повторяется отдельно, не создавая частичную работу.
- `locked_at`/`locked_by_result_id` only set inside review transaction in phase 6. Delete/reorder endpoint checks lock and returns `409 ATTACHMENT_LOCKED`.

## Frontend

- Focused written task and composer in `student/src/features/submissions/written`; text-only разрешён, raw LaTeX сохраняется, но v1 не рендерится.
- Thread timeline initially shows student entries; phase 6 adds review events.
- Отдельные Student actions «дописать ответ» и «пересдать решение» ведут к одной backend operation без fake attempt numbering.
- Staff correction flow позволяет выбрать одно или несколько сообщений/фото,
  найти целевую задачу, увидеть preview последствий и подтвердить перенос. Для
  уже проверенного материала UI явно предупреждает, что immutable evidence и
  прежний verdict останутся в исходном review, а целевая задача получит только
  исправленную проекцию выбранного материала.
- Offline quota estimate and recovery: keep local preview until server acknowledgement; warnings when browser storage is low. Каждое выбранное фото сразу получает настоящую thumbnail, включая processing/upload/error states.
- Composer metadata/text/order сохраняются в account/thread/revision-scoped `localStorage`, подготовленные фотографии и outbox — в Dexie. Reload/update восстанавливает одну согласованную композицию; receipt очищает оба слоя только после успешной фиксации.
- Пользовательский интерфейс не создаёт отдельную «квитанцию», reference number или доказательный экран: успешная запись становится обычным entry/status в треде. Технический idempotency key остаётся внутри протокола.
- Logout with pending queue warns and lists count; confirmed logout may clear it.

## Tests

- Worker dimensions/rotation/WebP/metadata tests with JPEG, PNG, WebP, HEIC fixture where supported, corrupt and huge input.
- Server fallback contract against `mathimg_service.py` capabilities, without importing external module at runtime.
- Converter failure matrix: missing/disabled `magick` or `cwebp`, timeout, corrupt output, non-zero exit и cleanup временного source/output.
- Storage adapter parity, interrupted upload, S3 transient retry, hash collision, temp cleanup.
- Config/source/redaction tests: incomplete S3 tuple fail-fast, test/prod file selection, secrets absent from `repr`/logs/Sentry/health; opt-in test bucket smoke работает только в disposable prefix.
- Authorization: other student/family cannot enumerate attachment; public URL accessibility follows explicit privacy decision.
- Offline outbox crash matrix and idempotency/payload conflict.
- Reload/remount, account isolation, partial-photo recovery, PWA update и cleanup-after-receipt для связки localStorage + Dexie.
- Concurrent edit vs review completion: новая фотография до commit обязана войти в текущую проверку; thread-version conflict заставляет teacher refetch.
- Reassignment tests: owner-confirmed teacher flow для одного сообщения,
  фотографии и batch; implementation-default admin/preview/post-review cases;
  cross-student denial, immutable object/review IDs, target projection и audit.
- Storybook photo-state matrix and 1/2/10-page mobile cases.
- Playwright real aiohttp/filesystem storage: camera-file input → worker → offline/reconnect → stored → reload; no MSW.

## Критерии приёмки

- Final stored object is valid WebP ≤1920 side and contains no retained EXIF GPS.
- Original and server temporary are absent after success/cleanup.
- В runtime с включённым server fallback обе обязательные image capabilities проходят readiness probe до приёма HEIC/unsupported upload.
- При выбранном S3 adapter readiness до первого upload подтверждает endpoint/bucket/capabilities без выдачи access/secret key; automated agent/E2E остаётся hermetic на filesystem.
- Retry creates one logical entry/asset set; Telegram media group и PWA entry сводятся в один thread/provenance.
- 1–2 photos require few clear actions; 10 photos remain manageable.
- Locked material cannot be mutated through UI or direct API.
- Teacher может исправить problem association; implementation default разрешает
  scoped admin и post-review correction через preview. Append-only operation не
  меняет байты locked material и не переносит существующий verdict.
- Незавершённый текст, порядок и выбранные страницы переживают reload; conflict/ошибка не очищают draft.
- Подготовка pre-review replacement копирует доступные WebP в новый durable
  draft; до атомарного подтверждения прежняя версия остаётся действующей.
- Telegram discussions remain readable and new PWA thread does not corrupt queue behavior.

## Пруфы завершения этапа

- [x] Schema migration `0047.pwa_submission_threads_entries_assets`:
      up/down, integrity, immutable identity и legacy-row preservation:
      [`phase5-written-submission-schema.md`](../../../pwa_tests/reports/phase5-written-submission-schema.md).
- [ ] Legacy discussion backfill: owner-reviewed problem revisions и решение о
      40 531 Telegram-only строках без восстанавливаемого payload. По решению
      владельца это изображения, хранящиеся только на серверах Telegram; v1 их
      не восстанавливает и не показывает placeholder. Новый учебный год
      начинается с новых submission threads.
- [x] Demo 1/2/10 images and offline state: Storybook
      `product-submission--one-page`, `product-submission--two-pages`,
      `product-submission--ten-pages`, `product-submission--offline` и
      production-browser scenario из
      [`phase5-written-consolidated-gates.md`](../../../pwa_tests/reports/phase5-written-consolidated-gates.md).
- [x] Real media corpus: JPEG orientation/GPS → bounded WebP without metadata,
      HEIC → WebP, corrupt/oversized rejection:
      [`phase5-written-media-corpus.md`](../../../pwa_tests/reports/phase5-written-media-corpus.md).
- [x] Filesystem/S3 adapter, public GET и cleanup:
      [`phase5-written-storage-live.md`](../../../pwa_tests/reports/phase5-written-storage-live.md).
- [x] Idempotency/crash/concurrency/lock matrix:
      [`phase5-written-consolidated-gates.md`](../../../pwa_tests/reports/phase5-written-consolidated-gates.md).
- [x] Pre-review replacement migration/API/outbox/reload/3-browser E2E:
      [`pwa_tests/reports/phase5-written-replacement.md`](../../../pwa_tests/reports/phase5-written-replacement.md).
- [x] Cross-storage draft recovery/isolation/receipt cleanup:
      [`phase5-written-browser-draft.md`](../../../pwa_tests/reports/phase5-written-browser-draft.md).
- [x] Material reassignment projection/audit/permissions/history:
      [`pwa_tests/reports/phase5-written-material-reassignment.md`](../../../pwa_tests/reports/phase5-written-material-reassignment.md).
- [x] Material reassignment Staff transport и reusable interaction/a11y UI:
      [`written-material-reassignment-client.ts`](../../packages/app-shell/src/written-material-reassignment-client.ts),
      [`written-material-reassignment.tsx`](../../packages/product/src/written-material-reassignment.tsx),
      Storybook `product-review--material-reassignment` и
      `product-review--material-reassignment-post-review`.
- [ ] Storybook visual gate: automated interaction/a11y suite прошёл как
      **50 files / 239 PASS**, deterministic 1/2/10-page stories технически
      просмотрены на mobile-light 390 px и desktop 1280 px без горизонтального
      overflow. Owner visual approval остаётся открытым; snapshots не
      обновлялись. См. consolidated proof.
- [x] Production-build Playwright in Chromium/WebKit/Firefox with real aiohttp,
      seeded SQLite and filesystem storage:
      [`phase5-written-replacement.md`](../../../pwa_tests/reports/phase5-written-replacement.md).
- [x] Telegram legacy discussion/queue compatibility:
      [`legacy-characterization.md`](../../../pwa_tests/reports/legacy-characterization.md)
      and consolidated proof.
- [x] Retention/privacy/storage limitations:
      [`accepted-technical-decisions-2026-07.md`](../../docs/accepted-technical-decisions-2026-07.md),
      [`object-storage.md`](../../docs/object-storage.md),
      [`deployment.md`](../../docs/deployment.md).

## Многокурсовый инкремент Phase 5

Text/photos/outbox/message сохраняют concrete `problem_id`. Logical synonym projection строит одну chronology без веточных вкладок и показывает provenance course/group/task на каждом блоке. Merge/split не копирует media objects и не меняет receipt IDs.

Дополнительный proof: merged online/offline chronology, stable concrete IDs/media keys, split recovery и `Product/Feedback--synonym-merged-timeline`.

## Task interaction polish

Implemented [full references and worksheet interaction corrections](../../docs/task-interaction-polish.md); [verification and screenshots](../../../pwa_tests/reports/task-interaction-polish/README.md) cover delayed sending, mobile input, closed answers and worksheet return. Existing task identities, drafts and print behavior are preserved.

## Written replacement recovery — 11 September 2026

Implemented and verified: 18 unit tests, production build, targeted lint/typecheck and recovery E2E in Chromium/WebKit/Firefox (Firefox separate rerun after an auth safety-screen interruption). Mobile 320/390 screenshots: `pwa_tests/reports/written-replacement-recovery/`. Owner authorized commit and push. See [recovery contract](../../docs/written-replacement-recovery.md): restrict replacement to pending unlocked work; explicitly recover rejected snapshots without losing photographs or duplicating sends. No backend or migration change.
