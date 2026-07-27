# Статус плана разработки

Последнее обновление: 2026-07-27.

## Состояние документов

| Документ/этап       | Статус                                | Решение/блокер                                                                                                                        |
| ------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Инженерный контракт | draft for approval                    | Формат proof описан; фактически заполняется при реализации                                                                            |
| Решения и границы   | accepted planning input               | Исходный опросник и 4 развилки внешнего ревью закрыты в `17-open-questions.md`                                                        |
| Модель данных       | revised planning input                | Cutoff, season backfill, analytics snapshots и reaction migration уточнены                                                            |
| API/events/files    | accepted planning input               | Batch move, cross-group confirm и classroom history зафиксированы                                                                     |
| Этап 0              | in progress                           | Runtime/schema/seed/auth/storage и one-origin functional E2E 72/72 готовы; visual owner gate, telemetry gaps и live Telegram остаются |
| Этапы 1–11          | planned with gates                    | Продуктовые развилки закрыты; readiness доказывается phase proof, а не дополнительным опросом                                         |
| Design system       | phases 5–7 ready for review           | [Этапы связаны](18-design-implementation-map.md) с components/story IDs; остался ручной owner gate                                    |
| Multi-course model  | verified prototype; owner visual gate | Phase 1–11, UI, stories и tests обновлены; backend/migrations не реализованы                                                          |

## Журнал решений

