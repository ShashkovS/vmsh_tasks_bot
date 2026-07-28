# Статус плана разработки

Последнее обновление: 2026-07-28.

## Состояние документов

| Документ/этап       | Статус                         | Решение/блокер                                                                                                                                                        |
| ------------------- | ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Инженерный контракт | draft for approval             | Формат proof описан; фактически заполняется при реализации                                                                                                            |
| Решения и границы   | accepted planning input        | Исходный опросник и 4 развилки внешнего ревью закрыты в `17-open-questions.md`                                                                                        |
| Модель данных       | revised planning input         | Cutoff, season backfill, analytics snapshots и reaction migration уточнены                                                                                            |
| API/events/files    | accepted planning input        | Batch move, cross-group confirm и classroom history зафиксированы                                                                                                     |
| Этап 0              | in progress                    | Runtime/schema/seed/auth/storage, one-origin functional E2E 72/72 и live Telegram bind/send/edit/delete готовы; остаются visual owner gate и telemetry gaps           |
| Этап 1              | in progress                    | Auth/HTTP/WebSocket и proxy boundary зафиксированы в `1aad776`, browser auth E2E 60/60 готовы; остаются server nginx-t/live rate smoke и production controlled import |
| Этап 2              | Phase 2A–2E + browser E2E      | Matching/metadata, PDF, пакетная загрузка и content E2E 3/3 проверены; открыты production parity/backfill и owner visual gate                                         |
| Этап 3              | Phase 3A–3H reading slice      | Course/lesson/home, canonical task/reveal, owner-isolated cold-offline reading и long-corpus KaTeX budget проверены; открыт только visual owner gate                  |
| Этап 4              | Phase 4A–4G functionally ready | Domain/API, draft/outbox, Student submit, Staff recheck и общая PWA/Telegram policy готовы; открыт только visual owner gate                                           |
| Этап 5              | Phase 5A–5D server vertical    | Evidence schema, text/photo draft/submit/read/edit, WebP compensation и review-lock проверены; offline UI/backfill ещё не реализованы                              |
| Этапы 6–11          | planned with gates             | Продуктовые развилки закрыты; readiness доказывается phase proof, а не дополнительным опросом                                                                         |
| Design system       | phases 5–7 ready for review    | [Этапы связаны](18-design-implementation-map.md) с components/story IDs; остался ручной owner gate                                                                    |
| Multi-course model  | schema + verified prototype    | Phase-1 course/access schema и UI prototype готовы; backend repository/HTTP и миграции последующих фаз ещё выполняются                                                |

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
| 2026-07-27 | PLAN-041 | Schema baseline — migration-derived inventory, а live drift остаётся явным                               | Head содержит 94 product objects; live lag 0039/0040 и 12 derived objects фиксируются без записи; product rows не выбираются, DDL/defaults только fingerprint |
| 2026-07-27 | PLAN-053 | Browser user identity отделена от account identity и legacy integer FK                                   | `users.public_id` nullable только до controlled activation; `userId`/`studentId` никогда не подменяются `accountId`, отсутствие значения закрывает web-доступ |
| 2026-07-27 | PLAN-054 | Session reference каноничен на всех cookie/token/storage границах                                        | Только 32 lowercase hex принимаются parser, signed access codec и repository; корректная подпись не легализует иной alias                                     |
| 2026-07-27 | PLAN-055 | Unsafe browser request защищён до появления cookie                                                       | Login тоже требует same-origin evidence; safe set ровно GET/HEAD/OPTIONS, TRACE fail-closed                                                                   |
| 2026-07-27 | PLAN-056 | Teacher authorizes только authoritative resource scope                                                   | Bare capability/collection и сочетание произвольного student ID с разрешённым request group fail-closed; collection фильтруется в SQLite                      |
| 2026-07-27 | PLAN-057 | Forwarded chain — явная deploy-конвенция, а не доверие к произвольному header                            | Trusted proxy заменяет client headers; точные hops и first-element external host/proto доказываются production-like nginx test                                |
| 2026-07-27 | PLAN-058 | Telegram UI scheduled queue является внешним mutable state до публикации                                 | Перед передачей destination Staff scheduler нужен inventory и explicit retain/cancel+recreate/cancel с доказательством no-gap/no-duplicate                    |
| 2026-07-27 | PLAN-059 | Legacy `cor_ans_checker` сначала характеризуется по фактической execution boundary                       | `is_py_func`/restricted globals/`run_py_func_checker` получают synthetic allow/deny/error/cache corpus; это trusted-admin compatibility, не sandbox           |
| 2026-07-27 | PLAN-060 | Cookie-authenticated WebSocket GET всегда проверяет browser Origin                                       | Handshake — исключение из safe-method policy; revoke/logout закрывает session sockets, long-lived connection перепроверяет server state                       |
| 2026-07-27 | PLAN-061 | Ошибочно приложенный материал исправляется append-only проекцией                                         | Owner: teacher + target history; default: scoped admin/post-review/preview; bytes, IDs, evidence и verdict не переписываются                                  |
| 2026-07-27 | PLAN-062 | Combined synonym review выбирает target только по серверному порядку                                     | Последняя `server_received_at`; internal submission ID — детерминированный tie-break, client time не влияет                                                   |
| 2026-07-27 | PLAN-063 | Annotation хранит нормализованные marks, но не состояние просмотрщика                                    | Owner core: pencil/eraser/text/arrow/rectangle/rotation; optional implementation: highlight/palette; zoom/pan локальны                                        |
| 2026-07-27 | PLAN-064 | Ранее подтверждённый аккаунт может читать свой кеш в offline-unverified                                  | Owner: offline reading/logout warning; default: session expiry, auth-before-sync и account cleanup общего устройства                                          |
| 2026-07-27 | PLAN-065 | Delivery observability различает channel success и частичный охват                                       | Owner: counters/partial lists; default: explicit retry только failed recipient/channel pairs без дублей success                                               |
| 2026-07-27 | PLAN-066 | Исторические credential/PII artifacts не становятся новыми fixtures или auth source                      | Migration `0038` и private logs остаются в истории по принятому owner risk; новый pipeline их не копирует и не выводит                                        |
| 2026-07-27 | PLAN-067 | Legacy state backfill не выдумывает события и связи review                                               | Повторные одинаковые `G`/`O` схлопываются; discussion импортируется одним thread без искусственного message→verdict round                                     |
| 2026-07-27 | PLAN-068 | Live Telegram smoke закреплён за owner-provided test-only destination                                    | Canonical `chat.id=-1003913815635` всё равно перепроверяется Bot API; token/production destinations не попадают в код или отчёт                               |
| 2026-07-27 | PLAN-069 | Production-size rehearsal начинается только с безопасной копии                                           | Source `db/vmsh.db` не мутируется; в isolated copy Faker заменяет имена/фамилии, а backup signal не заменяет полный restore rehearsal                         |
| 2026-07-27 | PLAN-070 | Production PWA mode задаётся `pwa-production` либо точным `PROD=true` marker                             | Prototype запрещён; explicit HTTPS origins и `Secure` cookies обязательны, legacy Telegram/Google loader не вызывается                                        |
| 2026-07-27 | PLAN-071 | Trusted proxy поддерживает explicit TCP CIDR либо exact filesystem Unix socket                           | AF_UNIX/local сам по себе не trusted; `sockname`, exact hops и origin обязательны, nginx заменяет headers; live nginx proof не подменяется structural tests   |
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
| 2026-07-27 | PLAN-052 | Phase-1 auth использует Argon2id, audience-salted signed access и soft-revoked rotating refresh sessions | Current defaults rehash после login; HMAC refresh/throttle keys живут только в SQLite; точная модель и источники закреплены в ADR 0003                        |
| 2026-07-27 | PLAN-072 | WebSocket становится routable только после authoritative pending-handshake                               | Session tombstone закрывает close-before-register; initial cursor frame атомарен с audience fan-out, invalidation не опережает handshake                      |
| 2026-07-27 | PLAN-073 | Stored Argon2id ограничен fail-closed resource envelope                                                  | Malformed и чрезмерно дорогой encoding выбирают startup dummy; unknown/invalid paths делают один instrumented Argon verify без wall-clock oracle              |
| 2026-07-27 | PLAN-074 | Telegram renderer закреплён на проверенном Bot API 10.2 Rich HTML dialect                                | До send проверяются 32 768 UTF-8 characters, 500 blocks, nesting 16, 50 media и 20 columns; dialect/limits входят в provenance и live corpus                  |
| 2026-07-28 | PLAN-075 | Publication wall time разрешает только backend в timezone группового занятия                             | Browser передаёт `scheduledLocalTime` + IANA `businessTimezone`; `zoneinfo` переводит в UTC и отклоняет DST gap/fold, `Date.parse()` не используется          |
| 2026-07-28 | PLAN-076 | Written evidence хранит final WebP, а порядок использует sparse ordinal                                  | Durable attachment принимает submission WebP ≤1920; лимит 10 проверяет trigger, временный высокий ordinal позволяет swap при immediate SQLite UNIQUE          |
| 2026-07-28 | PLAN-077 | Каждая Student written entry фиксирует exact problem revision                                            | Thread остаётся общей историей после правки условия; новая entry не теряет provenance, legacy teacher/Telegram backfill может оставить revision nullable      |
| 2026-07-28 | PLAN-078 | Written draft синхронизируется отдельно от окончательной отправки                                        | Поздняя offline-доставка не теряет материал; cutoff применяется при submit к immutable client time, server time и suspicious-clock сохраняются                |
| 2026-07-28 | PLAN-079 | Submission photo хранится только как уникальный final WebP после server re-encode                         | Source не попадает в durable storage; DB failure компенсирует object delete, filesystem использует owner-only mediaPath, production может отдать public S3 URL |
| 2026-07-28 | PLAN-080 | До review-lock страницы можно удалить и переупорядочить; после lock evidence неизменяемо                  | Удаление сразу убирает projection и ставит asset deleted_at; final object остаётся под admin-managed retention до отдельной manifest-driven очистки             |

