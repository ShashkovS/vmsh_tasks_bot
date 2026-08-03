# Стратегия тестирования

## Пирамида

1. Vitest: Zod contracts, query keys, runtime configuration, чистые преобразования, Dexie/outbox и deadline logic.
2. React Testing Library + user-event: редкие изолированные случаи, где DOM integration невозможно надёжно выразить story.
3. Storybook + addon-vitest browser mode: primitives, product components, theme/level/density matrices, loading/empty/error/offline states и interaction tests.
4. Playwright: реальные страницы и aiohttp, base paths/history fallback, runtime API, WebSocket/reconnect, PWA lifecycle, audience isolation и визуальные снимки.
5. Отдельная pytest-регрессия исторических Telegram-сценариев.

## Правила окружения

Unit и Storybook используют MSW 2. Main E2E никогда не использует MSW: Playwright поднимает профиль `pwa-e2e` с отдельной SQLite, media root и NATS prefix. Google и Telegram network calls в новых unit/E2E запрещены. Production build падает при включённом prototype MSW.

`make telegram-history-test` запускает только исторические handler-сценарии с `RecordingBot`, token-shaped заведомо фиктивным значением и без загрузки Telegram/Google credentials. Этот профиль не запускает polling/webhook и не является способом тестировать новый PWA API.

E2E выполняется в Chromium, WebKit и Firefox. Критические mobile Student flows дополнительно получают device projects при появлении реальных submission endpoints. iOS baseline — 16.4, Android — 10. Перед первым production-выпуском обязательна ручная проверка на доступных реальных Android-устройствах; iPhone проверяется по возможности и не блокирует выпуск при отсутствии устройства.

Основной E2E идёт через lock-aware
[`scripts/e2e_runner.py`](../scripts/e2e_runner.py): один `flock` охватывает
production build и Playwright и не даёт двум suite одновременно менять общие
`dist`, порты и seeded SQLite. `make pwa-e2e-runtime` запускает только
runtime/isolation spec, `make pwa-e2e-auth` и `make pwa-e2e-realtime` —
focused auth/realtime gates, `make pwa-e2e-functional` — весь non-visual набор,
`make pwa-e2e` — полный suite. Runner сначала собирает все три production
bundles с очищенным browser-build environment: все унаследованные `VITE_*`
удаляются, а полный текущий набор разрешённых ключей получает только
безопасные E2E-значения (`Sentry` и внешний media origin отключены,
MSW/prototype false). Это также перекрывает одноимённые значения из локальных
Vite `.env` благодаря приоритету process environment. Затем runner запускает
настоящий aiohttp и test-only one-origin gateway
[`scripts/e2e_gateway.py`](../scripts/e2e_gateway.py). Gateway отдаёт готовые
`dist` по `/student/*`, `/family/*`, `/staff/*` на
`http://127.0.0.1:5380` и проксирует точные audience API/WS paths на isolated
API 8380. Три независимых `vite preview` origin больше не используются: они не
моделируют production cookie paths, service-worker scopes, Cache Storage,
browser storage и history fallback одного host. Functional, visual, route
splitting, manifests и service-worker проверки видят production CSS/chunks, а
не dev/HMR-поведение. Deploy smoke остаётся отдельным коротким контролем уже
разложенных сервером assets. MSW не используется ни в одном E2E-режиме.

Gateway принимает только literal loopback bind/upstream и
`VMSH_RUNTIME_PROFILE=pwa-e2e`. Он не сохраняет upstream cookies, форсирует
`no-store` для API, отклоняет symlink самого dist root и escaping static paths и
обслуживает SPA fallback только после API/WS/asset boundaries. Эфемерные local
capability routes делают built `sw.js` byte-different и runtime несовместимым,
чтобы проверить update recovery даже при закрытом protected shell; это не
product endpoint и не production mock-auth.

Server-side fallback test через `APIRequestContext` недостаточен для PWA.
Поэтому browser test сначала получает активный worker, затем выполняет
настоящие page navigations к exact `/api`, malformed `/ws/...`, `/assets`,
missing root static и PDF. Manifest/icons проверяются отдельным request-based
install-boundary сценарием, поскольку browser navigation может инициировать
download UI. Так совместно проверяются gateway и `NavigationRoute` denylist:
worker не может скрыть ошибку gateway за app shell.

