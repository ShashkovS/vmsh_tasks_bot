# Phase 5B — текстовый вертикальный срез письменной сдачи

Дата: 2026-07-28

Revisions: `dbfd1ae`, `acbc8ec`

## Проверяемый результат

Первый runtime-срез Phase 5 работает поверх схемы Phase 5A и не подменяет
будущий photo upload:

- [`written_submissions.py`](../../db_methods/pwa/written_submissions.py)
  создаёт один Student draft в активном треде, сохраняет exact
  `problem_revision_id` и переводит непустую запись в `submitted` вместе с
  тредом `awaiting_review` в одной SQLite-транзакции;
- [`written_submission_routes.py`](../../apps/pwa_api/written_submission_routes.py)
  открывает authenticated Student API, никогда не принимает `studentId` или
  `accountId` от браузера и публикует owner-scoped invalidation только после
  нового commit;
- [`written-submissions.ts`](../../vmshpwa/packages/contracts/src/written-submissions.ts)
  валидирует strict create/submit/thread wire, exact revision provenance,
  хронологию, версии и будущие WebP attachment descriptors;
- [`written-thread.v1.json`](../../vmshpwa/packages/contracts/fixtures/submissions/written-thread.v1.json)
  является общей versioned fixture create → submit → read.

Реализованные endpoints:

```text
GET  /student/api/v1/problems/{problemPublicId}/thread
POST /student/api/v1/problems/{problemPublicId}/thread/entries
POST /student/api/v1/thread-entries/{entryPublicId}/submit
```

Text-only запись — полноценная письменная сдача, а не специальный тестовый
режим. Поле `attachmentIds` уже входит в submit-контракт, но до следующего
инкремента upload API принимает только фактически сохранённый и полностью
совпавший набор attachments; создать его через browser API пока нельзя.

## Неочевидные решения

Draft и submit разделены. Создание draft можно синхронизировать после server
cutoff: это необходимо для offline outbox. Своевременность проверяется при
submit по неизменяемому `client_created_at`; server receipt и
`clockSuspicious` сохраняются отдельно. Запись, созданная клиентом после
cutoff, остаётся черновиком и получает идемпотентный
`submission_deadline_passed`.

Письменный путь разрешён для `WRITTEN`, `ORALLY` и
`WRITTEN_BEFORE_ORALLY` (`problem_type IN (2, 3, 4)`), потому что по принятому
продуктовому правилу устную задачу всегда можно сдать письменно. Test problem
не попадает в этот API.

Create и submit используют разные записи общего `idempotency_records`.
Одинаковый ключ с тем же payload возвращает точный сохранённый response без
новой записи и realtime event; другой payload получает `409`. Ожидаемые
отказы также фиксируются и воспроизводятся, а неожиданный SQLite fault
откатывает thread, entry и processing idempotency row целиком.

Closed thread остаётся читаемым владельцу после отзыва group access. При
отсутствии собственной истории API требует актуальный опубликованный доступ и
возвращает одинаковый `404` для недоступной и чужой задачи.

## Покрытые сценарии

Repository regression в
[`test_submission_repository.py`](../integration/test_submission_repository.py):

- exact revision, один active thread и точный replay;
- mismatch idempotency key;
- atomic `draft → submitted` и `open → awaiting_review`;
- blank material, stale optimistic versions и поздний cutoff;
- offline-created-before-cutoff после поздней доставки;
- owner isolation и закрытая история после access revoke;
- конкурентный retry;
- rollback искусственного сбоя между созданием thread и entry.

Real aiohttp/SQLite regression в
[`test_content_http_api.py`](../integration/test_content_http_api.py):

- unauthenticated `401`, strict extras `422`, server-owned identity;
- empty thread, create, replay, submit, replay и последующий GET;
- owner-scoped realtime cursor меняется ровно один раз на commit;
- идемпотентная ошибка пустой отправки не меняет draft.

Zod tests проверяют fixture parity, UTC/UUID/exact fields, duplicate attachment
IDs, cross-problem history, nonempty submitted projection и principal-scoped
query keys.

## Автоматические проверки

Проверено на Python 3.14.3, Node 26 и pnpm 11.15.1:

```text
written repository focused             11 PASS
submission repository regression       34 PASS
real content/submission aiohttp         39 PASS
written Zod contract                     4 PASS

make pwa-lint                           PASS
make pwa-typecheck                      PASS
make pwa-test
  Vitest                                43 files / 327 PASS
  Python PWA                            1199 PASS / 3 skip / 1 existing warning
make pwa-storybook-test                 38 files / 187 PASS
make pwa-build                          PASS
  Student/Family injectManifest         PASS
```

Первый Storybook запуск внутри restricted sandbox получил только ожидаемый
`listen EPERM` на loopback; тот же target с разрешённым локальным browser port
прошёл полностью. Snapshots не обновлялись.

## Изоляция

Python tests использовали только временные migrated SQLite. Browser-mode
Storybook использовал локальный Chromium. Telegram, Google, S3, NATS,
`db/vmsh.db` и внешняя сеть не использовались. Legacy
`written_tasks_discussions`/`written_tasks_queue` не изменялись и не
backfill-ились.

## Открытая граница следующего инкремента

Phase 5B доказывает текст и серверную state machine, но ещё не доказывает:

- streaming raster/HEIC upload через aiohttp, WebP ≤1920, S3/filesystem,
  compensation и retry;
- attachment reorder/delete до review lock;
- production Student composer, localStorage/Dexie blobs/outbox и reload;
- legacy discussion backfill, material reassignment и Staff review;
- Storybook interaction, production-browser E2E и visual owner gate.

Эти пункты остаются Phase 5C+ и не считаются готовыми по наличию
`attachmentIds` в wire-контракте.
