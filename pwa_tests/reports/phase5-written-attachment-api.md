# Phase 5C — загрузка фотографий письменного решения

Дата: 2026-07-28

Revision: `9c065db`

## Проверяемый результат

Student может добавить фотографию к ещё не отправленному письменному entry,
получить final WebP descriptor, повторить тот же запрос без дубля и затем
отправить photo-only либо text+photo entry.

Реализованные endpoints:

```text
POST /student/api/v1/thread-entries/{entryPublicId}/attachments
GET  /student/api/v1/thread-entries/{entryPublicId}/attachments/{attachmentPublicId}/media
```

[`written_submission_routes.py`](../../apps/pwa_api/written_submission_routes.py)
читает multipart по ограниченным chunks, требует точный набор полей, UUID,
optimistic entry/thread versions и ordinal `0…9`. Identity всегда берётся из
проверенной Student session. Unicode filename безопасно декодируется из
multipart и хранится только как диагностическая метка.

[`written_attachments.py`](../../helpers/pwa/written_attachments.py) использует
общий bounded raster converter Phase 2. Любой поддерживаемый source, включая
server-fallback HEIC, повторно кодируется в WebP; final dimensions должны быть
не больше 1920×1920, source/output SHA-256 обязаны совпадать с фактическими
байтами. Оригинал не записывается в object storage или SQLite.

Final key строится только из server-derived scope:

```text
sol_imgs/user_{user_id}/{season_year}/lesson_{lesson_number}/
  {problem_public_id}_{server_utc}_{random_uuid}.webp
```

Имя ученика и browser-supplied path в key не входят. Production storage может
вернуть публичный длинный URL; для filesystem/dev descriptor всегда содержит
authenticated `mediaPath`. Media endpoint повторно проверяет owner, byte size
и SHA-256 перед выдачей.

## Атомарность и компенсация

Операция имеет отдельный ledger kind `written-attachment:create`.

1. Repository до конвертации проверяет owner, current published revision,
   optimistic versions, свободный ordinal и лимит 10.
2. Converter создаёт final WebP; storage записывает уникальный object key.
3. Одна `BEGIN IMMEDIATE` transaction создаёт `media_assets`,
   `submission_attachments`, увеличивает entry/thread versions и завершает
   idempotency record.
4. Любой контролируемый DB failure после object put удаляет именно этот новый
   object. Concurrent exact replay возвращает сохранённый response и также
   удаляет лишний уникальный object проигравшего запроса.

Неожиданный failure самой compensation не скрывается: наружу выходит
redacted service error, а типы primary/cleanup ошибок попадают в server log без
ключей credentials и содержимого фотографии.

## Контракты и покрытие

[`written-submissions.ts`](../../vmshpwa/packages/contracts/src/written-submissions.ts)
добавляет strict multipart metadata и attachment response. Общая fixture
[`written-thread.v1.json`](../../vmshpwa/packages/contracts/fixtures/submissions/written-thread.v1.json)
теперь покрывает create draft → upload WebP → submit → read.

Проверены:

- server-derived year/lesson/problem/user scope и exact object-key shape;
- final-only WebP metadata, Unicode filename и limit/version conflicts;
- exact replay, payload mismatch, concurrent replay и отсутствие дублей;
- DB failure compensation и явная cleanup failure;
- photo-only submit с точным порядком attachment IDs;
- owner-only repository/media read и integrity verification;
- unauthenticated media denial и owner-scoped invalidation только на новом
  commit;
- общий shared converter regression, filesystem/S3 adapter regression и
  действующие WebP/size/tool-failure тесты Phase 2 в полном Python suite.

## Автоматические проверки

Проверено на Python 3.14.3, Node 26 и pnpm 11.15.1:

```text
written attachment focused             10 PASS
submission repository regression       44 PASS
real content/submission aiohttp         40 PASS
written Zod contract                     5 PASS

make pwa-lint                           PASS
make pwa-typecheck                      PASS
make pwa-test
  Vitest                                43 files / 328 PASS
  Python PWA                            1210 PASS / 3 skip / 1 existing warning
make pwa-storybook-test                 38 files / 187 PASS
make pwa-build                          PASS
  Student/Family injectManifest         PASS
```

Первый полный Python run в restricted sandbox был остановлен после ожидаемых
`listen EPERM` у aiohttp fixtures; тот же `make pwa-test` с разрешённым
loopback прошёл полностью. Snapshots не обновлялись.

## Изоляция

Новые тесты использовали только временные migrated SQLite и in-memory object
storage. Полный regression использовал существующие hermetic storage/converter
fixtures. Telegram, Google, NATS, live S3, `db/vmsh.db` и внешняя сеть не
использовались. Test S3 smoke остаётся отдельным opt-in proof и не подменяется
этим отчётом.

## Открытая граница следующего инкремента

Phase 5C пока не реализует:

- удаление и reorder attachment до review lock;
- атомарную замену уже submitted, но ещё не locked набора фотографий;
- browser worker, thumbnails, localStorage/Dexie outbox и reload recovery;
- 1/2/10-photo Student UI, Storybook interactions и production-browser E2E;
- live test S3 create/public-GET/delete для submission key;
- legacy discussion backfill, reassignment и Staff review.

До реализации review query teacher не должен читать `draft` entry: видимым
рабочим evidence остаётся только атомарно переведённый `submitted` entry.