## Текущий инкремент этапа 0

- Реализация: `db_methods/pwa/migrations.py`, `db_methods/pwa/connection.py`, `main.py`, `vmshpwa/scripts/{runtime_guard,migrate_runtime,seed_runtime}.py`.
- Fault/API tests: `pwa_tests/integration/test_migration_lifecycle.py`, `pwa_tests/integration/test_sqlite_concurrency.py`, `pwa_tests/test_app_factory.py`, `pwa_tests/test_config_safety.py`, `pwa_tests/test_maintenance_commands.py`.
- Проверено 27 июля 2026: 15 целевых migration/concurrency/factory/config tests и 7/7 maintenance guard tests; полный `pwa_tests` — 33/33 PASS на Python 3.14.3.
- Toolchain increment: `helpers/pwa/toolchain.py`, `vmshpwa/scripts/toolchain_{preflight,smoke}.py`, unit/integration tests и `pwa_tests/reports/toolchain-local.md`; локальный preflight и оба converter chains PASS, HEIC advertised.
- Characterization increment: 63/63 domain tests PASS; `vmshpwa/scripts/golden_corpus.py check` подтвердил 54/54 source files. Дополнительно исполняемо зафиксированы `G`/`O` строки `user_changes_log`, повторные no-op commands, nullable `written_tasks_discussions.chat_id/tg_msg_id` и отсутствие достоверной связи legacy message→review round. Владелец закрыл правила backfill: no-op `G`/`O` схлопываются, а historical discussion остаётся единым thread без выдуманной связи с review round. Подробности: `pwa_tests/reports/legacy-characterization.md`.
- Schema/seed inventory: после additive migrations `0041`–`0043` head содержит
  192 product objects с hash `0a7593ea…`; generated inventory/snapshots и
  `make pwa-schema-check` согласованы. Последний live read-only report был снят
  до `0041`, поэтому остаётся историческим Phase-0 evidence и не выдаётся за
  текущую production readiness; `db/vmsh.db` при этом инкременте не открывалась
  на запись.
- Seed/lifecycle-lock increment: два последовательных актуальных agent seed запуска дают digest `782b4051…`; synthetic Family/auth/course/access/scopes и отдельные browser user IDs материализованы, но sessions/audit/throttle/consumed-refresh/history намеренно пусты. Пять Argon2id hashes проверяются только против test-harness credentials; production/path guards и очистка migration-carried credentials сохранены. Exhaustive answer examples совпадают с legacy regex; scoped FK gate, SQLite recovery и lifecycle locking остаются покрыты. Подробности: `pwa_tests/reports/baseline-v1.md` и ADR 0002.
- Auth/workload increment: 25/25 focused tests PASS; `make pwa-auth-preflight-check` подтвердил aggregate lower bound 36/1617 Student rows без source values; `make pwa-workload-profile-check` подтвердил 19 raw files, 176713 canonical events и 37408 traces, same-fd source checks и 0 unreviewed labels. Unknown user types, deserialize failure, source-change, symlink/hard-link/duplicate-inode и missing/stale report pairs закрыты. Отчёты: `pwa_tests/reports/{auth-preflight,workload-profile}.{json,md}`.
- Storage increment: 86 focused tests PASS; filesystem atomicity/no-follow, fail-closed S3 config, secret-file race protection, redacted errors, collision-safe live probes, Beget/Hetzner URL rules, pinned live identity и checksum compatibility закрыты. Live Beget test-bucket runs `codex-phase0-20260727-f6c821d9` и `codex-phase0-20260727-collision-safe` прошли put/private-read/public-GET/delete acknowledgement. Отчёт: `pwa_tests/reports/object-storage-phase0.md`.
- Realtime/Telegram harness increment: 74 focused tests PASS. NATS local fan-out/isolation smoke PASS; reconnect/cleanup/readiness, partial-startup cleanup, per-audience cursor, bounded fan-out с close-before-untrack, WebSocket shutdown, strict JSON/event boundary и RecordingBot/two-step binding покрыты. Актуальные полные `make pwa-test` totals приведены в runtime/browser increment ниже. 27 июля guarded live bind подтвердил test-only bot/private channel identity и права, а synthetic lifecycle успешно выполнил send/edit/delete с cleanup без остаточного сообщения. Rich Message proof относится к Phase 2. Отчёты: `pwa_tests/reports/phase0-{nats-local,live-integration-2026-07-27}.md`.
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
- Этап 0 не закрыт: workload пока не измеряет concurrent sessions/write latency/photo bytes/outbox/`SQLITE_BUSY` budget; впереди visual owner approval. Live Telegram bind и synthetic send/edit/delete smoke пройдены 27 июля. Trusted-proxy/public-origin и spoofed-forwarded matrix явно переданы в Phase 1 и не считаются доказанными текущим gateway.

## Текущий инкремент этапа 2

- Phase 2A реализует только schema/domain/repository boundary: additive
  [`0041`](../../../migrations/0041.pwa_content_lessons.sql), последующие
  concurrency/audit migrations
  [`0042`](../../../migrations/0042.pwa_content_concurrency.sql) и
  [`0043`](../../../migrations/0043.pwa_lesson_window_audit.sql), pure rules
  [`models/pwa/content.py`](../../../models/pwa/content.py) и
  connection-per-operation repository
  [`db_methods/pwa/content.py`](../../../db_methods/pwa/content.py).
- Зафиксированы independent course/group lessons, four-field versioned schedule
  с immutable materialization provenance, append-only revision/problem/synonym
  history, content-addressed assets и atomic publication
  schedule/replace/rollback/reveal invariants.