| Дата       | ID       | Решение                                                                                                  | Последствие                                                                                                                                                   |
| ---------- | -------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-07-23 | PLAN-001 | Этапы строятся как вертикальные работающие срезы                                                         | Backend/UI/contracts/tests/docs закрываются вместе                                                                                                            |
| 2026-07-23 | PLAN-002 | E2E и visual regression выполняются на production Vite bundles за one-origin gateway                     | Dev server остаётся для локальной разработки; gateway моделирует общий host/API/WS, но не заменяет deploy smoke                                               |
| 2026-07-23 | PLAN-003 | A11y gate остаётся для Staff                                                                             | Не создаётся отдельный исключённый контур                                                                                                                     |
| 2026-07-23 | PLAN-004 | Reconnect всегда вызывает authoritative refetch                                                          | WS cursor не используется как доказательство отсутствия пропусков между workers                                                                               |
| 2026-07-23 | PLAN-005 | `_vmsh_examples` — golden corpus, `_external_pipelines` — characterization references                    | Их не редактируют и не импортируют в новый production runtime                                                                                                 |
| 2026-07-24 | PLAN-006 | Первый выпуск: сезон 2025–2026, занятия 39–41, все три уровня                                            | Вертикальные этапы должны привести к полному онлайн-занятию, а не к pilot одной группы                                                                        |
| 2026-07-24 | PLAN-007 | Telegram остаётся двусторонним рабочим каналом на переходе                                               | Треды и provenance объединяют PWA и Telegram; все external pipelines сохраняются до cutover                                                                   |
| 2026-07-24 | PLAN-008 | Печатный/очный раздел, общий Staff→Telegram publisher и AI перенесены во вторую версию                   | Узкая персональная classroom delivery позже выделена отдельным v1-исключением; остальные функции не блокируют первый выпуск                                   |
| 2026-07-24 | PLAN-009 | Исходный продуктовый опросник закрыт                                                                     | Новые вопросы добавляются только при реальной развилке реализации                                                                                             |
| 2026-07-24 | PLAN-010 | Ответы разнесены по модели, API, этапам и эксплуатационным документам                                    | Этап 0 можно начинать без повторного сбора продуктовых требований                                                                                             |
| 2026-07-24 | PLAN-011 | Аудитории разделены на глобальный каталог, наследуемую схему по группам и версионируемый план школьников | Этап 7 получает admin-only catalog/layout/preview/confirm, без capacity и drag-and-drop; initial Excel используется один раз через dry-run/import             |
| 2026-07-25 | PLAN-012 | Classroom planner использует compact single/bulk select и локально накопленный draft                     | Каждая смена select не пишет на server; reload восстанавливает draft, batch-save атомарен, cross-group move требует confirmation                              |
| 2026-07-25 | PLAN-013 | Classroom read model показывает age/class/auto-strength, aggregates, fuzzy search и history              | `users`/`student_strength` остаются источниками; nullable values не входят в averages; confirmed plans образуют историю                                       |
| 2026-07-25 | PLAN-014 | Незавершённую значимую работу Student/Staff нельзя терять                                                | `localStorage` хранит serializable drafts, Dexie — blobs/outbox; очистка только после receipt/confirm/discard                                                 |
| 2026-07-25 | PLAN-015 | Ребёнок никогда не отмечается на групповой статистике                                                    | Self marker, percentile и словесное сравнение с группой запрещены в Student/Family charts                                                                     |
| 2026-07-25 | PLAN-016 | Test input повторяет 23 legacy-типа и `strip()+fullmatch`                                                | Видимая format error; tuple без «Отправится»; list preview после parsing; select передаёт видимый label                                                       |
| 2026-07-25 | PLAN-017 | Review — хронологическая основная колонка, teacher controls компактны, но подписаны                      | Evidence, существующий thread и новый ответ не разделяются на три независимые панели                                                                          |
| 2026-07-25 | PLAN-018 | Condition, hint и solution публикуются независимо; metadata имеет task/answer dropdown                   | У каждого artifact своё «сейчас»/расписание/rollback; TSV paste сохраняется                                                                                   |
| 2026-07-25 | PLAN-019 | Условия идут полноценным Telegram Rich Message, а broadcast editor переносится во вторую фазу            | Stories используют text/math/lists и export corpus; v1 не имитирует рассылку, отдельная submission-квитанция отсутствует                                      |
| 2026-07-25 | PLAN-020 | Client format validation не мешает незавершённому вводу                                                  | `TestAnswer` раскрывает ошибку после blur/submit; fixed tuple остаётся спокойным между слотами; weekday использует кнопки `пн–вс`                             |
| 2026-07-25 | PLAN-021 | Authoritative schema — применённые migrations + проверенный inventory, не старый snapshot в одиночку     | Этап 0 проверяет/перегенерирует `docs/db_structure.sql`; runtime schema drift обнаруживается до business migration                                            |
| 2026-07-25 | PLAN-022 | SQLite concurrency и migration lifecycle становятся обязательным ADR до первой бизнес-миграции           | Нет общего concurrent connection/`await` в transaction; yoyo запускается отдельным deploy command, startup только проверяет version                           |
| 2026-07-25 | PLAN-023 | Submission cutoff и solution publication моделируются раздельно                                          | `lesson_windows.submission_closes_at` существует заранее; policy переноса расписания вынесена в `SCHEDULE-01`                                                 |
| 2026-07-25 | PLAN-024 | Legacy analytics переносится versioned full-run snapshots, история текущего сезона backfill-ится         | `a53`/`a54` получают numerical parity; занятия 1–38 не исчезают из history/progress из-за отсутствия новых publication rows                                   |
| 2026-07-25 | PLAN-025 | Каждый внешний процесс имеет legacy bridge и конечного внутреннего владельца                             | `a00_dates`, `a03`, print/analytics/old-site chains добавлены в register; «не v1» больше не означает бессрочно внешний процесс                                |
| 2026-07-25 | PLAN-026 | Внешнее ревью открыло четыре новые продуктовые развилки без блокировки этапа 0                           | Production cutover соответствующих фаз ждёт ответов `SCHEDULE-01`, `AUTH-01`, `CLASSROOM-01`, `RETENTION-01`                                                  |
| 2026-07-25 | PLAN-027 | У каждого этапа есть явный design implementation map                                                     | Phase-файл ведёт к компонентам, story source и URL; изменение accepted UI обновляет код, story, карту и status вместе                                         |
| 2026-07-26 | PLAN-028 | Internal teacher reactions получают компактный Mod+Alt shortcut                                          | `⌘/Ctrl + Alt + 1…4` работает при фокусе в комментарии; простой Mod+digit оставлен браузеру, `AltGraph` игнорируется                                          |
| 2026-07-26 | PLAN-029 | Внешние converter binaries задаются общим backend config и разрешаются через service `PATH`              | Defaults: `pdf2svg`, `cwebp`, `pdflatex`, `magick`; absolute override/`None` явны, readiness/deploy проверяют capabilities до первого задания                 |
| 2026-07-26 | PLAN-030 | S3 adapter использует общий profile-aware config: Beget test, Hetzner production target                  | Test/production secret sources раздельны; agent/E2E остаются filesystem, secrets всегда redacted; legacy Beget default не считается PWA production default    |
| 2026-07-26 | PLAN-031 | Telegram channel destinations хранятся в course/group `telegram_bindings`                                | `@vmsh179devbot` + private test channel используются opt-in; Bot API canonical ID/rights проверяются, token остаётся config-only, unit/E2E offline            |
| 2026-07-26 | PLAN-032 | Принята иерархия season→course→group→lesson, логические синонимы и multi-course in-person events         | Фазы 1–11 дополнены; Storybook prototype реализован; production backend/migrations остаются невыполненными                                                    |
| 2026-07-27 | PLAN-033 | Cutoff и solution schedule независимы; реальные accounts валидны, тестовые исключаются preflight-ом      | `SCHEDULE-01` и `AUTH-01` закрыты; deadline меняется только отдельным audited action, неизвестный account не активируется молча                               |
| 2026-07-27 | PLAN-034 | Classroom confirm и notification разделены                                                               | Admin после preview явно выбирает PWA/Telegram; Student получает personal delivery, Family только state refetch, auto-resend отсутствует                      |
| 2026-07-27 | PLAN-035 | Print остаётся отдельным разделом v2, media retention — бессрочная admin-managed policy                  | V1 не обещает `a11`–`a14` compatibility export; очистка только manual manifest-driven с preview/audit                                                         |
| 2026-07-27 | PLAN-036 | Opt-in test S3/Telegram side effects явно разрешены владельцем                                           | Disposable test-prefix objects и synthetic test-channel messages можно create/read/edit/delete; production resources запрещены                                |
| 2026-07-27 | PLAN-037 | PWA runtime использует connection-per-operation и никогда не мигрирует SQLite при startup                | Отдельная maintenance-команда применяет yoyo под lock и включает WAL; startup fail-closed проверяет migration IDs/hash/WAL, legacy auto-migrate пока сохранён |
| 2026-07-27 | PLAN-038 | PWA maintenance-команды выбирают состояние только через явный проверенный профиль                        | Guard выполняется до импорта legacy config; неизвестные CLI-аргументы отклоняются, поэтому опечатка не может выбрать fallback DB или credential loader        |
| 2026-07-27 | PLAN-039 | Converter readiness подтверждается разрешением executable и поведенческим smoke                          | Fixed argv без shell, bounded output/timeout/process-group cleanup; synthetic TikZ→SVG и raster→WebP проверяют результат, HEIC capability отражается отдельно |
| 2026-07-27 | PLAN-040 | Legacy rules защищаются executable characterization, corpus — schema-light manifest                      | 23 answer types, verdict/reaction/queue/synonym semantics зафиксированы; 54 source files покрыты hash/encoding/structure без дублирования содержания          |
| 2026-07-27 | PLAN-041 | Schema baseline — migration-derived inventory, а live drift остаётся явным                               | 47 product objects воспроизводимы; 12 derived objects allowlisted; product row values не выбираются, live DDL/defaults сериализуются только fingerprints      |
| 2026-07-27 | PLAN-042 | `baseline-v1` строится вне target и устанавливается только после полной проверки                         | Exact profile/path allowlist, scoped FK gates, purge+VACUUM credentials, shared-runtime/exclusive-maintenance lock и durable atomic replace                   |
| 2026-07-27 | PLAN-043 | Auth/workload preflight читает реальные источники fail-closed и публикует только безопасные агрегаты     | Same-fd bytes/hash и alias rejection защищают inputs; auth query использует deserialize snapshot; explicit check ловит missing/stale report-pair              |
| 2026-07-27 | PLAN-044 | Live S3 разрешён только после pinned test-target check; SDK boundary всегда редактирует provider errors  | Beget test identity закреплена SHA-256, full provider key проверяется после prefix, optional checksums=`when_required`; Hetzner остаётся production target    |
| 2026-07-27 | PLAN-045 | Core NATS — transient fan-out с per-audience cursor и обязательным authoritative reconnect refetch       | Full startup cleanup, reconnect close fallback, bounded WS send/close-before-untrack, graceful shutdown и checked local smoke закрывают lifecycle             |
| 2026-07-27 | PLAN-046 | Live Telegram test использует двухшаговый trust flow                                                     | Read-only bind неизменно пишет owner-only local SQLite; write-smoke не принимает destination из environment и повторно проверяет private channel identity     |
| 2026-07-27 | PLAN-047 | Реестр внешних процессов разделяет наблюдаемый legacy-контур и ещё не реализованный target               | 48 процессов имеют invocation/upstream/side effects/recovery/transition; cutover возможен только после phase proof и явного решения                           |
| 2026-07-27 | PLAN-048 | Runtime namespace принадлежит серверу, а E2E моделирует один production origin                           | Runtime проверяется до router; namespace, PWA scopes/caches и gateway 5380 разделяют аудитории                                                                |
| 2026-07-27 | PLAN-049 | Runtime wire contract версионируется отдельно от browser storage                                         | Неизвестная версия fail-closed; additive v1 fields допустимы при rolling deploy; namespace version меняется только с миграцией локальных данных               |
| 2026-07-27 | PLAN-050 | PWA update recovery не зависит от runtime и IndexedDB gates, а E2E suite сериализован                    | Worker может обновить сломанный startup; единый flock охватывает production build, seed, shared ports и Playwright                                            |
| 2026-07-27 | PLAN-051 | Phase-0 one-origin gateway ещё не является trusted-proxy/auth моделью                                    | Phase 1 задаёт public origin и доверенные proxy hops; spoofed `Forwarded`/`X-Forwarded-*` входят в обязательные negative tests                                |

