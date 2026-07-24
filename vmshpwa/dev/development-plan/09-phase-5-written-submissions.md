# Этап 5. Письменная сдача, media pipeline и offline outbox

## Результат

Школьник создаёт одну логическую отправку из текста и до 10 фотографий, видит сжатие/порядок/загрузку, может уйти offline и позже безопасно дослать. Работа появляется у teacher только целиком. До первого review lock её можно изменить/удалить с подтверждением; после начала проверки можно добавлять новый материал в тред, но не переписывать исходную entry. После review evidence immutable.

## Модель данных

Migration: `pwa_submission_threads_entries_assets`.

Таблицы: `submission_threads`, `submission_entries`, `submission_attachments`, `media_assets`, `idempotency_records`. Lazy/batch backfill `written_tasks_discussions`; legacy IDs сохраняются. Публичный object key следует agreed pattern и не содержит имени школьника.

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
- File adapter in agent/test; `aioboto3` adapter in production.
- Write sequence: validate → temporary object → conversion/verify hash → final key → SQLite transaction → cleanup. Compensation job finds stale temporary objects.
- Public GET URL is long/unguessable; upload and list still require auth.
- Submission entry становится видима атомарно только после всех выбранных файлов; failed attachment повторяется отдельно, не создавая частичную работу.
- `locked_at`/`locked_by_result_id` only set inside review transaction in phase 6. Delete/reorder endpoint checks lock and returns `409 ATTACHMENT_LOCKED`.

## Frontend

- Focused written task and composer in `student/src/features/submissions/written`; text-only разрешён, raw LaTeX сохраняется, но v1 не рендерится.
- Thread timeline initially shows student entries; phase 6 adds review events.
- Отдельные Student actions «дописать ответ» и «пересдать решение» ведут к одной backend operation без fake attempt numbering.
- Offline quota estimate and recovery: keep local preview until server acknowledgement; warnings when browser storage is low.
- Logout with pending queue warns and lists count; confirmed logout may clear it.

## Tests

- Worker dimensions/rotation/WebP/metadata tests with JPEG, PNG, WebP, HEIC fixture where supported, corrupt and huge input.
- Server fallback contract against `mathimg_service.py` capabilities, without importing external module at runtime.
- Storage adapter parity, interrupted upload, S3 transient retry, hash collision, temp cleanup.
- Authorization: other student/family cannot enumerate attachment; public URL accessibility follows explicit privacy decision.
- Offline outbox crash matrix and idempotency/payload conflict.
- Concurrent edit vs review completion: новая фотография до commit обязана войти в текущую проверку; thread-version conflict заставляет teacher refetch.
- Storybook photo-state matrix and 1/2/10-page mobile cases.
- Playwright real aiohttp/filesystem storage: camera-file input → worker → offline/reconnect → stored → reload; no MSW.

## Критерии приёмки

- Final stored object is valid WebP ≤1920 side and contains no retained EXIF GPS.
- Original and server temporary are absent after success/cleanup.
- Retry creates one logical entry/asset set; Telegram media group и PWA entry сводятся в один thread/provenance.
- 1–2 photos require few clear actions; 10 photos remain manageable.
- Locked material cannot be mutated through UI or direct API.
- Telegram discussions remain readable and new PWA thread does not corrupt queue behavior.

## Пруфы завершения этапа

- [ ] Revision/migration/backfill/rollback: `<sha/paths/results>`.
- [ ] Demo 1/2/10 images online and offline: `<route/fixture/evidence>`.
- [ ] Media corpus results (dimensions, WebP, EXIF, HEIC fallback, corrupt/huge): `<path>`.
- [ ] Filesystem/S3 adapter and cleanup tests: `<result>`.
- [ ] Idempotency/crash/concurrency/lock tests: `<result>`.
- [ ] Storybook photo state matrix/interactions/a11y/visuals: `<ids/paths>`.
- [ ] Playwright 3 browsers and capability skips: `<result>`.
- [ ] Telegram legacy discussion/queue tests: `<result>`.
- [ ] Docs/storage retention/privacy/known limitations/acceptance: `<paths/issues/name/date>`.
