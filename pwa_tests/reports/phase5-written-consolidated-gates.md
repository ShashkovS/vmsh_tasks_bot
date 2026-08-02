# Phase 5 — consolidated written-submission gates

Дата проверки: 3 августа 2026 года.

Этот отчёт не заменяет подробные proof отдельных инкрементов. Он связывает
оставшиеся пункты Phase 5 с уже существующими исполняемыми проверками и отделяет
автоматически доказанное поведение от двух действительно открытых gates.

## Доказанный пользовательский путь

- Storybook `Product/Submission` содержит обычные случаи одной и двух страниц,
  точную границу в десять страниц, mixed processing/upload/error, offline queue
  и locked/closed state. Interaction у двух страниц проверяет перестановку
  кнопкой, а ten-page story проверяет обе границы списка.
- Production-build Playwright сценарий
  `Phase 5: a written draft with a photo survives reload and resumes exactly
once` проходит в Chromium, WebKit и Firefox. Он использует настоящий aiohttp,
  отдельную SQLite и filesystem storage, создаёт WebP в worker, переживает
  reload/offline и после reconnect выполняет ровно один create/upload/submit.
- Тот же browser scenario проверяет pre-review replacement: authenticated WebP
  восстанавливается в durable draft, переживает reload и заменяется одной
  атомарной операцией без перепривязки старого evidence.

Подробные browser proofs:

- [`phase5-written-browser-draft.md`](phase5-written-browser-draft.md);
- [`phase5-written-replacement.md`](phase5-written-replacement.md);
- [`phase11-production-e2e.md`](phase11-production-e2e.md).

## Локальный draft и offline outbox

[`written-submission-draft.test.ts`](../../vmshpwa/packages/offline/src/written-submission-draft.test.ts)
проверяет reload, owner/revision/runtime isolation, десять уникальных страниц,
quota compensation, repair missing/corrupt binaries, orphan cleanup и очистку
только одного owner. [`written-submission-outbox.test.ts`](../../vmshpwa/packages/offline/src/written-submission-outbox.test.ts)
проверяет immutable snapshot текста/порядка/bytes, checkpoint после каждого
server acknowledgement, resume с упавшей фотографии, duplicate enqueue,
missing-local-evidence conflict, revision conflict без потери snapshot и lease
между вкладками.

Актуальный frontend unit checkpoint: **110 files / 586 PASS**.

## SQLite, idempotency и блокировка evidence

Repository/service tests проверяют:

- exact idempotent replay и payload mismatch;
- один draft при concurrent create и cleanup лишнего object при concurrent
  attachment replay;
- atomic reorder/delete и отсутствие частичной мутации при stale version;
- своевременную offline entry по client-created time;
- запрет изменения submitted/locked evidence;
- cleanup final object при DB failure и явную redacted ошибку при cleanup
  failure.

Основные исполняемые файлы:

- [`test_submission_repository.py`](../integration/test_submission_repository.py);
- [`test_written_attachment_service.py`](../domain/test_written_attachment_service.py);
- [`test_phase5_written_submission_schema_migration.py`](../integration/test_phase5_written_submission_schema_migration.py).

Полный актуальный Python checkpoint, запущенный в восьми изолированных workers:
legacy **121 PASS / 1 skip**, PWA **1552 PASS / 5 skip**; общий wall time
**104,36 s**.

## Filesystem и test S3

Hermetic contract покрывает разные filesystem roots agent/E2E и общий root
только у явно одинаково настроенных adapters. Guarded live smoke использовал
только test bucket и disposable `integration/<run-id>/`: put, private read,
public GET и delete acknowledgement прошли для TikZ→SVG, raster→WebP и
настоящего `WrittenAttachmentService`. Production Hetzner не подменяется этим
smoke и проверяется deployment readiness.

Подробности:

- [`object-storage-phase0.md`](object-storage-phase0.md);
- [`phase5-written-storage-live.md`](phase5-written-storage-live.md);
- [`phase5-written-media-corpus.md`](phase5-written-media-corpus.md).

## Legacy Telegram compatibility

[`test_legacy_review_queue.py`](../domain/test_legacy_review_queue.py) сохраняет
исторические lease/group/synonym/SOS правила очереди.
[`test_legacy_user_changes_and_telegram_linkage.py`](../domain/test_legacy_user_changes_and_telegram_linkage.py)
проверяет Telegram `chat_id`/`tg_msg_id`, nullable non-Telegram provenance и
отсутствие выдуманной связи discussion→result. Migration proof подтверждает,
что additive Phase-5 schema не переписывает legacy discussion/queue rows.

Это доказывает совместимость, но не означает завершённый перенос старой истории
в новые `submission_threads`.

## Открытые gates

1. Legacy backfill требует owner-reviewed historical problem revisions и
   решения по 40 531 Telegram-only строкам без доступного payload. До ответа
   система не создаёт фиктивный текст и не выдумывает provenance.
2. Storybook browser suite последний раз прошёл как **50 files / 236 PASS** с
   addon-a11y error gate. Текущий повтор 3 августа дважды остановился до
   collection из-за внешнего macOS `MachPortRendezvous` failure headless
   Chromium; это не считается PASS. Production Storybook build, ESLint и strict
   TypeScript с новыми stories проходят. Их interactions должны пройти browser
   gate после восстановления launcher и затем получить ручное mobile-light
   visual approval владельца. Snapshots не обновлялись.