- Проверено 27 июля 2026: 48 focused domain/repository/migration PASS; 69 PASS
  вместе с полным schema-inventory suite; `make pwa-schema-check`, Ruff check и
  format-check PASS. Exact up/down/up не меняет legacy rows, а
  `db/vmsh.db` не мигрировалась.
- Proof: [`phase2-content-schema.md`](../../../pwa_tests/reports/phase2-content-schema.md).
  Последующие gate закрыли HTTP/UI и safe historical backfill tooling;
  production backfill apply и перечисленные ниже product gates остаются
  открыты, Phase 2 целиком не принят.
- Phase 2B добавляет side-effect-free compiler в
  [`helpers/pwa/content`](../../../helpers/pwa/content): bounded UTF-8/CP1251
  scanner, typed AST, positional diagnostics, role-isolated web/Telegram
  renderers, `WebContentDocument v1` и fixed-toolchain asset converters.
- Golden characterization: 30/30 TeX sources, 334 problem nodes, 0 errors и
  одно ожидаемое legacy-layout warning; report:
  [`phase2-content-compiler.md`](../../../pwa_tests/reports/phase2-content-compiler.md).
  Shared Python/Zod fixture:
  [`python-compiler-preview.v1.json`](../../packages/contracts/fixtures/content/python-compiler-preview.v1.json).
- Pure compiler/Telegram/characterization tests — 69 PASS; asset
  boundary tests — 15 PASS; converter→shared ObjectStorage→repository service —
  5 PASS; WebContentDocument contract — 18 PASS; real local TikZ→SVG and
  raster→WebP smoke with the configured executable paths — 1 PASS.
  Support/limitations:
  [`content-compiler-support-matrix.md`](../../docs/content-compiler-support-matrix.md).
- Phase 2C зафиксирован revisions `1aad776` и `866e3fe`: authenticated
  aiohttp content runtime, compile retry/lease, concurrency-safe publication,
  scheduler, readiness/cutoff gates, bounded history и три audience frontend.
  Staff умеет продолжить загруженную revision после reload, явно выбрать
  предыдущую `ready` revision для rollback, подтвердить опасное действие и
  одновременно сравнить PWA/Telegram preview; Student/Family получают update
  marker при смене revision.
- Schedule wire server-authoritative: UI передаёт `scheduledLocalTime` и
  authoritative IANA `businessTimezone`, а Python `zoneinfo` преобразует wall
  time в UTC и отклоняет DST gap/fold. `lesson_window_changes` из `0043`
  неизменно хранит actor/request/before/after; solution schedule/publish не
  допускается без отдельно заданного cutoff.
- Чистый compiler принимает для web asset только строгий descriptor (public
  ID, SHA-256, безопасный URL, media type, dimensions); hash и URL не могут
  разойтись как независимые источники истины.
- Полный checkpoint 28 июля: `make pwa-lint`, `make pwa-typecheck`,
  `make pwa-storybook-test`, `make pwa-build`, `make pwa-schema-check` — PASS;
  frontend unit — **218 PASS**, Python PWA — **1028 PASS / 3 skip / 1 warning**,
  Storybook browser — **167 PASS**, schema inventory — **192 product objects**;
  production-build `make pwa-e2e-auth` после deep-link default fix — **60/60
  PASS** в Chromium, WebKit и Firefox. Это auth regression, не content E2E.
- Phase 2D (`43b0323`, `08a8d0b`, `d39141d`) добавляет authenticated asset
  inventory/upload, content-addressed WebP/SVG/TikZ storage, immutable local
  media URL, Staff recovery states, PWA cache/proxy и provider-first PDF
  persistence. Regression: 302 Python asset, 10 PDF persistence, 21 frontend
  unit и 17 Storybook browser tests; Ruff/ESLint/typecheck/production builds
  PASS. Proof:
  [`phase2-content-assets-http.md`](../../../pwa_tests/reports/phase2-content-assets-http.md).
- Phase 2E backend добавляет полный immutable positional matching, отдельный
  review ETag, atomic condition metadata-grid confirmation и legacy `problems`
  projection. Teacher получает `403`, stale write — `409`; condition требует
  matching + metadata, а independently compiled hint/solution — собственного
  matching без дублирования task metadata. Domain/repository/real-aiohttp
  suite — **111 PASS**, Ruff — PASS. Proof:
  [`phase2-problem-review-api.md`](../../../pwa_tests/reports/phase2-problem-review-api.md).
- Phase 2E frontend boundary добавляет strict Zod full-batch contracts для
  matching/condition metadata, все 23 historical answer types, GET/PUT client,
  exact `If-Match`, body/header ETag consistency и query hooks. Два package
  typecheck, ESLint и **24 unit tests** — PASS. Proof:
  [`phase2-problem-review-frontend.md`](../../../pwa_tests/reports/phase2-problem-review-frontend.md).
- Phase 2E Staff UI добавляет real-client matching/condition metadata workflow,
  fail-closed publication gate и revision-scoped recovery обоих черновиков из
  `localStorage`. Targeted Storybook — **14 PASS**, Staff production build —
  PASS; snapshots не обновлялись. Proof:
  [`phase2-problem-review-ui.md`](../../../pwa_tests/reports/phase2-problem-review-ui.md).
- Persisted-PDF increment добавляет admin-only descriptor/stream, проверяет
  derivative metadata и exact stored bytes, а в Staff объединяет
  PWA/Telegram/PDF preview без добавления print workflow. Python aiohttp —
  **26 PASS**, frontend unit — **26 PASS**, targeted Storybook — **11 PASS**,
  строгие проверки и Staff production build — PASS. Proof:
  [`phase2-content-pdf-http.md`](../../../pwa_tests/reports/phase2-content-pdf-http.md).
- Bulk-upload target discovery больше не зависит от filename conventions:
  repository/API возвращают только siblings одного `course_lesson`, а strict
  contract/client требуют уникальные public targets. Real aiohttp — **27
  PASS**, frontend unit — **28 PASS**, строгие проверки — PASS. UI orchestration
  закрыта следующим инкрементом. Proof:
  [`phase2-bulk-upload-targets.md`](../../../pwa_tests/reports/phase2-bulk-upload-targets.md).
- Staff bulk-upload UI требует явное file → group lesson → material kind
  сопоставление, валидирует границы и duplicate slots, последовательно
  обрабатывает набор с per-file progress/partial failure и не публикует
  revisions автоматически. Targeted unit — **25 PASS**, Storybook — **12
  PASS**, strict checks и Staff production build — PASS; mobile/desktop light
  просмотрены вручную, snapshots не обновлялись. Proof:
  [`phase2-bulk-upload-ui.md`](../../../pwa_tests/reports/phase2-bulk-upload-ui.md).
- Production-build browser checkpoint `3b5a4e8` добавляет отдельный guarded
  content fixture/seed и `make pwa-e2e-content`. Настоящие Staff и Student UI,
  aiohttp, compiler и SQLite прошли upload → matching → metadata → publish →
  Student read → вторую revision → rollback: **3 PASS** в Chromium, WebKit и
  Firefox. Proof:
  [`phase2-content-e2e.md`](../../../pwa_tests/reports/phase2-content-e2e.md).
- Phase 2 всё ещё открыт для production owner-reviewed parity/backfill и owner
  visual approval. Missing-asset recovery пока не включён в один Playwright
  flow с публикацией и остаётся доказан отдельными live/API/Storybook suites.
  Snapshots не обновлялись. Ранее закрытые HTTP/frontend proof:
  [`phase2-content-api.md`](../../../pwa_tests/reports/phase2-content-api.md),
  [`phase2-content-frontend.md`](../../../pwa_tests/reports/phase2-content-frontend.md).

## Текущий инкремент этапа 3

- Phase 3A revision `d70b0d9` открывает authenticated Student course list и
  enrollment detail поверх revalidated session authority. Handler не принимает
  `studentId`, не выполняет собственный N+1 и возвращает одинаковый `403` для
  неизвестного либо неразрешённого course context.