## Текущий инкремент этапа 0

- Реализация: `db_methods/pwa/migrations.py`, `db_methods/pwa/connection.py`, `main.py`, `vmshpwa/scripts/{runtime_guard,migrate_runtime,seed_runtime}.py`.
- Fault/API tests: `pwa_tests/integration/test_migration_lifecycle.py`, `pwa_tests/integration/test_sqlite_concurrency.py`, `pwa_tests/test_app_factory.py`, `pwa_tests/test_config_safety.py`, `pwa_tests/test_maintenance_commands.py`.
- Проверено 27 июля 2026: 15 целевых migration/concurrency/factory/config tests и 7/7 maintenance guard tests; полный `pwa_tests` — 33/33 PASS на Python 3.14.3.
- Toolchain increment: `helpers/pwa/toolchain.py`, `vmshpwa/scripts/toolchain_{preflight,smoke}.py`, unit/integration tests и `pwa_tests/reports/toolchain-local.md`; локальный preflight и оба converter chains PASS, HEIC advertised.
- Characterization increment: 63/63 domain tests PASS; `vmshpwa/scripts/golden_corpus.py check` подтвердил 54/54 source files. Дополнительно исполняемо зафиксированы `G`/`O` строки `user_changes_log`, повторные no-op commands, nullable `written_tasks_discussions.chat_id/tg_msg_id` и отсутствие достоверной связи legacy message→review round. Открытые правила backfill вынесены в вопросы 12–13. Подробности: `pwa_tests/reports/legacy-characterization.md`.
- Schema increment: 22/22 inventory/migration tests PASS; fresh hash `5ba3e432…`, live read-only check воспроизвёл 12 fingerprinted derived objects, yoyo infrastructure и 2 известных FK-дефекта без изменения `db/vmsh.db`. Sentinel-тесты доказывают, что live SQL/default literals не попадают в отчёт. Подробности: `pwa_tests/reports/live-schema-drift.md`.
- Seed/lifecycle-lock increment: 129/129 focused tests PASS; два последовательных `make pwa-agent-seed` дают digest `193cc450…`; exhaustive answer examples совпадают с legacy regex; scoped FK gate не скрывает ошибки `reactions`; stale WAL очищается только SQLite; shared locks независимых runtime workers исключают migrate/seed и сохраняются до aiohttp cleanup; fork/cancellation/startup-failure/path-alias cases и прежнее окно перед `os.replace` воспроизведены. Подробности: `pwa_tests/reports/baseline-v1.md` и ADR 0002.
- Auth/workload increment: 25/25 focused tests PASS; `make pwa-auth-preflight-check` подтвердил aggregate lower bound 36/1617 Student rows без source values; `make pwa-workload-profile-check` подтвердил 19 raw files, 176713 canonical events и 37408 traces, same-fd source checks и 0 unreviewed labels. Unknown user types, deserialize failure, source-change, symlink/hard-link/duplicate-inode и missing/stale report pairs закрыты. Отчёты: `pwa_tests/reports/{auth-preflight,workload-profile}.{json,md}`.
- Storage increment: 86 focused tests PASS; filesystem atomicity/no-follow, fail-closed S3 config, secret-file race protection, redacted errors, collision-safe live probes, Beget/Hetzner URL rules, pinned live identity и checksum compatibility закрыты. Live Beget test-bucket runs `codex-phase0-20260727-f6c821d9` и `codex-phase0-20260727-collision-safe` прошли put/private-read/public-GET/delete acknowledgement. Отчёт: `pwa_tests/reports/object-storage-phase0.md`.
- Realtime/Telegram harness increment: 74 focused tests PASS. NATS local fan-out/isolation smoke PASS; reconnect/cleanup/readiness, partial-startup cleanup, per-audience cursor, bounded fan-out с close-before-untrack, WebSocket shutdown, strict JSON/event boundary и RecordingBot/two-step binding покрыты. Актуальные полные `make pwa-test` totals приведены в runtime/browser increment ниже. Live Telegram bind/smoke ждёт canonical signed channel ID; Rich Message proof относится к Phase 2. Отчёты: `pwa_tests/reports/phase0-{nats-local,live-integration-template}.md`.
- External-process register increment: 48 current/reference процессов, 36 repository artifacts, два runbook и шесть отсутствующих dependencies описаны без PII; неатомарное окно restore старой DB и обязательный credentials workbook почтового pipeline зафиксированы явно; current/target и `legacy_bridge|v1_cutover|later_internalization` разведены. 7 focused structural/link/privacy/semantic tests PASS. Документы: `21-external-process-register.md`, `16-external-artifacts.md`; fixture: `pwa_tests/fixtures/external-process-register.v1.json`.
- Runtime/browser isolation increment: explicit v1 Python↔Zod wire/error
  fixtures с rolling-deploy policy, bounded pre-router bootstrap, safe
  localStorage, canonical Dexie namespaces с blocked/timeout/close recovery,
  update recovery outside startup gates, scope-versioned Workbox caches и
  lock-aware one-origin production E2E реализованы. Focused Python — 97 PASS;
  `make pwa-test` — Vitest 68 PASS и Python 461 PASS / 1 intentional skip;
  lint/typecheck/build PASS; Storybook browser mode — 32 files / 140 PASS.
  `make pwa-e2e-functional` — 72/72 PASS в Chromium/WebKit/Firefox, включая
  active-worker path denylist, incompatible-runtime update и obsolete-cache
  cleanup; после static-suffix и external-network hardening итоговый
  `make pwa-e2e-runtime` повторно дал 60/60 PASS во всех трёх engines. Startup
  stories: `product-app-startup--runtime-loading`,
  `product-app-startup--runtime-rejected`,
  `product-app-startup--offline-storage-unavailable`. `make pwa-visual` без
  update: Staff 3 PASS; Student current-week 3 ожидаемых stale diff 390×1188 →
  390×1615. Owner approval остаётся обязательным. Отчёт:
  `pwa_tests/reports/runtime-isolation-phase0.md`.