Все browser-facing E2E specs импортируют auto-fixture
[`e2e/fixtures.ts`](../e2e/fixtures.ts). HTTP(S) и WebSocket соединения
разрешены только к literal `127.0.0.1:5380`; `localhost`, другие loopback-порты
и внешние origins блокируются до сети и считаются ошибкой теста. API 8380
остаётся разрешён только server-side gateway/readiness процессам, но не
product page. Исполняемый probe с `.invalid` HTTP и WebSocket URL доказывает
работу этого запрета в Chromium, WebKit и Firefox. Совместно с очищенным build
environment это не позволяет случайно отправить E2E telemetry в реальный
Sentry или загрузить media из внешнего бакета.

Playwright запускает разные spec-файлы параллельно даже при
`fullyParallel: false` ([официальная модель](https://playwright.dev/docs/test-parallel)).
Поэтому конфигурация держит ровно три общих workers и не более одного worker в
каждом browser project: Chromium, WebKit и Firefox идут одновременно, но один
движок не создаёт несколько service-worker/visibility tabs против общей
настоящей SQLite. Project-level `workers` поддерживается с Playwright 1.52
([release notes](https://playwright.dev/docs/release-notes#version-152)). В CI
retry сохраняет trace для диагностики, однако `failOnFlakyTests: true` делает
любой такой retry ошибкой gate; flaky нельзя выдать за зелёный результат.

Контрольный production-build functional run 2 августа 2026 года: **228 total,
216 passed, 12 intentional skips, 0 unexpected, 0 flaky**, три фактических
workers, browser duration 208,01 с. Сводка и оставшиеся внешние/visual gates:
[`phase11-production-e2e.md`](../../pwa_tests/reports/phase11-production-e2e.md).

Playwright-specific Service Worker events и network interception официально
доступны только в Chromium. Наш lifecycle proof не зависит от них: он вызывает
browser-native `navigator.serviceWorker`/Cache Storage API и сейчас обязателен и
зелёный в Chromium, WebKit и Firefox. Capability-based skip разрешён только
если конкретный engine действительно не предоставляет нужный browser API, и
остаётся видимым в результате. При активации worker тест ждёт browser
state/controller, а не только событие регистрации — это соответствует
[официальному руководству Playwright](https://playwright.dev/docs/service-workers).
Update scenario также создаёт устаревший audience-owned precache `v0` и после
активации `v1` проверяет его удаление. Scope остаётся частью Workbox suffix,
поскольку именно по нему
[`cleanupOutdatedCaches()`](https://developer.chrome.com/docs/workbox/modules/workbox-precaching/#cleanupoutdatedcaches)
распознаёт принадлежащие текущей регистрации precaches.

Перед стартом настоящего aiohttp Playwright вызывает изолированный
seed/migration entrypoint. Сам server startup схему не меняет. Python PWA suite
создаёт мигрированную временную SQLite отдельно в каждом pytest worker; поэтому
`make pwa-test` безопасно использует восемь xdist-процессов. Полный Python gate
`make python-test` запускает legacy `tests` и PWA `pwa_tests` двумя
последовательными pytest-командами: смешивать их при collection нельзя из-за
разных import-time runtime profiles. Каждый набор внутри команды использует
восемь workers. Контрольный прогон 2 августа 2026 года: legacy `121 passed, 1
skipped` за 12,87 с; PWA `1542 passed, 5 skipped` за 69,55 с; общий wall time
85,53 с. Подробный proof:
[`python-xdist-gate-2026-08-02.md`](../../pwa_tests/reports/python-xdist-gate-2026-08-02.md).
Тесты migration lifecycle дополнительно
проверяют пустую/устаревшую/будущую схему, hash drift, WAL, конкурирующих writers
и rollback после исключения. Guarded live-smoke targets остаются
последовательными: они управляют общими внешними ресурсами и не входят в
hermetic suite.

## Phase 1: browser-auth proof

Команда `make pwa-e2e-auth` запускает только
[`e2e/authentication.spec.ts`](../e2e/authentication.spec.ts), но сохраняет весь
production-like контур выше: сначала production build трёх приложений, затем
one-origin gateway, настоящий aiohttp и отдельная seeded SQLite. Общие
synthetic credentials читаются из
[`auth-credentials-v1.json`](../../pwa_tests/fixtures/auth-credentials-v1.json)
только seed/test helpers; product entry и production bundle этот fixture не
импортируют.

Матрица обязательна в Chromium, WebKit и Firefox и проверяет:

- private deep-link → правильный audience login → исходные path/query/hash;
- Student, Family, Teacher и Admin login, authoritative `/auth/me` и reload;
- одинаковую безопасную ошибку неверных credentials без account enumeration;
- logout, точные cookie names/Path и одновременные независимые audience-сессии;
- anonymous/cross-audience `401`, точные browser Host/Origin и отклонение
  spoofed forwarding headers;
- смену access и refresh cookie при ротации без смены logical session ID;
- автоматический single-flight refresh и восстановление private shell после
  удаления только access-cookie;
- две вкладки одного audience после удаления access-cookie координируются через
  browser lock и вместе расходуют refresh cookie ровно один раз;
- отзыв одной device session при сохранении второй активной сессии.

Зафиксированный прогон 27 июля 2026 года: **60/60 PASS**. Focused frontend
auth/session suite после expiry/cross-tab hardening дал **31/31 PASS**. Повторный
полный gate текущего worktree: frontend unit **19 файлов / 162 PASS**, Python
PWA — **808 PASS / 1 intentional skip**, Storybook browser mode — **33 файла /
152 PASS**; lint/typecheck/production build зелёные.
MSW, Telegram и Google в этом контуре не используются.

Teacher→admin browser **API** `403` добавляется только с первым настоящим
capability-protected admin product endpoint (Phase 2/7/8/10). До этого UI
forbidden и permission/API matrix являются честным текущим proof; тестовый
production endpoint или mock-auth backdoor ради Playwright запрещены.

### Phase 1: product realtime client proof

`make pwa-e2e-realtime` собирает production bundles всех трёх приложений и
запускает focused часть
[`e2e/runtime-isolation.spec.ts`](../e2e/runtime-isolation.spec.ts) с настоящими
aiohttp, seeded SQLite и one-origin gateway. Тест наблюдает именно WebSocket,
созданный production `RealtimeProvider`, а не создаёт отдельный ручной клиент.
В Chromium, WebKit и Firefox проверяются exact audience path без credential,
первый `connected`, принудительный transport close, reconnect URL только с
cursor, `resync-required`, обязательный HTTP authority refetch и сохранение
private shell. Отдельный сценарий отзывает current session настоящим API,
доказывает закрытие сокета, переход на login и отсутствие reconnect loop.

Playwright `WebSocketRoute` нормализует server policy close `1008` в `1000` во
всех трёх движках. Поэтому точный wire code остаётся обязательным Python
aiohttp/unit proof, а browser test проверяет наблюдаемый close, HTTP authority
logout и отсутствие нового socket. Frontend state-machine unit suite отдельно
проверяет exact `1008`, fail-closed protocol, CONNECTING/handshake/pong timeouts,
offline/hidden, bounded backoff, invalidation coalescing, cursor-only URL,
StrictMode cleanup и tri-state authority: реальный `401` терминален, а
transient unavailable повторяется и восстанавливает reconnect. Зафиксированный
результат 27 июля 2026 года: Vitest **2
файла / 17 PASS**, Playwright **12/12 PASS**; snapshots не изменялись.

Полный `make pwa-e2e-runtime` того же worktree дал **65 PASS, 6 FAIL, 1
flaky**. Realtime, current-session revoke, audience-scoped theme storage и
IndexedDB isolation прошли во всех трёх движках. Все шесть failures относятся
к прежнему Student/Family PWA-update тесту: после применения byte-different
worker не наблюдается ожидаемый `framenavigated` в Chromium, WebKit и Firefox.
WebKit scope probe один раз прошёл только при retry. Этот результат остаётся
отдельным открытым service-worker gate; ради realtime-инкремента старые
проверки не ослаблялись и snapshots не обновлялись.

## Phase 2: authenticated content checkpoint

Revisions `1aad776`/`866e3fe` прошли общий gate 28 июля 2026 года:

- `make pwa-lint`, `make pwa-typecheck`, `make pwa-build` — PASS;
- `make pwa-test` — **218 TypeScript + 1028 Python PASS**, 3 skip, 1 warning;
- `make pwa-storybook-test` — **167 PASS** с addon-a11y `error`;
- `make pwa-schema-check` — **192 product objects PASS**;
- `make pwa-e2e-auth` — **60/60 PASS** в Chromium, WebKit и Firefox после
  production build.

Content backend tests используют реальный aiohttp application и отдельную
migrated SQLite: compile lease/retry, publication concurrency, readiness +
solution-cutoff gates, `0043` lesson-window audit, server-side bounded history
и server-authoritative timezone/DST conversion. Frontend unit/Storybook
проверяют reload resume, rollback только к `ready`, confirmations,
business-timezone schedule, два preview и audience update marker.

Отдельный `make pwa-e2e-content` в revision `3b5a4e8` закрывает обычный
production-build browser path upload→compile→match metadata→publish→Student
read→second revision→rollback: **3 PASS** в Chromium, WebKit и Firefox на
настоящих aiohttp/SQLite без MSW. Каждый project получает независимый mutable
group lesson через guarded E2E-only seed. Proof:
[`phase2-content-e2e.md`](../../pwa_tests/reports/phase2-content-e2e.md).

Этот Playwright flow пока не проходит missing-asset recovery. Его TikZ/SVG/
WebP/S3, authenticated HTTP и Staff states доказаны отдельными live/API/
Storybook suites. До принятия всего Phase 2 также нужны production
owner-reviewed parity/backfill и ручное visual approval. Snapshots не
обновлялись. Ранее закрытые proof:
[`phase2-content-api.md`](../../pwa_tests/reports/phase2-content-api.md) и
[`phase2-content-frontend.md`](../../pwa_tests/reports/phase2-content-frontend.md).

## Phase 3: Student course, lesson and home reads

Phase 3A проецирует course enrollment непосредственно из revalidated session,
Phase 3B добавляет опубликованный lesson list/detail, Phase 3C — единый home
snapshot и production страницу `/student/`, Phase 3D — cursor archive
`/student/tasks`. Реальный aiohttp/SQLite
suite проверяет `403` для недоступной группы, строгие query/cursor, отсутствие
урока до condition publication, появление после publication и полное исчезновение
после hide. Bounded list извлекает окно, три material slots и problem count одним
SQLite statement без per-lesson queries. Zod fixture отдельно фиксирует provenance,
обратный порядок и независимые `submissionClosesAt`/`solutionScheduledAt`.

Home выбирает последнее видимое занятие каждого active group одним SQLite
statement, а Zod запрещает duplicate course и lesson другой группы. Production
страница не использует prototype state и открывает exact `group_lesson`.

Зафиксированный результат 28 июля 2026: полный regression — **259 TypeScript +
1098 Python PASS**, Storybook browser mode — **180 PASS**; production-build
publish→home→course/group archive→URL-selected lesson→read→rollback — **3
PASS** в Chromium, WebKit и Firefox. Proof:
[`phase3-student-lessons-api.md`](../../pwa_tests/reports/phase3-student-lessons-api.md)
[`phase3-student-home.md`](../../pwa_tests/reports/phase3-student-home.md) и
[`phase3-student-task-archive.md`](../../pwa_tests/reports/phase3-student-task-archive.md).
Problem status projection, Dexie cache и offline navigation остаются следующими
gates.

## Runtime contract и browser isolation

Versioned fixtures в
[`packages/contracts/fixtures`](../packages/contracts/fixtures) являются общей
проверяемой границей, а не источником сгенерированных типов. TypeScript Zod
schemas парсят runtime/error fixtures; Python builders в
[`helpers/pwa/api_contracts.py`](../../helpers/pwa/api_contracts.py) собирают
точно те же payload. Обязательный `contractVersion: 1` отделён от browser
namespace version: неизвестная версия отклоняется, а дополнительные v1 fields
при rolling deployment игнорируются. Несовпадение audience, base paths,
instance grammar, fixture/contract version, HTTP error envelope или realtime
invalid-JSON envelope должно ломать contract tests до E2E.

Unit/DOM tests дополнительно доказывают:

- protected shell не монтируется до успешной audience-specific runtime
  validation;
- malformed/cross-audience/incompatible runtime fail-closed, десятисекундный
  timeout и retry не включают fallback configuration;
- theme key содержит полный `audience + instance` namespace;
- отказ `localStorage` оставляет shell и in-memory theme работоспособными;
- Student/Family действительно записывают разные IndexedDB, а Staff Dexie не
  создаёт;
- Dexie открывается до consumers; blocked upgrade, timeout, rejected open и
  unexpected close дают retryable error, а teardown закрывает точную базу;
- `PwaUpdateController` остаётся снаружи runtime/Dexie gates, поэтому waiting
  worker можно применить даже на startup error screen.
- owner-confirmed cold offline reading и предупреждение при logout проверяются
  вместе с implementation-default защитой общего устройства: только собственный
  `offline-unverified` cache до `sessionExpiresAt`, cleanup после подтверждения и
  запрет выдавать queued mutation за отправленную до auth refresh;

Storybook фиксирует startup состояния отдельными story IDs:

- `product-app-startup--runtime-loading`;
- `product-app-startup--runtime-rejected`;
- `product-app-startup--offline-storage-unavailable`.

Production build sentinel в
[`test_production_build_guard.py`](../../pwa_tests/test_production_build_guard.py)
запускает все три Vite apps с каждым запрещённым флагом и проверяет, что build
останавливается до изменения output. Unit test общего guard создаёт
контролируемый `.env.production` и проверяет Vite `loadEnv`, а subprocess test
проверяет process environment всех трёх приложений. One-origin transport,
dist-root/path safety и preservation/no-store response headers проверяются в
[`test_e2e_gateway.py`](../../pwa_tests/test_e2e_gateway.py), а browser proof —
в [`runtime-isolation.spec.ts`](../e2e/runtime-isolation.spec.ts). Поведение
runner lock/modes и browser-build environment allowlist отдельно фиксирует
[`test_e2e_runner.py`](../../pwa_tests/test_e2e_runner.py).

LocalStorage/Dexie/cache-name assertions доказывают ownership convention и
отсутствие случайных коллизий. Они не доказывают security isolation между
same-origin apps: такой JavaScript может перечислять соседние browser stores.
Authorization/session/CSP proof закрывается отдельно на этапе 1.

Ограничение этапа 0: `RuntimeBootstrap` пока делает обязательный network fetch
на cold start. Offline cached runtime bootstrap с expiry/revocation semantics
появляется на этапе 3; наличие precache и Dexie само по себе не считается
доказательством cold offline reading.

One-origin gateway этапа 0 не является моделью trusted reverse proxy: upstream
`Host` указывает на API 8380, browser `Origin` — на gateway 5380. Перед auth/CSRF
E2E этапа 1 вводится явный public-origin/proxy contract и negative cases для
spoofed `Forwarded`/`X-Forwarded-*`; текущий transport suite не засчитывается
как session/CSRF proof.

## Legacy characterization и golden corpus

Новые реализации не угадывают поведение Telegram-era кода по документации. Исполняемые тесты в `pwa_tests/domain/test_legacy_*.py` фиксируют все 23 `ANS_TYPE`, `strip()+fullmatch`, преобразования ответов, verdict weights/solved thresholds, реакции, 30-минутную аренду письменной очереди, SOS partition и старую title-based synonym projection. Тестовая БД после migrations сразу удаляет migration-carried `kv_logins`; исторические credential-shaped строки не становятся fixture и не попадают в вывод.

`make pwa-golden-check` сверяет все 54 файла `_vmsh_examples` с `vmshpwa/fixtures/content/golden-manifest.json`: SHA-256, encoding, роль и структурные счётчики. Manifest содержит только относительные пути и метаданные, без копий математического текста и персональных данных. `pwa-golden-update` разрешён только после просмотра изменившихся исходников; visual parity PWA/Telegram/PDF остаётся отдельным gate.

## Aggregate preflight реальных источников

Auth и workload baseline — локальные read-only проверки реальных артефактов, а не
hermetic unit-тесты. Поэтому они не входят неявно в `make pwa-test`:

- `make pwa-auth-preflight-check` повторно анализирует quiescent `db/vmsh.db` и
  сверяет только агрегатные `pwa_tests/reports/auth-preflight.{json,md}`;
- `make pwa-workload-profile-check` анализирует raw
  `logs/events.jsonl` + `events.jsonl.YYYY-MM-DD` и сверяет
  `pwa_tests/reports/workload-profile.{json,md}`;
- `*-update` перезаписывает отчёты только после просмотра aggregate diff;
- `make pwa-baseline-check` собирает эти read-only gates с golden/schema checks.

Auth-команда отказывается работать при `-wal`/`-shm`/`-journal`, symlink и
hard-link alias. Она открывает source fd с `O_NOFOLLOW_ANY`, где он доступен,
иначе с final-component `O_NOFOLLOW`; сравнивает `lstat`/`fstat`, читает и
SHA-256-хеширует exact bytes через тот же fd. Запросы идут к `:memory:` SQLite,
полученной через `Connection.deserialize(exact_bytes)`, с `query_only` и явной
read transaction: SQLite повторно path не открывает. Отсутствие/ошибка
`deserialize` — fail-closed; `immutable=1` не используется. После запроса source
fd и path проверяются повторно. Hard link запрещён, потому что journal sidecars
привязаны к имени файла. Команда не сериализует фамилии, token, login candidates,
chat/user IDs и неизвестные raw `users.type`: известные enum показываются
allowlist-строками, остальные только общим count. Collision и activation
остаются lower-bound до versioned login generator и явной классификации test
accounts.

Нормативные детали этого gate привязаны к primary documentation:

- [Python 3.14 `sqlite3.Connection.deserialize`](https://docs.python.org/3.14/library/sqlite3.html#sqlite3.Connection.deserialize)
  описывает замену database connection сериализованными bytes;
  preflight отдельно доказывает `query_only=1` и fail-closed при
  отсутствии или ошибке capability;
- [SQLite `sqlite3_deserialize`](https://sqlite.org/c3ref/deserialize.html)
  фиксирует in-memory semantics, возможность сборки без deserialize
  и ограничение для WAL-mode serialization. Preflight не меняет
  SQLite header bytes: WAL/journal sidecars и недесериализуемый
  snapshot отклоняются;
- [`os.O_NOFOLLOW_ANY`](https://docs.python.org/3.14/library/os.html#os.O_NOFOLLOW_ANY),
  [`os.O_NOFOLLOW`](https://docs.python.org/3.14/library/os.html#os.O_NOFOLLOW) и
  [`os.fstat`](https://docs.python.org/3.14/library/os.html#os.fstat) задают
  платформенные примитивы. `O_NOFOLLOW_ANY` используется только
  если его экспортирует platform; fallback защищает финальный
  component через `O_NOFOLLOW`, а identity доказывается сверкой
  `lstat`/`fstat`.

Workload-команда держит fd всех источников открытыми, читает и хеширует bytes
через эти же descriptors, затем повторяет `fstat`/hash и path identity check.
Применяется strongest available `O_NOFOLLOW_ANY`/`O_NOFOLLOW`; состав rotations
перепроверяется. Symlink, hard-link и duplicate-inode aliases, способные повторно
посчитать одни raw lines, отклоняются.
`logs/selected.jsonl` намеренно исключён: это PII-bearing filtered derivative,
который дублирует выбранные raw events и искажает нагрузку. Raw labels проходят
explicit allowlists; неизвестные значения становятся `other-*`, legacy numeric
actor labels преобразуются только явной таблицей, а missing actor учитывается
отдельно. Отчёт не содержит trace/flow, Telegram/user/chat IDs или payload
fragments.

Каждый report-файл создаётся во временном файле в том же каталоге, получает
`fsync`, заменяется через `os.replace`, после чего выполняется `fsync` каталога.
JSON и Markdown при этом не образуют общую транзакцию: прерванная между двумя
replace команда может оставить частичную пару, и именно поэтому следующий
`*-check` обязан сверять наличие и содержимое обоих файлов. Сообщение об ошибке
ведёт к `make ...-update` либо эквивалентному `python -m ... write`, а не к
неработоспособному запуску файла по path.

Minute-level workload numbers — только observed proxies. Дополняющий opt-in
two-process smoke проверяет server-side burst чуть выше наблюдаемого пика: 16
письменных сдач, 32 фотографии и 16 MiB representative file IO через одну WAL
SQLite. Для этого малого объёма user-visible exhausted `SQLITE_BUSY` не
допускается; внутренний bounded retry разрешён. Широкие smoke thresholds ловят
зависший writer и не являются production SLA. Реальные concurrent sessions и
глубина клиентского offline outbox по-прежнему требуют production telemetry.
Команда и результаты зафиксированы в
[`phase11-two-worker-runtime.md`](../../pwa_tests/reports/phase11-two-worker-runtime.md).

## Visual regression

Снимки страниц хранятся по browser project, делаются при фиксированном viewport, locale, timezone и reduced motion. Перед снимком тест ждёт видимый app shell и `document.fonts.ready`, чтобы локальная скорость загрузки шрифтов не становилась случайным diff. Сейчас reference environment — macOS машины владельца; Docker normalization откладывается. `pwa-visual-update` не является способом «починить» тест: перед обновлением человек или агент обязан открыть diff, проверить обе темы и убедиться, что изменение ожидаемо. Raw snapshots не меняются вместе с не относящимся к UI refactor.

Отдельный content visual gate сравнивает три реальных листка одного уровня во всех производных представлениях: PWA, Telegram-rich и PDF. Сравнение проверяет формулы, списки, таблицы и SVG/TikZ, а не только общий screenshot страницы.

## Accessibility

Storybook a11y violations имеют status `error`. Проверяются keyboard order, visible focus, accessible names, dialogs/focus trap, таблицы, zoom/reflow, forced colors where applicable и контраст WCAG 2.2 AA. Цвет никогда не является единственным носителем статуса.

Axe baseline действует для Student, Family и Staff. Для Staff обязательны labels, alt, валидный ARIA и контраст; отдельный полноценный keyboard-аналог специализированного gesture/DnD не является самостоятельным требованием. Текущий classroom planner использует обычные select/checkbox controls и поэтому остаётся работоспособным с клавиатуры без специального исключения.

## Definition of done компонента

Публичный общий компонент имеет типы, semantic tokens, stories основных состояний, interaction/a11y test при наличии поведения и краткое назначение. Изменение общего компонента сопровождается обновлением stories; app-specific logic не переносится в `packages/ui`.

Числовой coverage threshold сознательно не вводится. Покрываются contract boundaries, рискованные чистые функции, offline/idempotency logic и наблюдаемое поведение; бессодержательные тесты ради процента не добавляются.

## Начальная приёмка каркаса

- strict typecheck, ESLint, Prettier check, Vitest и Python PWA tests проходят;
- три production bundles собираются, Student/Family создают injectManifest workers;
- Storybook строится и browser tests запускаются;
- Playwright подтверждает shell/base/history/theme/runtime/WebSocket/PWA/audience separation во всех трёх движках;
- Telegram regression запускается отдельной командой.

Текущее доказательство именно runtime-isolation инкремента и честный список
ещё не выполненных gates находятся в
[`runtime-isolation-phase0.md`](../../pwa_tests/reports/runtime-isolation-phase0.md).

## Проверки миграции и интеграций

- Migration rehearsal выполняется на копии production SQLite вместе с её `-wal` и `-shm`, если они существуют. Исходный `db/vmsh.db` всегда открывается только для получения согласованной копии и никогда не анонимизируется/мигрируется на месте, даже если его можно восстановить из backup. В изолированной временной копии Faker заменяет все имена и фамилии до передачи тестам; отчёт не содержит исходных значений. Копия никогда не подключается к human/production runtime.
- Производительность и корректность импортов проверяются на production-size копии до применения миграции в production; фиксированный календарный график таких репетиций не нужен.
- Исторические Telegram-сценарии могут дополнительно прогоняться через отдельного тестового бота и тестовый канал. Это изолированный integration profile, не unit/E2E dependency.
- Live profile использует `@vmsh179devbot`; token берётся из `creds_test/vmsh_bot_config_test.json` и не выводится в command/report. Владелец подтвердил canonical Bot API `chat.id = -1003913815635` приватного `vmsh179devbot channel`; это pinned test-only значение, а не вычисление из Telegram UI ID. Bot имеет admin rights. Read-only bind сначала сверяет `getMe`, `getChat`, `getChatMember` и отсутствие public username, затем неизменно сохраняет identity в owner-only local SQLite `verified_telegram_test_binding`. Write-enabled smoke не принимает destination из environment, повторно проверяет pinned identity и читает `chat.id` только из этой SQLite. Целевая course/group `telegram_bindings` появляется с Phase 2 migration, а не подменяется test-only таблицей.
- Владелец разрешил opt-in smoke только в выделенных test resources: disposable S3 prefix `integration/<run-id>/` можно upload/read/public-GET/delete, а test bot может send/edit/delete synthetic messages в приватном test channel. Production bucket, credentials, recipients и учебные каналы запрещены. Classroom delivery hermetic suite использует RecordingBot и проверяет personal recipient resolution без реальных учеников; live smoke отправляет только synthetic test recipient payload.
- В test channel можно публиковать любые synthetic payloads в пределах Telegram limits: Phase 0 проверяет простой identity/send/edit/delete lifecycle; Phase 2 добавляет граничные Rich Message, formatting, math, tables, media и album cases уже для целевого renderer. Real student data/production media не используются. Owner-only runtime report хранит case/request marker, canonical chat ID, returned message IDs и delete/cleanup result при наличии, но не token.
- Live suite запускается явно и последовательно, чтобы тесты не боролись за edit/delete одних сообщений. Обычный `make telegram-history-test`, unit и E2E продолжают использовать RecordingBot без сети.
- Первый content acceptance corpus включает уроки 39, 40 и 41 сезона 2025–2026 для всех трёх уровней; три наиболее показательных листка одного уровня проходят ручное сравнение PWA/Telegram/PDF.
- Classroom unit/domain suite проверяет trim/NFKC/casefold, кириллические дубликаты, archive/restore, inherited layout, optimistic conflicts и свойства алгоритма: комнаты не смешивают группы, прежняя допустимая комната сохраняется, остальные распределяются по наименьшей фактической загрузке. Отдельно проверяются возраст до десятой года, nullable class/strength, aggregates без `NULL`, fuzzy normalization/edit distance и сортировка фамилия+имя.
- Classroom API suite проверяет Teacher `403`, stale `409`, запрет неполного/mismatched plan, атомарный batch move, обязательное подтверждение cross-group change, confirmed history и неизменность прошлых plans. Storybook покрывает catalog/layout/plan states, group markers и `очно/распределено`, 6/5/2 и плотный 15-room/~200-student fixtures, stale/reassigning/no-room, profile missing data, room averages возраста/класса/силы, search/history, bulk mode, local draft restore/conflict и mobile Staff. Отдельная проверка `mobile-staff-layout` требует эти поля в student rows и room headers.
- Classroom Playwright E2E в трёх браузерах создаёт `201` и `Актовый зал`, отклоняет `АКТОВЫЙ ЗАЛ`, подтверждает layout/plan, сверяет Student/Family, скрывает комнату, видит `reassigning`, пересчитывает и подтверждает новую версию. Дополнительно E2E восстанавливает несохранённые select после reload, выполняет bulk и подтверждённый cross-group move, находит фамилию с опечаткой и открывает историю. E2E использует production preview, настоящий aiohttp и seeded SQLite без MSW.
- Draft-persistence suite для Student/Staff проверяет reload/remount, PWA update prompt, account isolation, base-version conflict, explicit discard и очистку только после server receipt. Текст/UI-state проверяются через `localStorage`, blobs/outbox — через Dexie.
- Course runtime settings backend проверяется migration `up/down/up`, точным
  whitelist enum без `save_sol_mode`, admin-only доступом, default `v0` →
  stored `v1`, stale ETag, атомарным audit rollback и fail-closed чтением
  повреждённого JSON. Staff interaction и Telegram compatibility read являются
  отдельными последующими gates.
- Written-submission suite проверяет owner-confirmed teacher flow и
  implementation-default admin/post-review/preview: один текст, одна фотография
  и batch материалов получают audited target projection; исходные bytes/IDs,
  review evidence и verdict остаются неизменными, а actor вне scope получает
  отказ.
- Review suite обязательно проверяет owner-confirmed annotation core
  `pencil|eraser|text|arrow|rectangle`, rotation, normalized geometry и
  отсутствие zoom/pan в payload. Если реализация экспонирует optional highlight
  или palette, их schema/renderer также получают fixtures, но точное число
  цветов не является product gate. Combined synonym target выбирается по server receive
  time и детерминированному internal-ID tie-break, никогда по client time.
- Delivery suite сверяет owner-confirmed channel counters/partial lists и
  implementation-default explicit retry: новые attempts появляются только у
  failed recipient/channel pairs, а успешные PWA/Telegram доставки не
  повторяются.
- Student/Family progress tests запрещают self marker, percentile и словесное сравнение ребёнка с группой во всех chart/story fixtures.
- Multi-course unit/contract suite проверяет один active group и несколько allowed groups на enrollment; независимые schedule snapshots; course/group Telegram inheritance; merge/split без изменения concrete IDs; chronology provenance; combined review target и split status; synonym counting per group sheet; best-group tie-break; course-scoped progress/strength/notifications; inheritance classroom assignments для выбранных групп события.
- Storybook proof включает `Product/Courses`, Staff catalog/schedules/Telegram, synonym merge/timeline/review, multi-course classroom event, classroom delivery preview/changed-after-send, course-separated progress и соответствующие `Pages/Student`, `Pages/Family`, `Pages/Staff`. Visual snapshots не обновляются до owner review.