- `@vmsh/app-shell` экспортирует strict same-origin client и principal-scoped
  TanStack Query hooks. Runtime фиксирует Student audience/API base, unsafe ID
  отклоняется до сети, `401` допускает один штатный refresh/retry.
- Real aiohttp/SQLite auth+content regression — **45 PASS**; app-shell/course
  contracts — **90 PASS**; Ruff, Prettier, ESLint, два strict typecheck и Student
  production build/injectManifest — PASS. Proof:
  [`phase3-course-access-api.md`](../../../pwa_tests/reports/phase3-course-access-api.md).
- Phase 3B revision `66f30c0` добавляет опубликованный lesson list/detail одним
  bounded query; полный content HTTP regression — **32 PASS**, focused TS —
  **16 PASS**. Proof:
  [`phase3-student-lessons-api.md`](../../../pwa_tests/reports/phase3-student-lessons-api.md).
- Phase 3C revision `77927e0` добавляет server-owned home snapshot и подключает
  production `/student/` к реальным enrollment/lesson данным. Production-build
  Staff publish→Student home/read→rollback прошёл **3/3** в Chromium, WebKit и
  Firefox; focused TS — **22 PASS**, content HTTP — **32 PASS**. Proof:
  [`phase3-student-home.md`](../../../pwa_tests/reports/phase3-student-home.md).
- Phase 3D revision `42ea05c` подключает production `/student/tasks` к
  course/group-scoped cursor archive и exact published group lesson. Полный
  regression: **259 TS + 1098 Python PASS**, Storybook **180 PASS**,
  production browser checkpoint **3/3 PASS**. Proof:
  [`phase3-student-task-archive.md`](../../../pwa_tests/reports/phase3-student-task-archive.md).
- Phase 3E revisions `1aeb78d`, `8448a8b` добавляют immutable public identity,
  course/group-scoped canonical problem list, реальные queue/result/synonym
  states и focused condition URL с `problem-*`. Полный regression: **263 TS +
  1100 Python PASS**; production browser checkpoint **3/3 PASS**. Proof:
  [`phase3-student-problem-list.md`](../../../pwa_tests/reports/phase3-student-problem-list.md).
- Phase 3F revision `fabdf93` добавляет точные material availability states,
  закрывает прямой Student hint/solution GET и атомарно пишет immutable reveal
  только после явного подтверждения. Shared disclosure не показывает content
  до успешного audit POST и восстанавливается после ошибки. Полный regression:
  **265 TS + 1100 Python PASS**, Storybook **181 PASS**, production browser
  checkpoint **3/3 PASS**. Proof:
  [`phase3-student-material-reveal.md`](../../../pwa_tests/reports/phase3-student-material-reveal.md).
- Phase 3G revisions `50cd541`, `d4b0b9b`, `89cefb7`, `bb6c6ef`, `d822e2e`
  добавляют secret-free durable auth boundary, 10 MiB owner-scoped validated
  Dexie cache и offline read-through для production Student. Audited hint
  доступен после cold reload, новая publication не доверяет старому reveal, а
  второй Student не видит cache первого. Полный regression: **283 TS + 1101
  Python PASS**, Storybook **182 PASS**, production browser checkpoint **3/3
  PASS**. Proof:
  [`phase3-student-offline-reading.md`](../../../pwa_tests/reports/phase3-student-offline-reading.md).
- Phase 3H revision `f787a64` добавляет browser stress-fixture из четырёх копий
  реальных листков 39–41: **132 задачи / 56 KaTeX**, exact structural checks,
  SVG load-error fallback и мягкий render budget **≤2500 мс**. Полный regression
  — **285 TS + 1101 Python PASS**, Storybook browser — **183 PASS**, strict
  checks и production builds PASS; focused story test time текущего запуска —
  **672 мс**. Proof:
  [`phase3-long-math-rendering.md`](../../../pwa_tests/reports/phase3-long-math-rendering.md).
- Phase 3 остаётся открыт только для ручного visual owner gate; snapshots не
  обновлялись.

## Текущий инкремент этапа 4

- Phase 4A revision `6409191` добавляет additive ledger schema: immutable
  test attempts, idempotency operation и exact checker/config snapshots без
  изменения legacy `results`.
- Phase 4B revisions `bd0487f`, `1d5df54` фиксируют все 23 historical
  `ANS_TYPE`, `strip()` + `fullmatch`, visible-label `SELECT_ONE`, несколько
  правильных ответов, trusted-admin `cor_ans_checker`, client/server cutoff и
  default 3/hour + 6/day rate policy.
- Connection-per-operation repository проверяет account/course/group/content
  authority, исполняет checker вне writer transaction, затем revalidate-ит
  контекст и атомарно пишет attempt + ровно одну legacy `results` строку.
  Exact idempotency replay, mismatch, concurrent race и fault rollback
  проверены отдельными интеграционными тестами.
- Phase 4C revisions `7793d0f`, `0475cd0` добавляют strict Zod request,
  mutation/history response и principal-scoped query keys, а затем
  authenticated POST/GET поверх настоящих cookie, aiohttp и SQLite. Пустая
  история требует текущего access, собственные старые attempts после отзыва
  группы остаются доступны. Новый commit публикует owner-scoped Student
  invalidation, exact replay — нет.
- Phase 4D revisions `6d1909c`, `bab5947`, `5b682d1`, `3d22373` добавляют
  strict same-origin transport, account/problem/revision-scoped local draft и
  immutable Dexie outbox с retry/crash lease/conflict/receipt semantics.
- Phase 4E revisions `a779493`, `6268092`, `9358e76` подключают production
  focused-task route к настоящему input/draft/outbox/history контуру. Отдельный
  production-build Playwright seed позволяет Admin UI выполнить LaTeX upload →
  matching → metadata → publish, после чего Student UI проходит client format
  error без POST, reload draft, online verdict, реальный browser-offline reload
  и exactly-once retry.
- Phase 4F revision `2b00b06` переводит historical Telegram test-answer
  handler и legacy admin recheck на ту же `evaluate_test_answer` policy. Все
  23 `ANS_TYPE`, visible-label `SELECT_ONE`, invalid-format без расхода лимита
  и безопасный broken-checker path закреплены в `make telegram-history-test`:
  **44 PASS**. Telegram по-прежнему пишет в legacy `results`; PWA attempt/
  idempotency ledger не подменяет отсутствие web revision/account context у
  старых bot-задач.
- Phase 4G revisions `e5b83a4`, `0fde237` добавляют preview/apply recheck для
  `pending_configuration`, привязанный к current published revision, и
  production Staff route `/staff/problems/$problemId`. Immutable attempt
  сохраняет исходный ответ, а authoritative outcome/result обновляются
  атомарно; teacher получает `403`, stale revision — `409`, broken checker
  остаётся retryable. Storybook IDs:
  `product-test-answer--recheck-pending`,
  `product-test-answer--recheck-still-pending`,
  `product-test-answer--recheck-conflict`,
  `product-test-answer--recheck-loading`.
- Focused domain/repository — **66 PASS**; repository/real-aiohttp/app-factory
  regression дополнен recheck concurrency/rollback/authority; contracts —
  **94 PASS**; чистый полный Python run — **1180 PASS / 3 intentional skips**;
  frontend unit — **42 файла / 323 PASS**; Storybook browser — **38 файлов /
  187 PASS**; production-build Phase-4 E2E — **6/6 PASS**: два workflow в
  Chromium, WebKit и Firefox; lint, strict typecheck и production build — PASS.
  Proof:
  [`phase4-test-submission-domain-and-repository.md`](../../../pwa_tests/reports/phase4-test-submission-domain-and-repository.md).