- Этап 0 не закрыт: workload пока не измеряет concurrent sessions/write latency/photo bytes/outbox/`SQLITE_BUSY` budget; live Telegram bind/smoke и visual owner approval ещё впереди. Trusted-proxy/public-origin и spoofed-forwarded matrix явно переданы в Phase 1 и не считаются доказанными текущим gateway.

## Историческая проверка многокурсового прототипа

Проверено 26 июля 2026 года до Phase 0 runtime-hardening; числовые результаты
этого среза не являются текущим gate, актуальные результаты приведены выше:

- `make pwa-lint`, `make pwa-typecheck`, `make pwa-test`, `make pwa-storybook-test`, `make pwa-build` — успешно;
- unit: 4 файла / 29 тестов; Python PWA: 11 тестов; Storybook browser mode: 31 файл / 137 тестов с `addon-a11y` в режиме error;
- production build всех трёх приложений и отдельный Storybook build — успешно; Student/Family собрали валидные `injectManifest` service workers;
- локальные ссылки проверены в 48 Markdown-файлах; `git diff --check` — успешно;
- вручную в agent Storybook просмотрены mobile-light Student/Family и desktop Staff/course/synonym/progress/classroom stories из [карты design→implementation](18-design-implementation-map.md);
- production visual без обновления snapshots: Staff baseline совпал в Chromium/WebKit/Firefox; Student current week ожидаемо отличается во всех трёх браузерах (1188→1615 px, около 4% пикселей) из-за новой многокурсовой композиции;
- visual snapshots намеренно не обновлены до решения владельца;
- backend endpoints, migrations и production wiring не реализованы и не считаются proof завершения фаз 1–11.

## Фактические proof этапов

Пока отсутствуют: это план, а не отчёт о реализации. При завершении этапа сюда добавляется одна строка со ссылкой на заполненный proof-раздел соответствующего phase-файла.

| Этап | Revision | Proof | Принято |
| ---: | -------- | ----- | ------- |
|    0 | —        | —     | —       |
|    1 | —        | —     | —       |
|    2 | —        | —     | —       |
|    3 | —        | —     | —       |
|    4 | —        | —     | —       |
|    5 | —        | —     | —       |
|    6 | —        | —     | —       |
|    7 | —        | —     | —       |
|    8 | —        | —     | —       |
|    9 | —        | —     | —       |
|   10 | —        | —     | —       |
|   11 | —        | —     | —       |
