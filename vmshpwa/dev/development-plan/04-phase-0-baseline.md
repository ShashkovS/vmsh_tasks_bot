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
9. Зафиксировать измеримый workload profile по traces/production counts: одновременные Student/Staff sessions, submits/minute в пике, photo count/bytes, write latency, queue/outbox depth и допустимый `SQLITE_BUSY`/error budget. Число `200 учеников` само по себе не является load-test specification.
10. Для каждого реально запускаемого `_external_pipelines` записать owner, команду/расписание, upstream, side effects, rollback и состояние `legacy bridge | v1 cutover | later internalization`.

## Файлы реализации

Планируемые:

- `pwa_tests/fixtures/seed.py`, `pwa_tests/fixtures/schema_snapshot.sql`;
- `adr/NNNN-pwa-sqlite-concurrency-and-migrations.md`;
- `pwa_tests/reports/auth-preflight.example.json`, `pwa_tests/reports/workload-profile.md`;
- `pwa_tests/domain/test_legacy_answer_types.py`;
- `pwa_tests/domain/test_legacy_review_queue.py`;
- `pwa_tests/domain/test_legacy_results_and_reactions.py`;
- `vmshpwa/fixtures/content/golden-manifest.yaml`;
- `vmshpwa/packages/contracts/fixtures/runtime/*`;
- `vmshpwa/e2e/runtime-isolation.spec.ts`;
- `vmshpwa/docs/developer-runtime.md` или обновление существующего runtime doc.

Не коммитить production DB snapshot, credential-bearing rows из migration fixtures и реальные персональные данные.

## Fixtures

Seed `baseline-v1` и первый release fixture:

- 4 динамических учебных группы + одна system group;
- Student online, Student in-person, Family с двумя детьми, Teacher с одной разрешённой группой, Admin;
- один текущий и один прошлый урок, а также занятия 39–41 сезона 2025–2026 для трёх уровней;
- по одной задаче каждого `PROB_TYPE`;
- все значения `ANS_TYPE` в isolated answer fixtures;
- empty/review-queued/review-locked/accepted/needs-work threads;
- timestamps по обе стороны отдельного submission cutoff и более поздней solution publication.

Для migration/performance characterization разрешена локальная защищённая копия production SQLite вместе с `-wal` и `-shm`. Она не коммитится и не используется обычным E2E seed. Content visual gate сравнивает PWA, Telegram и PDF для трёх листков одного уровня из `_vmsh_examples`.

## Автоматические проверки

- Python: schema snapshot, seed repeatability, legacy characterization, app factory imports без Telegram/Google.
- Python/integration: два connection/process writers, `SQLITE_BUSY` retry exhaustion, crash внутри transaction и schema-version mismatch без auto-apply.
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
- Auth preflight перечисляет все неактивируемые Student rows, workload profile задаёт численные входы для этапа 11, а external-process register не содержит строки без владельца/срока следующего решения.

## Пруфы завершения этапа

- [ ] Revision: `<sha>`; миграции: `none` или `<paths>`.
- [ ] Demo: `<make commands>`; seed `baseline-v1`; URLs всех трёх приложений.
- [ ] Isolation report: `<path>` с портами, DB, media, NATS, IndexedDB и scopes.
- [ ] Tests: Python `<result>`; TS `<result>`; Storybook `<result>`; E2E 3 browsers `<result>`.
- [ ] Golden corpus manifest: `<path>`; source hashes/encoding verified `<result>`.
- [ ] Legacy characterization report: `<path>`.
- [ ] DB concurrency/migration ADR и two-writer fault tests: `<path/result>`.
- [ ] Auth preflight aggregates и unresolved policy rows: `<path/result>`.
- [ ] Approved workload profile и external-process decommission register: `<paths>`.
- [ ] Visual baseline environment and screenshots: `<paths>`.
- [ ] Docs updated: `<paths>`.
- [ ] Known limitations/issues: `<links or none>`.
- [ ] Accepted by/date: `<name/date>`.