- Функциональные критерии Phase 4 закрыты; открыт только ручной visual owner
  gate. Structured Telegram attempt/idempotency persistence остаётся отдельной
  будущей cutover-задачей и не блокирует этап. Staff recheck/configuration-repair
  для PWA ledger закрыт. Product input/recheck stories служат UI-контрактом;
  snapshots не обновлялись.

## Текущий инкремент этапа 5

- Phase 5A revisions `5acecbb`, `c6d6fd8` добавляют migrations
  `0047.pwa_submission_threads_entries_assets`: versioned threads/entries,
  максимум 10 final submission WebP ≤1920, review evidence lock и append-only
  material reassignment без изменения legacy Telegram discussions/queue.
- Condition revision scope проверяется через concrete `problem_revisions`.
  Sparse non-negative attachment ordinal позволяет безопасный reorder при
  immediate SQLite UNIQUE; отдельный trigger обеспечивает продуктовый лимит.
- Exact `up → down → up`, additive row preservation, state/version/owner/result
  scopes, attachment contract/limit/reorder/lock и reassignment audit:
  **6 PASS**. Schema lifecycle regression: **31 PASS**.
- Entry-revision hardening migration `0048` фиксирует exact
  `problem_revision_id` на каждой Student entry; thread остаётся общей историей
  после новой публикации условия, а старый teacher/Telegram backfill может
  оставить поле пустым.
- Fresh inventory: **263 product objects**, SHA-256 `8032fb8b…`; полный
  checkpoint: **323 frontend + 1186 Python PASS**, 3 intentional skips и одна
  существующая SymPy warning. `make pwa-schema-check`, Ruff и
  `git diff --check` — PASS. Proof:
  [`phase5-written-submission-schema.md`](../../../pwa_tests/reports/phase5-written-submission-schema.md).
- Upload/conversion/cleanup, offline composer, backfill,
  reassignment API/UI, Storybook и E2E остаются следующими Phase 5 increments;
  наличие схемы их не доказывает.
- Phase 5B revisions `dbfd1ae`, `acbc8ec` добавляют text-only server vertical:
  connection-per-operation repository, strict Zod fixture/contract и три
  authenticated Student endpoints create/submit/read. Устные типы 3/4 также
  принимают письменный материал; test type 1 остаётся в Phase 4 API.
- Draft→submitted и thread→awaiting_review выполняются атомарно; exact replay и
  ожидаемый failure хранятся в общем idempotency ledger, а неожиданный fault
  откатывает весь unit of work. Closed owner history читается после access
  revoke; чужая/недоступная задача не раскрывается.
- Focused repository — **11 PASS**, общий submission repository — **34 PASS**,
  real aiohttp content/submission — **39 PASS**, written Zod — **4 PASS**.
  Полный checkpoint: frontend **43 файла / 327 PASS**, Python PWA **1199 PASS /
  3 intentional skips / 1 existing SymPy warning**, Storybook browser **38
  файлов / 187 PASS**; lint, strict typecheck и production build с обоими
  injectManifest — PASS. Proof:
  [`phase5-written-submission-api.md`](../../../pwa_tests/reports/phase5-written-submission-api.md).
- Phase 5C revision `9c065db` добавляет bounded multipart photo upload,
  shared raster/HEIC→WebP converter, server-derived `sol_imgs` key, final
  storage metadata и owner-only integrity-checked media read. Source image не
  становится durable object; final WebP обязан иметь обе стороны ≤1920.
- Object put предшествует одной SQLite transaction. Stale/mismatch/fault после
  put удаляет уникальный object; concurrent exact replay не оставляет объект
  проигравшего запроса. `written-attachment:create` replay останавливается до
  повторной конвертации и storage write.
- Focused attachment/service/repository — **10 PASS**, общий submission
  repository — **44 PASS**, real aiohttp content/submission — **40 PASS**,
  written Zod — **5 PASS**. Полный checkpoint: frontend **43 файла / 328
  PASS**, Python PWA **1210 PASS / 3 intentional skips / 1 existing SymPy
  warning**, Storybook browser **38 файлов / 187 PASS**; lint, strict typecheck
  и production build с обоими injectManifest — PASS. Proof:
  [`phase5-written-attachment-api.md`](../../../pwa_tests/reports/phase5-written-attachment-api.md).
- Phase 5D revision `38579a5` добавляет complete-list reorder, logical delete
  и explicit no-op response для draft и submitted-before-review evidence.
  SQLite migration `0049` запрещает оставить submitted entry без текста и
  фотографий; owner/version/state/lock повторно проверяются в одной write
  transaction.
- Reorder использует временные sparse ordinals и заканчивает плотным `0…n-1`.
  Delete сразу удаляет attachment из projection и ставит asset `deleted_at`;
  physical final WebP остаётся под принятой admin-managed retention policy.
  Locked evidence возвращает отдельный conflict, exact replay не меняет версии
  и не публикует повторную invalidation.
- Repository/schema/real-aiohttp checkpoint — **88 PASS**, written Zod — **6
  PASS**, schema inventory — **264 objects / PASS**. Полный checkpoint:
  frontend **43 файла / 329 PASS**, Python PWA **1215 PASS / 3 intentional
  skips / 1 existing SymPy warning**, Storybook browser **38 файлов / 187
  PASS**; lint, strict typecheck и production build с обоими injectManifest —
  PASS. Proof:
  [`phase5-written-attachment-mutations.md`](../../../pwa_tests/reports/phase5-written-attachment-mutations.md).
- Следующий gate: browser worker + localStorage/Dexie composer/outbox и
  thumbnails. Post-submit pre-review atomic replacement, live test S3, legacy
  backfill/reassignment, Staff review, Storybook interaction, production E2E
  и visual owner gate остаются открыты; snapshots не обновлялись.

## Текущий инкремент этапа 1

- `4343371` добавляет чистые правила входа, Argon2id, вычисление ближайшей
  границы 10 августа по Москве, HMAC refresh digest и audience-salted signed
  access token; `08d6980` приводит публичный session ID к каноническому
  lowercase browser-контракту. Focused Python suite: 24 PASS.
- `3b22eaa` добавляет fail-closed auth runtime config: отдельные public origins,
  cookie names/paths, signing keyring и независимые refresh/throttle peppers.
  Prototype defaults существуют только для известных isolated profiles;
  production не смешивается с ними. Auth/config suite: 36 PASS.
- `36f6bb2` добавляет Zod-first audience-specific login/auth/session и
  multi-course enrollment/access contracts, versioned synthetic valid/invalid
  fixtures и principal-scoped query keys. Student body не принимает `audience`,
  а срок fixture `2026-08-09T21:00:00Z` явно доказывает московскую границу.
  Focused Vitest: 15 PASS; contracts typecheck, ESLint и Prettier PASS.
- Cookie/token boundary принимает только тот же 32-символьный lowercase hex
  session reference, который создаёт генератор и принимает repository. Даже
  корректно подписанный payload с неканоническим `sid` отклоняется до SQLite;
  focused model suite — 29 PASS.
- Чистые permission и request-security policies добавлены в
  `helpers/pwa/{permissions,request_security}.py`: роли и scopes fail-closed,
  Student/Family ownership не смешивается с request scope, Staff collection
  требует scope-filtered repository query, а unsafe login проходит тот же
  Origin/Referer/Fetch Metadata gate. Cookie-bearing WebSocket GET отдельно
  требует allowlisted Origin. Focused suite на этом срезе — 156 PASS; actual
  aiohttp TCP/Unix и nginx structural boundary закрыты более поздним proxy
  increment ниже, server syntax/live burst остаются deploy proof.
- Миграции `0039`/`0040` добавляют auth/session/throttle и первый
  course/enrollment/access/scope слой без изменения legacy IDs и имеют точный
  rollback. Fresh inventory содержит 94 product objects; read-only live report
  честно фиксирует, что `db/vmsh.db` пока отстаёт на две миграции. Phase-1
  актуальный объединённый migration/schema/seed suite — 129 PASS, полный
  Python PWA suite до opaque user-ID increment — 520 PASS / 1 intentional
  skip; полный suite будет повторён после сборки auth repository.
