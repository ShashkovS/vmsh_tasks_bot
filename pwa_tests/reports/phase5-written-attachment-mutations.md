# Phase 5D — порядок и удаление фотографий до проверки

Дата: 2026-07-28

Revision: `38579a5`

## Проверяемый результат

Student может изменить полный порядок страниц кнопками «вверх/вниз» и удалить
страницу как у draft, так и у уже отправленной, но ещё не проверенной работы.
После review-lock те же операции fail closed. Reload читает тот же порядок и
состав evidence из SQLite.

Реализованные endpoints:

```text
PATCH  /student/api/v1/thread-entries/{entryPublicId}/attachments/order
DELETE /student/api/v1/thread-entries/{entryPublicId}/attachments/{attachmentPublicId}
```

Оба запроса требуют Student session, optimistic entry/thread versions и
отдельный idempotency key. Reorder принимает полный упорядоченный список, а не
пары индексов: пропавшая, лишняя или повторная фотография даёт conflict вместо
частичной перестановки. Exact no-op возвращает `changed: false`, не увеличивает
версии и не публикует invalidation.

## Инварианты хранения

[`0049.pwa_submission_attachment_mutations.sql`](../../migrations/0049.pwa_submission_attachment_mutations.sql)
добавляет SQLite guard: у submitted entry без текста нельзя удалить последнюю
фотографию даже в обход repository. Миграция проверена exact up/down/up.

[`written_submissions.py`](../../db_methods/pwa/written_submissions.py):

- revalidate-ит owner, entry/thread versions и mutable state внутри одной
  `BEGIN IMMEDIATE` transaction;
- разрешает изменения в `draft|uploading|submitted`, причём submitted — только
  пока thread остаётся `awaiting_review`;
- возвращает отдельный `written_attachment_locked` после фиксации evidence;
- использует временные sparse ordinals, затем сохраняет плотный порядок
  `0…n-1`, не нарушая immediate SQLite UNIQUE;
- записывает exact replay и ожидаемые failures в общий idempotency ledger;
- при удалении сразу убирает связь из thread projection и ставит
  `media_assets.deleted_at`.

Физический final WebP при пользовательском удалении не уничтожается в этой
transaction. Он немедленно становится недоступен через owner media endpoint,
но остаётся объектом admin-managed бессрочного retention до отдельной
manifest-driven ручной очистки. Это исключает некомпенсируемое окно
«объект удалён, SQLite transaction откатилась» и соответствует принятой
политике хранения фотографий.

## Контракты и HTTP

[`written-submissions.ts`](../../vmshpwa/packages/contracts/src/written-submissions.ts)
содержит strict Zod requests и общий mutation response с `changed`. Fixture
[`written-thread.v1.json`](../../vmshpwa/packages/contracts/fixtures/submissions/written-thread.v1.json)
фиксирует create → upload → submit → reorder no-op → delete → reload.

Real aiohttp test поднимает настоящий PWA app и временную migrated SQLite,
загружает две разные страницы через converter/storage service, меняет порядок,
проверяет replay/no-op cursor behavior, отправляет работу, удаляет страницу и
перечитывает thread. Удалённый media path возвращает owner-scoped `404`.

## Автоматические проверки

Проверено на Python 3.14.3, Node 26 и pnpm 11.15.1:

```text
repository + schema + real aiohttp focused    88 PASS
written Zod contract                           6 PASS
schema inventory                              264 objects / PASS

make pwa-lint                                 PASS
make pwa-typecheck                            PASS
make pwa-test
  Vitest                                      43 files / 329 PASS
  Python PWA                                  1215 PASS / 3 skip / 1 existing warning
make pwa-storybook-test                       38 files / 187 PASS
make pwa-build                                PASS
  Student/Family injectManifest               PASS
```

Первый Storybook run в restricted sandbox получил ожидаемый `listen EPERM`;
тот же target с разрешённым loopback прошёл полностью. Visual snapshots не
обновлялись.

## Изоляция

Все новые проверки использовали временную SQLite, synthetic converter и
in-memory object storage. Telegram, Google, NATS, live S3, `db/vmsh.db` и
внешняя сеть не использовались.

## Открытая граница следующего инкремента

Phase 5D пока не реализует browser compression worker, thumbnails,
localStorage/Dexie recovery/outbox, upload progress и Student composer.
Добавление новой страницы после submit оформляется новым entry в общей
хронологии; атомарная замена набора внутри уже submitted entry остаётся
отдельным решением. Также открыты live test S3 proof, Staff review/lock API,
legacy backfill/reassignment, production E2E и visual owner gate.
