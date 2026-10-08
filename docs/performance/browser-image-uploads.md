# Браузерный WebP и direct-to-S3

Решение владельца от 8 октября 2026. Реализация: общий browser worker и
image-upload transport в `vmshpwa/packages/app-shell`, существующие photo
endpoints в `apps/pwa_api`, `helpers/pwa/image_uploads.py`,
`db_methods/pwa/image_uploads.py` и миграция 0114.

Все пользовательские фото (Student/Family/Staff, решения, вопросы и rich
редакторы) готовятся в браузере: WebP, сторона ≤1920, quality 0.82, исходник
≤25 МиБ, результат ≤20 МиБ. Encoder проверяется в worker. Ошибка подготовки
использует существующую серверную конвертацию. Telegram/импорты не меняются.

После подготовки в фоне запрашивается разрешение на 600 секунд. Байты
отправляются только по отправке формы (rich-editor: при вставке изображения).
PUT подписывает key, MIME, точный размер и SHA-256. Сервер делает только HEAD:
GET/Range/CopyObject и повторного кодирования в direct path нет. Формат,
ориентация, dimensions и удаление EXIF проверяет браузер; checksum подтверждает
целостность передачи, а не содержимое изображения.

SQLite хранит owner/audience/purpose/context, стабильный client photo ID,
неизменяемые параметры, key, последнее expires_at и квитанцию финализации.
Доменные метаданные и квитанция фиксируются в одной транзакции. Повторы
возвращают прежний результат. URL не сохраняется на диск. Потерянный PUT ack
вначале проверяется финализацией, затем при отсутствии объекта повторяется PUT.
Proxy fallback подготовленного WebP проверяет bytes без перекодирования.

Каждый час cleanup забирает SQLite claim на незавершённые intents спустя
24 часа после последнего expires_at. Claim исключает renew/finalize. Deletes
повторяемы после падения; финализированные материалы и существующие серверные
черновики не затрагиваются. Устаревший очищенный intent требует новой попытки.

Direct upload включается только явной конфигурацией после live capability
proof: корректный и неверный checksum, HEAD checksum, exact length и browser
CORS для конкретного провайдера. Filesystem и непроверенный S3 используют proxy.
Live tests выполняются отдельно в pinned test-only bucket/prefix. В unit/E2E
никаких внешних credentials, Telegram polling или production state.

Gate: `make pwa-check-release`; browser/source/cancellation, retry/reload,
permissions/version/lock, atomic finalize и cleanup races. Измеряем preparation,
direct PUT, HEAD/finalize и send-to-receipt, без URL/payload в telemetry.

## Progress

- 2026-10-08: implementation started; migration/storage/protocol first, then
  all callers and durable drafts. Gate and live provider proof pending.

- Protocol/atomic finalization wired across all upload endpoints. Known rich
  browser images are reused during news/banner/lesson saves without GET/convert.
- Targeted initial gate: 95 backend tests passed (21 new image scenarios plus
  storage regressions), workspace typecheck passed. New rich reuse/frontend
  transport/Storybook cases added; full release gate follows.
- Direct transport remains disabled by default until provider/browser proof.
  Guarded live CLI checks checksum, exact length, HEAD and CORS headers; it
  deliberately reports browserProof separately.

- Live pinned Beget probe `browser-upload-20261008-0728`: exact length enforced,
  PUT accepted, but changed bytes with the original SHA-256 were also accepted;
  HEAD did not return checksum. CORS failed for the agent loopback origin.
  [Redacted proof](browser-image-upload-s3-proof-20261008.json). Disposable object
  delete acknowledged. Provider direct capability remains disabled; production
  config/bucket permissions were not changed. Native browser proof was not run
  because the prerequisite checksum enforcement failed.
- First release run stopped at Prettier on the changed Student form; formatting
  corrected before retry. No runtime/deployment action has been taken.