- `baseline-v1` schemaVersion 2 детерминированно материализует Student online,
  Student in-person, Family с двумя детьми, Teacher/Admin, один season/course,
  enrollments/access/scopes и ни одной предварительно созданной browser session.
  Два agent seed запуска дали одинаковый digest `782b4051…`; актуальный
  seed+migration/schema suite — 129 PASS.
- Auth repository реализует connection-per-operation login/session/refresh,
  soft revoke, credential invalidation, shared-worker throttle и
  course/family/staff authority reads. Независимое ревью закрыло exact legacy
  types, identity TOCTOU, Student token↔hash atomicity, canonical public IDs,
  session metadata bounds и collision rollback. Полный Python PWA suite после
  исправлений — 669 PASS / 1 intentional skip; focused auth/schema/seed —
  160 PASS, Ruff/schema/live-drift checks — PASS.
- HTTP auth increment реализует семь audience routes, default-private
  middleware, exact Origin/target boundary, audience cookie paths и
  authoritative SQLite revalidation. Real aiohttp/migrated-SQLite tests
  покрывают Student/Family/Staff login, capabilities, refresh replay, logout,
  logout-all и revoke-device; corrupt-principal cleanup покрыт service tests.
  Focused auth/repository/HTTP/transport gate — 245 PASS; полный `pwa_tests` —
  714 PASS / 1 intentional skip. Logout гарантированно отзывает живую
  access-сессию даже без refresh-cookie, а public allowlist сопоставляет точные
  method/resource пары. Production marker tests доказывают, что
  `pwa-production` и `PROD=true` включают HTTPS/`Secure`, а prototype
  fail-closed запрещён.
- Authenticated realtime increment связывает каждый WebSocket с проверенными
  audience/account/session до upgrade, сериализует все операции над transport,
  закрывает session/account sockets local-first и через строгий versioned NATS
  control event, а при сбое fan-out fail-closed перепроверяет server state в
  SQLite. Owner-scoped invalidation доставляется только вкладкам нужного
  account и не раскрывает account ID в browser payload или логах. Logout,
  refresh-only logout, revoke-device и logout-all закрывают только доказанные
  targets; wrong/foreign/replayed refresh secret не образует close-oracle.
  Полный `.venv/bin/pytest -q pwa_tests` — 759 PASS / 1 intentional skip;
  missing/wrong Origin, cross-audience cookie, expired/out-of-band-revoked
  session, multiple tabs/devices, cross-worker close, publish failure fallback,
  send/close race и owner isolation покрыты регрессиями.
- Phase-1 race/resource hardening делает post-upgrade socket pending и
  non-routable до повторной SQLite-проверки и первого cursor frame. Session
  tombstone закрывает auth→register revoke race, а audience broadcast lock —
  initial-frame/invalidation ordering. Stored Argon2id дополнительно проходит
  generous bounded resource policy; malformed/out-of-policy active row и
  unknown login выполняют один и тот же dummy verify. Barrier/work-count tests
  не используют wall-clock. Focused suites — 31 PASS и 45 PASS; полный
  `.venv/bin/pytest -q -n0 pwa_tests` — **808 PASS / 1 intentional skip**.
  Proof: [`phase1-auth-race-hardening.md`](../../../pwa_tests/reports/phase1-auth-race-hardening.md).
- Frontend auth wiring подключает server-authoritative `/auth/me` во всех трёх
  приложениях после validated runtime (и после IndexedDB gate в Student/Family),
  не монтирует private shell до подтверждённой сессии и сохраняет безопасный
  app-relative `returnTo` с query/hash. Controlled формы используют ровно
  `telegramToken` для Student и `password` для Family/Staff; состояния invalid,
  rate-limited, account-unavailable и network покрыты без account enumeration.
  Явные Staff capability gates закрывают classrooms, broadcasts и audit.
  Route generation, typecheck, ESLint/stylelint и production build трёх apps —
  PASS; Vitest unit — 16 файлов / 138 PASS, Storybook browser mode — 32 файла /
  140 PASS. Реальный browser E2E входа/refresh/logout с aiohttp остаётся gate.
- Domain-neutral session/device UI добавлен в `packages/app-shell` и подключён
  к Student/Family profile: настоящий `GET /auth/sessions`, current marker,
  revoke одной чужой сессии, current logout и logout-all с подтверждением.
  Empty/corrupt/cross-audience ответы и ошибка offline-work inspection работают
  fail-closed; opaque session IDs не становятся видимыми device labels.
  `SessionOfflineWorkGuard` доказывает предупреждение для непустой очереди и
  порядок server logout → cleanup даже при размонтировании shell, но реальный
  Dexie adapter честно отложен. Staff route не придуман. Focused unit — 18
  PASS; session Storybook interaction + addon-a11y — 9 PASS; snapshots не
  обновлялись и visual owner gate остаётся открытым.
- Frontend auth hardening сериализует single-use refresh между вкладками через
  audience-scoped Web Locks. Каждый получивший lock сначала повторяет `/auth/me`;
  поэтому второй contender не расходует уже ротированный secret. Без Web Locks
  bounded BroadcastChannel/storage wake-up приводит только к fail-closed
  `/auth/me`, а не к небезопасной localStorage-lease. `sessionExpiresAt`
  enforced как абсолютная server-owned граница таймером и browser-resume
  checks; prior-verified `offline-unverified` UI размонтируется по expiry.
  Focused auth/session Vitest — 31/31 PASS, app-shell typecheck и scoped ESLint
  — PASS. Повторный полный gate: frontend unit 19 файлов / 162 PASS, Python PWA
  808 PASS / 1 intentional skip, Storybook browser mode 33 файла / 152 PASS;
  full lint/typecheck — PASS.
- Canonical auth preflight теперь исполняет frozen Student username algorithm
  v1 на read-only snapshot `db/vmsh.db`: 1617 Student rows, 10 field/token
  blockers, 29 collision groups / 58 affected rows и 1549 eligible до явных
  overrides/launch-cohort exclusions. Отчёты не содержат IDs, login candidates
  или credentials; focused privacy/source-safety suite — 10 PASS. Apply и
  collision overrides ещё не выполнены.
- Controlled Student import tooling готово для **отдельной migrated copy**:
  owner-only inventory, deterministic preview без Argon2 и all-at-once apply с
  повторной проверкой под `BEGIN IMMEDIATE`. Explicit cohort/exclusions и
  overrides обязательны; target разрешён только под `.runtime/auth-import/`, а
  authoritative/human/agent DB, symlink/hardlink, небезопасные
  permissions и несовпавший confirmation path отклоняются. Повторный apply
  идемпотентен, а aggregate proof не содержит IDs/login candidates/credentials.
  Quiescent snapshot sidecars также fail-closed. Focused suite — 16 PASS,
  включая concurrent source change; synthetic 1617-row
  preview — менее `1 s`, без Argon2; локальная оценка default Argon2 для 1549
  pending rows — около `0.8 min` до write transaction и ещё `0.8 min` для
  post-commit verification. Runbook:
  [`phase-1-student-auth-import.md`](../../docs/phase-1-student-auth-import.md),
  proof: [`phase1-auth-import-tooling.md`](../../../pwa_tests/reports/phase1-auth-import-tooling.md).
  Настоящие overrides/exclusions и production apply не выполнялись; course
  enrollment/access/event backfill явно отложен и не фабрикует `G`/`O` events.
