# Phase 6A — lease-safe очередь письменной проверки

Дата проверки: 2026-07-28. Revision: `16980f6`.

## Проверяемый результат

- Migration `0051.pwa_review_queue_leases` rebuild-ит legacy
  `written_tasks_queue`: исправляет declared type `teacher_id` с `TIMESTAMP` на
  `INTEGER`, сохраняет legacy `cur_status`/`teacher_ts` и добавляет opaque
  `public_id`, `claim_token`, `claimed_at`, `lease_expires_at`, optimistic
  `lease_version` и `updated_at`.
- Невалидный исторический `teacher_id` не приводится молча к другому user ID:
  migration прерывается, а исходная таблица остаётся неизменной. Up/down/up
  сохраняет строки и legacy write shape.
- Legacy Telegram insert по-прежнему может не знать новые поля: DB default и
  fill-trigger создают `updated_at`/opaque ID. PWA claim одновременно обновляет
  legacy lock columns, поэтому существующий бот видит занятую работу.
- `PwaWrittenReviewQueueRepository.claim()` работает внутри `BEGIN IMMEDIATE` и
  захватывает все текущие queue rows одного школьника в active modern
  synonym-group как один логический кейс.
- Захват fail-closed проверяет scope каждой ветки. Если хотя бы одна задача
  synonym-case лежит вне разрешённых групп Staff, ни одна строка не меняется.
- Живая legacy Telegram-проверка блокирует PWA claim до истечения прежних 30
  минут. Два конкурентных Staff claim получают ровно один lease и один
  `ReviewLeaseConflict`.
- Heartbeat продлевает все строки логического кейса и увеличивает их версии;
  release атомарно возвращает их в `NEW`. Удалённый, истёкший или сброшенный
  legacy-клиентом lease даёт `ReviewLeaseLost`, а не ложное продолжение работы.

## Реализующие файлы

- Migration и rollback:
  [`0051.pwa_review_queue_leases.sql`](../../migrations/0051.pwa_review_queue_leases.sql),
  [`0051.pwa_review_queue_leases.rollback.sql`](../../migrations/0051.pwa_review_queue_leases.rollback.sql).
- Repository:
  [`reviews.py`](../../db_methods/pwa/reviews.py).
- Migration guards:
  [`test_phase6_review_queue_migration.py`](../integration/test_phase6_review_queue_migration.py).
- Shared-SQLite claim/heartbeat/release:
  [`test_review_queue_repository.py`](../integration/test_review_queue_repository.py).
- Telegram-era characterization:
  [`test_legacy_review_queue.py`](../domain/test_legacy_review_queue.py).
- Deterministic schema и runtime seed:
  [`schema_inventory.v1.json`](../fixtures/schema_inventory.v1.json),
  [`baseline-v1.json`](../fixtures/baseline-v1.json).

## Автоматические доказательства

- Focused migration/repository/legacy queue: **10 PASS**.
- Schema inventory + queue increment: **31 PASS**; canonical product schema —
  **274 objects**, `make pwa-schema-check` — **PASS**.
- Seed/maintenance: **117 PASS**; два synthetic queue public IDs и canonical
  digest детерминированы.
- Полный `make pwa-test`: **48 frontend-файлов / 367 PASS** и **1233 Python
  PASS / 3 intentional skips / 1 existing SymPy warning**.
- Ruff format/check и `git diff --check`: **PASS**.
- Все тесты используют временные SQLite. `db/vmsh.db`, Telegram, Google, NATS,
  S3 и production credentials не использовались.

## Открытые границы

- Staff HTTP contracts/endpoints, queue overview, WebSocket invalidation и typed
  frontend client ещё не реализованы.
- Claim пока объединяет только подтверждённые modern
  `problem_synonym_members`. Legacy `problems.synonyms` должен быть backfill-нут
  в modern membership до cutover; молчаливого смешивания двух источников нет.
- Review snapshot, verdict/comment/annotation transaction, evidence lock и
  fault injection относятся к следующим Phase 6 increments.
- Migration rehearsal на анонимизированной production-size копии и report по
  некорректным историческим `teacher_id` ещё не выполнены.
