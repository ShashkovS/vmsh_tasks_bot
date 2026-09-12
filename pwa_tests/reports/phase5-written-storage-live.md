# Phase 5 — live test S3 для конвертеров и письменного фото

Дата проверки: 2026-07-28.
Revision harness: `71e96e6`.

## Безопасная граница

- Использован только pinned профиль `pwa-s3-integration` и выделенный пустой
  test bucket с fingerprint `993fe1242fb7`.
- Все provider keys находились под отдельными
  `integration/<run-id>/...`; production credentials, Telegram, Google и
  `db/vmsh.db` не использовались.
- Команды принимают явный opt-in `VMSH_ENABLE_LIVE_S3_TEST=true`, проверяют
  локальную привязку bucket и не печатают provider exception messages, URL
  объектов или credentials.
- Каждый успешно созданный объект прочитан через server adapter, проверен через
  публичный GET и удалён. Успех требует отдельного delete acknowledgement.

## Прогоны

### Общий converter/storage pipeline

Команда `make pwa-content-assets-live-smoke`, run ID
`phase5-written-20260728-a2`:

- TikZ → SVG: `67×67`, 3331 bytes; put/private read/public GET/delete — PASS;
- raster → WebP: `4×2`, 82 bytes; put/private read/public GET/delete — PASS;
- endpoint family `s3.ru1.storage.beget.cloud`, region `ru1`, integration
  prefix — подтверждены безопасным отчётом.

Первый preflight `phase5-written-20260728-a1` остановился на conversion до S3,
потому что `pdflatex` не входил в service `PATH`. Успешный запуск использовал
явный `VMSH_PDFLATEX_PATH=/Users/sergeyshashkov/bin/pdflatex`; это не credential
и соответствует принятой модели explicit converter path.

### WrittenAttachmentService

Новая guarded-команда `make pwa-written-attachment-live-smoke`, run ID
`phase5-written-service-20260728-b2`, скомпоновала настоящий
[`WrittenAttachmentService`](../../helpers/pwa/written_attachments.py), общий
raster converter и S3 adapter:

- server-derived key соответствует
  `sol_imgs/user_{id}/{year}/lesson_{n}/{problem}_{time}_{uuid}.webp`;
- synthetic source преобразован в final WebP `4×2`, 82 bytes;
- persisted SHA-256 совпал с private-read bytes;
- public GET вернул те же bytes;
- delete acknowledgement — PASS.

Фактический object key и public URL намеренно не записаны в proof. Unit harness
дополнительно проверяет cleanup при сбое public GET, одновременном cleanup fault,
обязательный opt-in и отсутствие provider secrets в ошибке. Focused storage /
written-service regression — **86 PASS / 1 existing SymPy warning**.

## Что остаётся отдельным gate

- Browser E2E остаётся hermetic на filesystem adapter; live smoke не создаёт
  product session или строку настоящей сдачи в SQLite.
- Большой photo corpus, EXIF/GPS и HEIC server fallback требуют отдельного
  media-corpus proof. Этот smoke доказывает wiring и lifecycle тестового S3, а
  не качество распознавания всех форматов.
- Production Hetzner readiness выполняется только при deploy с production
  profile и не подменяется результатом Beget test bucket.