- Production proxy boundary реализован: one-host nginx template, exact
  forwarding replacement, per-IP login `429`/`Retry-After`, fail-closed CSP,
  loopback TCP/exact Unix transport и wrong-path/host/proto/chain/WS Origin
  regression. Production hostname не зашит: checker требует exact approved
  lowercase `VMSH_PWA_PUBLIC_HOST` и сверяет оба `server_name`, redirect и CSP.
  Pure + actual aiohttp + structural suite — 106 PASS; локальный
  syntax helper вернул explicit `UNAVAILABLE`/exit 2 из-за отсутствующего nginx;
  полный Python PWA suite — 793 PASS / 1 intentional skip.
- Следующий gate: server `nginx -t` и live rate-limit smoke, утверждённые
  owner decisions + rehearsal/apply controlled import
  и реальный browser E2E login/refresh/logout/revoke. Владелец принял
  риск старых credential-like literals в migration history; они не копируются
  в fixtures/reports и не становятся источником нового web-входа. Controlled
  production activation всё равно требует preflight, актуальных
  Telegram-токенов и явного отчёта. Историческая credential-развилка закрыта,
  но настоящий inventory теперь требует owner-only decision-файл для 10
  blockers и 58 строк login-collision; это открытый вопрос 16 в
  [`20-implementation-questions.md`](20-implementation-questions.md), а не
  повод угадывать исключения или логины.

## Phase 1 browser-auth increment — 27 июля 2026

- Production entry всех трёх приложений использует server-authoritative auth;
  private routes сохраняют безопасный intended route с query/hash, а Teacher и
  Admin получают разные Staff route gates.
- Единый test-only fixture
  `pwa_tests/fixtures/auth-credentials-v1.json` согласован с seed; product bundle
  его не импортирует. Playwright использует настоящий aiohttp и отдельную SQLite
  через one-origin gateway, без MSW, Telegram, Google и mock-auth backdoor.
- `make pwa-e2e-auth` — **60/60 PASS** в Chromium, WebKit и Firefox: четыре
  роли, reload/logout, cookie Path и audience isolation, simultaneous sessions,
  invalid credentials, deep-link return, `401`, Host/Origin/forwarding,
  explicit refresh rotation, single-flight automatic recovery при отсутствующей
  access-cookie, two-tab recovery с ровно одним refresh request и revoke
  отдельного устройства.
- Этот production-build gate повторно подтверждён 28 июля после исправления
  default deep-link; отдельный Phase-2 content Playwright flow позднее закрыт
  revision `3b5a4e8`.
- Browser proof нашёл и закрыл Family `500` на ISO `users.birthday`:
  `FamilyChildRecord.birthday` читает nullable строку; repository regression
  закрепляет реальный формат legacy данных.
- Актуальные соседние gates: Vitest **16 файлов / 139 PASS**; Python PWA
  **780 PASS / 1 intentional skip**; Storybook browser mode **32 файла / 143
  PASS** с addon-a11y error; lint, typecheck и production build — PASS.
- Более ранние строки этого журнала, где browser auth E2E назван будущим gate,
  этим блоком заменены. Не закрыты controlled production import, server
  `nginx -t`/live rate smoke и browser Teacher→admin API `403`: последний ждёт
  первого настоящего capability-protected admin endpoint Phase 2/7/8/10.
  Искусственный production endpoint ради теста не добавляется; UI forbidden и
  permission/API matrix уже покрыты.

## Phase 1 frontend realtime increment — 27 июля 2026

- Общий [`RealtimeProvider`](../../packages/app-shell/src/realtime.tsx)
  подключён в production entry Student, Family и Staff только внутри
  authenticated context. Same-origin URL содержит максимум memory cursor;
  credential/account/session IDs не попадают в URL или Web Storage.
- Клиент fail-closed валидирует frame, требует `connected` на первом handshake
  и `resync-required` после любого reconnect, выполняет полный active Query
  refetch до ready, коалесцирует invalidations и ограничивает
  handshake/heartbeat/backoff. Offline/hidden и StrictMode cleanup не оставляют
  reconnect storm или дублирующий transport.
- `1008` и нормализованный transport-слоем `1000` запускают HTTP authority
  check. Revoke current session переводит private route на login и не открывает
  новый socket; подтверждённая session продолжает обычный cursor/refetch path,
  transient network/5xx повторяет authority check с bounded backoff и не
  оставляет клиент навсегда заблокированным.
- Focused Vitest: **2 файла / 17 PASS**. `make pwa-e2e-realtime`: **12/12 PASS**
  в Chromium, WebKit и Firefox после production build трёх приложений.
  Visual snapshots не обновлялись; provider не меняет визуальное состояние.
- Повторный полный `make pwa-e2e-runtime` сначала подтвердил realtime revoke /
  reconnect, theme-storage и IndexedDB isolation, но обнаружил шесть падений
  Student/Family PWA-update. Разбор trace показал, что новый worker уже
  становился controller и приложение делало reload, а тест ошибочно требовал
  навигацию на корневой URL: к этому моменту auth boundary мог сохранить
  `/student/login?returnTo=…` или `/family/login?returnTo=…`. Product-кнопка
  теперь адресует фактический `registration.waiting` напрямую, а E2E доказывает
  reload с сохранением текущего audience-local URL. Точный повторный сценарий
  `a byte-different built worker reaches prompt and controls the page` —
  **6/6 PASS** в Chromium, WebKit и Firefox. Полный runtime suite после этой
  локальной правки ещё должен быть повторён; snapshots не обновлялись.
- Реализующие/проверяющие файлы:
  [`realtime-client.test.ts`](../../packages/app-shell/src/realtime-client.test.ts),
  [`realtime-provider.test.tsx`](../../packages/app-shell/src/realtime-provider.test.tsx),
  [`runtime-isolation.spec.ts`](../../e2e/runtime-isolation.spec.ts),
  [`e2e_runner.py`](../../scripts/e2e_runner.py). Target зафиксирован как
  `make pwa-e2e-realtime`.

## Phase 2 browser content renderer increment — 27 июля 2026

- Production browser wire отделён от внутреннего compiler AST и legacy
  `web_html`: [`WebContentDocument v1`](../../packages/contracts/src/content.ts)
  имеет tagged camelCase blocks, один material kind, обязательный persisted
  `revisionId` и отдельную nullable preview schema. Generic preflight до
  recursive Zod parsing ограничивает depth/nodes/text; shared Python preview
  fixture доказывает отсутствие sibling answer/hint/solution branches.
- [`SemanticMathDocument`](../../packages/content/src/math-document.tsx)
  рендерит paragraphs/headings/lists/subparts/callouts/tables/formulas и только
  внешние SVG/raster figures. Compatibility `MathHtml` fail-closed отклоняет
  script/event/style/inline SVG/forms/unsafe URL целиком и монтирует очищенный
  `DocumentFragment`, не raw HTML string.
- KaTeX работает на клиенте с `trust:false`, bounded `maxSize`/`maxExpand` и
  детерминированным локальным fallback. [`ZoomableAssetFigure`](../../packages/content/src/zoomable-asset-figure.tsx)
  применяет один transform к холсту и изображению, поддерживает keyboard,
  buttons, pinch/pan и missing/load-error state.
- Focused Zod/sanitizer/renderer unit: **3 files / 33 PASS**; TypeScript,
  scoped ESLint/stylelint и `git diff --check` — PASS. Focused Storybook
  browser mode: **9/9 PASS** в Chromium с addon-a11y `error`. Story IDs и
  остающиеся integration/visual gates: [`phase2-web-renderer.md`](../../../pwa_tests/reports/phase2-web-renderer.md).
- Этап 2 целиком не закрыт: API/page wiring, storage/asset resolution,
  publication flow, corpus/PDF/Telegram/S3 gates и visual owner approval ещё
  впереди. Snapshots не обновлялись.

## Phase 2 live derivatives и authenticated content vertical — 28 июля 2026