- Full Python 2863/7 skipped, frontend 1053, Storybook 364 passed. The first
  three-browser E2E run revealed a stale “saved” indicator while a new photo was
  still preparing; fixed in Organizer/Support composers. Added native-worker
  orientation/EXIF/format and 1/2/10-photo reload proof in
  `vmshpwa/e2e/browser-image-upload.spec.ts`. Final release receipt pending.
- Targeted native-worker/dialogue E2E: 15 PASS across Chromium/WebKit/Firefox.
  Chromium/Firefox use native WebP; WebKit uses the legacy fallback. Exact hashes
  and local stage samples: [browser proof](../../pwa_tests/reports/browser-image-uploads-20261008/README.md).
  Final full release gate running; direct S3 remains disabled.
- Full gate `20261008T082357.286699Z`: preparatory checks passed, main E2E
  386 PASS / 20 SKIP / 2 Firefox failures. Both Family failures precede photo
  selection and involve an initial PWA update notice. The existing review-queue
  spec also overwrote tracked documentation captures, invalidating source digest.
  Captures now go to testInfo.outputPath; previous doc assets restored, generated
  copies retained in the report. Family scenarios explicitly apply an initial
  update before unrelated navigation. Focused and full re-verification pending.
- Focused release gate `20261008T092814.668624Z`, modes `family organizers`:
  all preparatory checks and 15 three-browser E2E PASS, source_changed=false.
  Full default release gate rerun in progress; no product code changed after
  the earlier main E2E run.
- Default full rerun `20261008T094100.161143Z`: source_changed=false, preparatory
  checks PASS, main E2E 382 PASS / 20 SKIP / 6 failures in existing navigation,
  shared-refresh and service-worker handover scenarios. Their traces precede
  photo processing. The global release gate is not green; no snapshot threshold
  or production behavior was changed to conceal these failures.
- Final audit tightened written-context validation for cached domain receipts;
  regression confirms a different intent cannot reuse a receipt across problems.
  Relevant photo modes plus previously unexecuted layout/statistics/visual phases
  are being verified through the common release runner.
- Relevant-mode gate `20261008T101249.562184Z`: all preparatory suites PASS
  including the final context regression. E2E dispatch temporarily blocked by
  the shared lock/ports held by another worktree's performance run (`9eab`);
  its processes were identified read-only and left running.
- Final relevant-mode release run `20261008T102533.573581Z`: all prep suites
  PASS; 63 functional E2E PASS across three browsers, including all photo modes,
  layout and statistics. Staff visual 3 PASS; Student visual 3 FAIL because the
  existing support-navigation fixture adds a course absent from the old baseline.
  All engine diffs inspected and preserved; snapshots unchanged. source_changed=false.
  [Final proof and remaining global-gate failures](../../pwa_tests/reports/browser-image-uploads-20261008/README.md).
  Implementation complete; default all-mode release remains unconfirmed/failed.
  Provider enablement, native S3 CORS proof, real-device handwriting review and
  production speed comparison remain separate release checks.

## Implementation references

- [Shared worker/client](../../vmshpwa/packages/app-shell/src/image-upload-client.ts),
  [contracts](../../vmshpwa/packages/contracts/src/image-uploads.ts),
  [durable photo drafts](../../vmshpwa/packages/offline/src/organizer-draft.ts).
- [HTTP routes and cleanup lifecycle](../../apps/pwa_api/image_upload_routes.py),
  [intent/finalization service](../../helpers/pwa/image_uploads.py),
  [SQLite queries](../../db_methods/pwa/image_uploads.py),
  [migration 0114](../../migrations/0114.browser_image_uploads.py).
- [HEAD-only and race tests](../../pwa_tests/integration/test_browser_image_uploads.py),
  [browser proof spec](../../vmshpwa/e2e/browser-image-upload.spec.ts),
  [guarded provider probe](../../vmshpwa/scripts/image_upload_storage_smoke.py).
- Provider contract: [S3 HeadObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html)
  and [presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html).
