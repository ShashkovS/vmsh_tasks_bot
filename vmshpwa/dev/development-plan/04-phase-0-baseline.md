# Этап 0. Базовая линия, fixtures и наблюдаемая совместимость

## Результат

Один developer/agent может одной командой поднять три production-preview frontend, настоящий aiohttp API и отдельную seeded SQLite без Telegram/Google. Репозиторий знает точную исходную схему, исторические типы ответов и контентный golden corpus. Бизнес-функции ещё не добавляются.

Дизайн-контракт этапа: [shells, state panels, foundations, Storybook stories и visual baselines](18-design-implementation-map.md#phase-0-design).

## Объём

1. Зафиксировать schema inventory существующих таблиц/индексов из реально применённой цепочки migrations и согласованной БД; проверить/перегенерировать `docs/db_structure.sql`, но не считать старый snapshot самостоятельным источником истины.
2. Создать characterization tests для правил, которые последующие этапы не должны случайно сломать: answer types, verdict weights, queue lease/selection, group/online log, Telegram discussion/result writes.
3. Создать manifest `_vmsh_examples` с encoding/hash/expected structure, не создавая новый renderer.
4. Описать `_external_pipelines` inputs/outputs и выбрать parity samples.
5. Проверить human/agent isolation: порты, DB, media, NATS prefixes, browser storage, PWA scopes.
6. Зафиксировать contract/error/clock conventions и test data privacy.
7. Принять ADR по SQLite concurrency/migration lifecycle: connection ownership, async boundary, `busy_timeout`, bounded retry, write transaction mode, отсутствие `await` внутри transaction и отдельный deploy-only yoyo command.
8. Провести auth preflight без выгрузки секретов: количество `NULL`/невалидных birthday, пустых фамилий, коллизий будущих логинов, token-length buckets и chat-id/других явно guessable token shapes. Отчёт содержит только агрегаты и synthetic examples.
9. Зафиксировать измеримый workload profile по raw traces/production counts: честно отделить доступные minute-level proxies от пока отсутствующих измерений одновременных Student/Staff sessions, photo bytes, write latency, outbox depth и допустимого `SQLITE_BUSY`/error budget. Число `200 учеников` само по себе не является load-test specification.
10. Для каждого реально запускаемого `_external_pipelines` записать owner, команду/расписание, upstream, side effects, rollback и состояние `legacy bridge | v1 cutover | later internalization`.
11. Зафиксировать внешний converter contract: четыре настраиваемых executable (`pdf2svg`, `cwebp`, `pdflatex`, `magick` по умолчанию из service `PATH`), capability probe, безопасный argv-вызов, timeout и поведение при `None`/missing binary.
12. Зафиксировать storage profile contract: filesystem/mock для hermetic unit/agent/E2E; opt-in Beget test integration берёт allowlisted `s3_*` поля из test secret file и сверяет pinned bucket identity, production target Hetzner читает отдельный production secret file, без побочной загрузки Telegram/Google credentials.
13. Зафиксировать live Telegram integration profile: `@vmsh179devbot`, token только из test config, private test channel `vmsh179devbot channel` с UI ID `3913815635`; read-only Bot API bind получает canonical chat ID/admin capability и неизменно сохраняет identity в owner-only local SQLite, после чего write-smoke использует только её. Целевая course/group `telegram_bindings` остаётся migration Phase 2.

## Подтверждённые локальные входы — 27 июля 2026

- Локальный NATS уже управляется пользователем и слушает `127.0.0.1:4222`; Docker/NATS container для этого runtime не запускается. Agent tests сохраняют собственный topic prefix и не останавливают внешний процесс.
- Authoritative read-only preflight source — `db/vmsh.db`. Любые schema/auth/migration эксперименты выполняются только над отдельной временной копией; исходный файл не изменяется и не коммитится.
- `pdflatex` доступен через локальный human toolchain override. Абсолютный пользовательский путь не попадает в репозиторий: capability probe получает его из environment/config и обязан доказать реальную TikZ compile, а не только наличие executable.
- Владелец явно разрешил opt-in side effects только в выделенных test resources: S3 create/read/public-GET/delete под disposable `integration/<run-id>/` и send/edit/delete synthetic content через `@vmsh179devbot` в private test channel. Production bucket/credentials/channels/recipients запрещены.

## Файлы реализации

Планируемые:

- `pwa_tests/fixtures/seed.py`, `pwa_tests/fixtures/schema_snapshot.sql`;
- `adr/NNNN-pwa-sqlite-concurrency-and-migrations.md`;
- `pwa_tests/reports/auth-preflight.{json,md}`, `pwa_tests/reports/workload-profile.{json,md}`;
- `helpers/pwa/toolchain.py` и поля toolchain в общем backend config;
- `pwa_tests/domain/test_legacy_answer_types.py`;
- `pwa_tests/domain/test_legacy_review_queue.py`;
- `pwa_tests/domain/test_legacy_results_and_reactions.py`;
- `vmshpwa/fixtures/content/golden-manifest.yaml`;
- `vmshpwa/packages/contracts/fixtures/runtime/*`;
- `vmshpwa/e2e/runtime-isolation.spec.ts`;
- `vmshpwa/docs/developer-runtime.md` или обновление существующего runtime doc.

Фактически реализованный seed находится в `vmshpwa/scripts/seed_runtime.py`; данные и loader — в `pwa_tests/fixtures/{baseline-v1.json,answer-types-v1.json,seed.py}`, проверки — в `pwa_tests/test_seed_runtime.py`, воспроизводимый отчёт — в `pwa_tests/reports/baseline-v1.md`.

Auth/workload preflight реализованы в `vmshpwa/scripts/{auth_preflight,workload_profile,report_io,safe_source}.py`; проверки находятся в `pwa_tests/test_{auth_preflight,workload_profile}.py`. `make pwa-auth-preflight-check` и `make pwa-workload-profile-check` только перечитывают реальные источники и сверяют четыре aggregate reports. Обновление вынесено в отдельные `*-update` targets и требует просмотра diff. Эти live-source gates намеренно не входят в hermetic `make pwa-test`.

Auth preflight отклоняет sidecars и symlink/hard-link aliases, затем читает exact bytes через secure fd (`O_NOFOLLOW_ANY` либо final-component `O_NOFOLLOW`), сверяя `lstat`/`fstat` и SHA-256 до/после. Анализ выполняется над `:memory:` SQLite, созданной `Connection.deserialize(exact_bytes)`, с `query_only`; source path SQLite повторно не открывает, `immutable=1` не используется, отсутствие deserialize — ошибка. В отчёт не попадают source rows, фамилии, token/login candidates, identifiers и неизвестные raw `users.type`: последние складываются только в aggregate other count. На снимке 27 июля 2026 года измерено 1617 Student rows: 10 имеют field/token blocker, 26 входят в 13 lower-bound collision groups, объединённая lower bound — 36 rows, provisional remainder — 1581. Это не окончательный activation result: canonical login generator и явный test-account flag отсутствуют.

Техническая опора этой гарантии: [Python 3.14 `Connection.deserialize`](https://docs.python.org/3.14/library/sqlite3.html#sqlite3.Connection.deserialize), [SQLite `sqlite3_deserialize`](https://sqlite.org/c3ref/deserialize.html) с ограничением WAL-mode serialization и platform-dependent [`O_NOFOLLOW_ANY`](https://docs.python.org/3.14/library/os.html#os.O_NOFOLLOW_ANY), [`O_NOFOLLOW`](https://docs.python.org/3.14/library/os.html#os.O_NOFOLLOW), [`fstat`](https://docs.python.org/3.14/library/os.html#os.fstat). Код не меняет SQLite header bytes; непригодный к deserialize snapshot отклоняется fail-closed. Полная тестовая формулировка зафиксирована в [`testing-strategy.md`](../../docs/testing-strategy.md#aggregate-preflight-реальных-источников).

Workload profile использует только raw `logs/events.jsonl` и 18 rotations `events.jsonl.YYYY-MM-DD`; PII-bearing filtered derivative `logs/selected.jsonl` исключён, чтобы не дублировать и не смещать выборку. Все source fd удерживаются открытыми; bytes читаются и хешируются через эти же descriptors, после parsing повторяются `fstat`/hash/path checks. Состав rotations проверяется повторно, symlink/hard-link/duplicate-inode aliases отклоняются, JSON records deduplicate-ятся по canonical representation, а event/source/actor labels проходят explicit allowlists. Текущий отчёт покрывает 176713 observed records и 37408 traces в окне 2–20 марта; completeness metadata отсутствует. Peak minute proxies — 38 ingress updates, 13 submission events, 11 review completions и 12 distinct flows. Concurrent sessions, request/write latency, photo bytes, outbox depth и `SQLITE_BUSY` budget остаются неизвестными и всё ещё блокируют окончательный performance input этапа 11.

Decommission baseline реализован как связанная пара
[`21-external-process-register.md`](21-external-process-register.md) и
[`external-process-register.v1.json`](../../../pwa_tests/fixtures/external-process-register.v1.json).
Она различает наблюдаемое legacy-поведение и будущий target, описывает 48
операционных/reference процессов, 36 repository artifacts, два точных runbook и
шесть отсутствующих внешних зависимостей. Структуру, уникальность, двусторонние
ссылки, реальные question anchors, существование путей и отсутствие скопированных
секретов/JSONL payload проверяет
[`test_external_process_register.py`](../../../pwa_tests/test_external_process_register.py).

Каждый JSON/Markdown-файл заменяется отдельно через same-directory temporary file, file `fsync`, `os.replace` и directory `fsync`. Пара файлов не объявляется транзакцией: прерванная запись обнаруживается последующим `*-check`.

Не коммитить production DB snapshot, credential-bearing rows из migration fixtures и реальные персональные данные.

## Fixtures

Seed `baseline-v1` и первый release fixture:

- 4 динамических учебных группы + одна system group;
- Student online, Student in-person, Teacher с одной разрешённой группой и Admin; Family с двумя детьми остаётся manifest-only до миграций Phase 1;
- один текущий и один прошлый урок, а также занятия 39–41 сезона 2025–2026 для трёх уровней;
- по одной задаче каждого `PROB_TYPE`;
- все значения `ANS_TYPE` в isolated answer fixtures;
- empty/review-queued/review-locked/accepted/needs-work threads;
- timestamps по обе стороны отдельного submission cutoff и более поздней solution publication.

Для migration/performance characterization разрешена локальная защищённая копия production SQLite вместе с `-wal` и `-shm`. Она не коммитится и не используется обычным E2E seed. Content visual gate сравнивает PWA, Telegram и PDF для трёх листков одного уровня из `_vmsh_examples`.

## Автоматические проверки

- Python: schema snapshot, seed repeatability, legacy characterization, app factory imports без Telegram/Google.
- Python/preflight: aggregate-only auth classification, unknown-type redaction и collision lower bound; отказ от symlink/hard-link/SQLite sidecars; descriptor-bound source-change и duplicate-inode detection; deserialize absence/failure; exact/canonical event dedup; raw rotation selection; label allowlists, включая динамический middleware label; missing/stale report-pair detection и durable single-file replacement.
- Python/integration: два connection/process writers, `SQLITE_BUSY` retry exhaustion, crash внутри transaction и schema-version mismatch без auto-apply.
- Python/integration: два runtime workers держат shared lifecycle locks, seed/migrate требуют exclusive lock; lock сохраняется до aiohttp cleanup, а отдельный процесс не может открыть старую SQLite между финальной проверкой seed и `os.replace`.
- Python/toolchain: default-name lookup через контролируемый `PATH`, absolute override, `None`, missing/non-executable file, fake version/error/timeout executables; реальные binary smoke отмечаются как environment capability test.
- Python/storage config: полный/частичный/отсутствующий набор `s3_*`, test/prod source selection, secret redaction и доказательство, что filesystem agent/E2E profile не читает credential files.
- Python/Telegram: RecordingBot для hermetic suite; opt-in live probe проверяет `getMe/getChat/getChatMember`, сохраняет canonical group destination и может отправить synthetic boundary payloads в test channel без real student data.
- TS: runtime config parsing, production prohibition MSW/prototype, query-key baseline, Dexie namespace isolation.
- Storybook: shells и глобальные states, уже существующие в дизайн-фазе.
- E2E production preview: base path/history fallback, health/runtime, WS reconnect/refetch signal, theme, audience isolation, SW installation/update smoke.
- Three-browser run. Проверки SW, недоступные конкретному engine, помечаются capability-based skip с объяснением.
- Physical baseline: все критические сценарии на доступных Android-устройствах; iPhone — по возможности, при сохранении автоматического WebKit gate.

## Документация

- Обновить `vmshpwa/docs/testing-strategy.md`, runtime isolation и этот `STATUS.md`.
- Зафиксировать версии macOS/browser/fonts для visual baseline.
- Составить «legacy invariants» без секретов и исторических логинов.
- Составить полный decommission register внешних процессов; наличие будущего внутреннего владельца не означает, что legacy path уже можно выключить.

## Критерии приёмки

- Human и agent profiles могут работать одновременно и не видят данные друг друга.
- Новый test/build не читает `creds_prod`, Google service account или Telegram token.
- `golden-manifest` обнаруживает смену исходного файла/hash/encoding.
- Characterization tests падают при изменении очереди, verdict mapping или answer enum.
- Все последующие фазы имеют один воспроизводимый seed entrypoint.
- Принят DB concurrency ADR; обычный app startup не применяет migrations, а намеренно устаревшая schema останавливает startup до обслуживания.
- Auth preflight считает measured lower-bound blockers без сериализации source values. Workload profile фиксирует доступные численные proxies и явно перечисляет недостающие performance inputs этапа 11; external-process register не содержит строки без владельца/срока следующего решения.
- Toolchain config не содержит локальных абсолютных путей по умолчанию; preflight до запуска pipeline сообщает все отсутствующие обязательные capabilities и версии найденных converters.
- S3 adapter fail-fast отклоняет неполную конфигурацию, а filesystem agent/E2E проходит без `creds_test`, `creds_prod` и network access.
- Live Telegram test не запускается обычным unit/E2E, не использует production token/channel и перед отправкой подтверждает, что bot username/channel mapping совпали с test profile.

## Пруфы завершения этапа

- [ ] Revision: `<sha>`; миграции: `none` или `<paths>`.
- [ ] Demo: `<make commands>`; seed `baseline-v1`; URLs всех трёх приложений.
- [ ] Isolation report: `<path>` с портами, DB, media, NATS, IndexedDB и scopes.
- [ ] Tests: Python `<result>`; TS `<result>`; Storybook `<result>`; E2E 3 browsers `<result>`.
- [ ] Golden corpus manifest: `<path>`; source hashes/encoding verified `<result>`.
- [ ] Legacy characterization report: `<path>`.
- [ ] DB concurrency/migration ADR и two-writer fault tests: `<path/result>`.
- [x] Auth preflight aggregates и unresolved policy: `pwa_tests/reports/auth-preflight.{json,md}`; 1617 Student, 36 measured lower-bound blockers, 1581 provisionally eligible, final eligibility unknown.
- [ ] Workload profile: `pwa_tests/reports/workload-profile.{json,md}`; 176713 observed events/37408 traces и minute proxies зафиксированы, но concurrent sessions/write latency/photo bytes/outbox/`SQLITE_BUSY` budget и approval всё ещё отсутствуют.
- [x] External-process decommission register: `vmshpwa/dev/development-plan/21-external-process-register.md` + `pwa_tests/fixtures/external-process-register.v1.json`; 48 процессов, 36 artifacts, два runbook, шесть известных внешних dependencies; 7 focused tests PASS.
- [ ] Converter config/probe contract и local capability report; server повторяет gate в этапе 11: `<paths/results>`.
- [x] Storage profile/config/redaction: `helpers/{object_storage,pwa/storage_config}.py`, `vmshpwa/docs/object-storage.md`; 86 focused tests PASS, pinned Beget test-bucket live runs `codex-phase0-20260727-f6c821d9` и collision-safe replay `codex-phase0-20260727-collision-safe` прошли put/private-read/public-GET/delete-ack. Production target Hetzner остаётся Phase-11 readiness gate.
- [ ] RecordingBot suite и opt-in `@vmsh179devbot`/test-channel capability report с message IDs, без token: hermetic suite и двухшаговый harness готовы (`helpers/pwa/telegram_test_{harness,binding}.py`, `vmshpwa/scripts/telegram_test_capability.py`), но live bind/smoke ждёт canonical signed `chat.id` из раздела «Где взять канонический ID тестового канала?» в `20-implementation-questions.md`. Rich/limits proof выполняется с renderer в Phase 2.
- [ ] Visual baseline environment and screenshots: `<paths>`.
- [ ] Docs updated: `<paths>`.
- [ ] Known limitations/issues: `<links or none>`.
- [ ] Accepted by/date: `<name/date>`.