- Локальный полный TeX дал воспроизводимую PDF-производную: real
  `pdflatex` smoke — **1 PASS**. Test bot в подтверждённом приватном test
  channel выполнил compiler-owned Rich Message на границе 32 768 symbols:
  send/edit/delete/cleanup — **PASS**, публикация удалена. Proof:
  [`phase2-derivative-adapters.md`](../../../pwa_tests/reports/phase2-derivative-adapters.md).
- Фиксированные synthetic TikZ и raster прошли реальный
  SVG/WebP → test S3 `PutObject` → private read → public GET → delete под
  `integration/phase2-assets-20260727-a1/`: **2/2 PASS**, оба объекта удалены.
  Hermetic service/guard suite — **13 PASS**. Proof:
  [`phase2-content-assets-live.md`](../../../pwa_tests/reports/phase2-content-assets-live.md).
- Повторное review после `0042`/`0043` приняло backend boundary в `1aad776`:
  source/compile leases и publication slots сериализованы, rollback отменяет
  ровно ожидаемый schedule, due scheduler/hide/invalidation и terminal audit
  проверены. Publish/schedule/rollback дополнительно требуют resolved problem
  matches + reviewed metadata; solution требует отдельный lesson cutoff.
  Staff history ограничена сервером и содержит authoritative timezone.
- Frontend vertical в `866e3fe` использует тот же wire: после reload продолжает
  `uploaded`/expired-compiling revision, для rollback предлагает предыдущую
  `ready`, не переводит `datetime-local` через timezone браузера, подтверждает
  publish/schedule/rollback/hide и показывает два preview рядом на desktop.
  Student/Family читают только published typed document и отмечают новую
  revision без показа внутренних compiler/publication данных.
- Полный общий gate: lint/typecheck/build/schema PASS, 218 TypeScript unit,
  1028 Python PASS (3 skip, 1 warning), 167 Storybook browser PASS и 192
  product schema objects. Подробные команды и остающиеся границы:
  [`phase2-content-api.md`](../../../pwa_tests/reports/phase2-content-api.md) и
  [`phase2-content-frontend.md`](../../../pwa_tests/reports/phase2-content-frontend.md).
- Этот checkpoint сам по себе не завершал Phase 2: перечисленные здесь asset,
  matching/metadata, stored PDF, bulk-upload и production content E2E gaps
  закрыты последующими proof выше. Текущие открытые gate — production
  owner-reviewed parity/backfill и owner visual approval. Snapshots не
  обновлялись.

## Phase 2 real-content Storybook gate — 27 июля 2026

- Условия начинающих занятий 39–41 теперь имеют воспроизводимые committed
  fixtures: exact source/PDF SHA-256, typed PWA document и Telegram Rich
  derivative из одного compiler run. Stale fixture обнаруживает отдельный
  `check`-режим; Python corpus/renderer suite — **37 PASS**, TypeScript contract
  — **21 PASS**.
- Story
  `Product/Mathematical document/Real corpus--Lessons 39–41 · PWA, Telegram and PDF`
  прошла **1/1** в browser mode с addon-a11y `error`. Desktop и mobile 390 px
  light просмотрены вручную; mobile horizontal overflow отсутствует.
- Visual gate нашёл и закрыл не фиктивную ошибку: print-header newlines больше
  не становятся высоким пустым `<p><br/>…</p>` в Telegram derivative. PDF tab
  показывает проверяемый repository reference artifact, а не browser print.
- Proof:
  [`phase2-real-content-corpus.md`](../../../pwa_tests/reports/phase2-real-content-corpus.md).
  Snapshots не обновлялись, owner visual approval и generated-PDF parity всё
  ещё не закрыты.

## Phase 4 browser transport, production UI, Staff recheck, E2E и Telegram — 28 июля 2026

- [`submission-client.ts`](../../packages/app-shell/src/submission-client.ts)
  добавляет strict same-origin Student transport и TanStack Query hooks;
  единственный `401` retry повторяет тот же body и UUID.
- POST-контракт теперь обязательно несёт expected condition revision/config
  version. Реальный aiohttp отклоняет stale offline payload как
  `409 test_problem_revision_changed`; focused Python integration — **21 PASS**.
- [`test-answer-draft.ts`](../../packages/offline/src/test-answer-draft.ts)
  сохраняет account/problem/revision-scoped текст в `localStorage`, явно
  возвращает несовместимую revision и не скрывает write/quota failure.
- [`test-answer-outbox.ts`](../../packages/offline/src/test-answer-outbox.ts)
  сохраняет immutable request/UUID/hash в Dexie, сериализует claim, повторяет
  network failure и crashed sending lease, удерживает conflict/failed и
  удаляет synced запись только после явного acknowledge.
- Offline focused — **7 файлов / 34 PASS**; полный frontend unit — **39 файлов /
  311 PASS**; TypeScript и scoped ESLint — PASS. Подробный proof:
  [`phase4-test-submission-domain-and-repository.md`](../../../pwa_tests/reports/phase4-test-submission-domain-and-repository.md).
- Revisions `a779493`, `6268092` подключают type-safe input и production
  Student route к transport + draft + outbox + history. Revision `9358e76`
  добавляет отдельный E2E seed/runner target и настоящий offline browser proof.
- Актуальный полный checkpoint: frontend **42 файла / 323 PASS**, Python PWA
  **1180 PASS / 3 intentional skips**, Storybook browser **38 файлов / 187
  PASS**, production-build E2E **6/6 PASS**: Student submit и Staff repair/
  recheck в Chromium, WebKit и Firefox; lint/typecheck/build PASS. MSW,
  Telegram, Google, S3 и `db/vmsh.db` не использовались.
- Revision `2b00b06`: Telegram test-answer handler и legacy admin recheck
  используют общую PWA domain policy; historical fake-Bot/isolated-SQLite
  regression — **44 PASS**, без Telegram network/credentials. Сломанный checker
  не создаёт ложный минус и не раскрывает source/answer/traceback.
- Revisions `e5b83a4`, `0fde237` закрывают Staff configuration repair/recheck
  для нового attempt ledger: current-revision preview/apply, immutable исходная
  попытка, atomic result projection, authority/conflict/concurrency/rollback и
  owner invalidation проверены repository, aiohttp и production-browser tests.
- Открыты ручной visual owner gate и отдельное решение по cutover legacy
  Telegram `results` в structured attempt ledger; snapshots не обновлялись.

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

Таблица различает промежуточный проверенный инкремент и окончательное принятие
этапа. Наличие revision/proof не закрывает оставшиеся criteria из phase-файла.

| Этап | Revision             | Proof                                                                                           | Принято                               |
| ---: | -------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------- |
|    0 | —                    | —                                                                                               | —                                     |
|    1 | `1aad776`, `866e3fe` | [Этап 1](05-phase-1-auth.md#пруфы-завершения-этапа)                                             | частично; production gates открыты    |
|    2 | `43b0323`…`3b5a4e8`  | [Этап 2](06-phase-2-content.md#пруфы-завершения-этапа)                                          | Browser path принят; этап открыт      |
|    3 | `d70b0d9`…`f787a64`  | [Этап 3](07-phase-3-student-reading.md#пруфы-завершения-этапа)                                  | Phase 3A–3H приняты; visual открыт    |
|    4 | `6409191`…`0fde237`  | [Phase 4A–4G proof](../../../pwa_tests/reports/phase4-test-submission-domain-and-repository.md) | функционально; visual открыт          |
|    5 | `5acecbb`…`38579a5`  | [Phase 5A–5D proof](../../../pwa_tests/reports/phase5-written-attachment-mutations.md)          | частично; server text/photo edit vertical принят |
|    6 | —                    | —                                                                                               | —                                     |
|    7 | —                    | —                                                                                               | —                                     |
|    8 | —                    | —                                                                                               | —                                     |
|    9 | —                    | —                                                                                               | —                                     |
|   10 | —                    | —                                                                                               | —                                     |
|   11 | —                    | —                                                                                               | —                                     |
