# Runtime isolation и команды

Human и agent runtime могут работать одновременно и не делят изменяемое состояние.

| Ресурс    | Human                                    | Agent                                    | E2E                                   |
| --------- | ---------------------------------------- | ---------------------------------------- | ------------------------------------- |
| Student   | `127.0.0.1:5173/student/*`               | `127.0.0.1:5273/student/*`               | `127.0.0.1:5380/student/*`            |
| Family    | `127.0.0.1:5174/family/*`                | `127.0.0.1:5274/family/*`                | `127.0.0.1:5380/family/*`             |
| Staff     | `127.0.0.1:5175/staff/*`                 | `127.0.0.1:5275/staff/*`                 | `127.0.0.1:5380/staff/*`              |
| Storybook | 6006                                     | 6106                                     | —                                     |
| gateway   | —                                        | —                                        | 5380, единственный browser origin     |
| API       | 8180                                     | 8280                                     | 8380, доступен браузеру через gateway |
| SQLite    | `db/vmshpwa_dev.sqlite3`                 | `db/vmshpwa_agent.sqlite3`               | `db/vmshpwa_e2e.sqlite3`              |
| instance  | `human`                                  | `agent`                                  | `e2e`                                 |
| NATS      | `127.0.0.1:4222`, prefix `vmshpwa_human` | `127.0.0.1:4222`, prefix `vmshpwa_agent` | отключён                              |
| media     | `.runtime/vmshpwa/human`                 | `.runtime/vmshpwa/agent`                 | `.runtime/vmshpwa/e2e`                |

Legacy aiohttp остаётся на 8179. Новые команды его не занимают.

## Запуск

- `make pwa-dev` — API, три приложения и Storybook для человека;
- `make pwa-agent-dev` — параллельный комплект агента;
- отдельные цели `pwa-api`, `pwa-student`, `pwa-family`, `pwa-staff`, `pwa-storybook` и их `pwa-agent-*` аналоги;
- `make pwa-migrate` / `make pwa-agent-migrate` — явное применение yoyo migrations и включение WAL до запуска API;
- `make pwa-seed` / `make pwa-agent-seed` — явные миграции и детерминированная prototype-fixture;
- `make pwa-toolchain-check` / `make pwa-agent-toolchain-check` — redacted capability/version preflight; соответствующие `*-toolchain-smoke` реально строят synthetic TikZ→SVG и raster→WebP во временной папке;
- `make pwa-schema-check` — воспроизводит schema-only artifacts из migrations; `pwa-schema-live-check` безопасно сверяет только структуру `db/vmsh.db`, а update-цели требуют отдельного явного запуска;
- `make pwa-format`, `pwa-lint`, `pwa-typecheck`, `pwa-test`, `pwa-storybook-test`, `pwa-build`;
- `make pwa-e2e` — полный production E2E; `make pwa-e2e-runtime` — только
  runtime/isolation; `make pwa-e2e-functional` — все non-visual сценарии;
- `make pwa-visual`, `pwa-visual-update` — visual gate и отдельно разрешённое
  обновление снимков;
- `make telegram-history-test` — отдельная историческая регрессия Telegram.

`VMSH_API_ORIGIN` настраивает только proxy локального Vite dev server и
не встраивается в production bundle. Frontend всегда обращается к относительным
`/{audience}/api/v1/*` и `/{audience}/ws`. Test credentials и browser context
создаются независимо для каждого запуска.

## Runtime contract и browser state

Backend является владельцем `instance`. При composition он принимает только
канонический lowercase ASCII token длиной 1–64 символа: первый и последний
символ — `[a-z0-9]`, внутри также разрешены `.`, `_` и `-`. Значение без
нормализации возвращается из `/{audience}/api/v1/runtime`; небезопасный token
останавливает startup, а не создаёт частично работающий browser namespace.

Каждое приложение монтирует [`RuntimeBootstrap`](../packages/app-shell/src/runtime-bootstrap.tsx)
до TanStack Router. Wire payload содержит обязательный `contractVersion: 1` и
проходит audience-specific Zod-проверку точных `appBase`, `apiBase` и
`websocketPath`. Неизвестная версия, cross-audience или malformed payload не
открывает shell. Для rolling deployment дополнительные поля v1 допустимы и
игнорируются старым клиентом; изменение обязательной семантики требует новой
версии контракта. Запрос имеет десятисекундный timeout, после ошибки пользователь
видит спокойный русский state с retry и, если сервер вернул валидный error
envelope, correlation ID. Python builders и TypeScript schemas сверяются с
общими versioned JSON fixtures в
[`packages/contracts/fixtures`](../packages/contracts/fixtures), включая
ошибку realtime invalid JSON.

Все HTTP-ответы PWA API, включая exact `/{audience}/api`, нормальные ответы и
пересобранные aiohttp exceptions, получают authoritative `no-store`, request ID
и security headers. Стабильные коды доменных ошибок задаёт `PwaApiError`, а
разрешённые end-to-end exception headers сохраняются без переноса исходных
body/cache headers.

Realtime state создаётся атомарно вместе с app. Per-audience lock сериализует
cursor allocation и рассылку внутри аудитории, не блокируя другие аудитории;
invalid WebSocket JSON возвращает versioned recoverable error event. Если
клиент отменяет upgrade у E2E gateway, уже открытый upstream WebSocket явно
закрывается.

Канонический префикс изменяемого browser state:

```text
vmsh-179:v1:<student|family|staff>:<instance>
```

- theme хранится как `<namespace>:theme`;
- Dexie database Student и Family называется ровно этим namespace;
- Staff не создаёт offline database;
- Student/Family открывают Dexie до protected router. Blocked upgrade,
  десятисекундный timeout, rejected open и неожиданное закрытие переводят
  lifecycle в retryable error state. Ошибка IndexedDB не подменяется
  online-only режимом, который мог бы обещать сохранение черновика, когда оно
  не работает;
- отказ браузера в доступе к `localStorage` не ломает shell: theme остаётся
  in-memory на текущей странице. Это допустимо только для косметической
  настройки; пользовательская работа хранится через явный Dexie gate.

Версия browser namespace меняется только при миграции локальных данных и не
связана автоматически с версией HTTP fixtures. Реальные IndexedDB records, а не
только вычисленные строки, проверяются между `student:agent`, `student:human` и
`family:agent` в
[`packages/offline/src/database.test.tsx`](../packages/offline/src/database.test.tsx).

Это ownership/collision convention, а не security boundary внутри одного
origin. Любой уже исполняющийся same-origin JavaScript технически может
перечислить соседние `localStorage`, IndexedDB и Cache Storage. Защиту данных
между ролями обеспечивают server authorization, отдельные audience sessions,
HttpOnly cookies/CSP и отсутствие чувствительных данных в общих public assets;
их полный proof относится к этапу 1. Namespace предотвращает случайное
смешение состояния корректными приложениями и runtime-профилями.

Student и Family имеют отдельные service-worker scope `/student/` и `/family/`;
Staff service worker не регистрирует. Workbox caches получают разные prefix
`vmsh-179-student` и `vmsh-179-family`; suffix сохраняет полный
`self.registration.scope` и добавляет migration version `v1`. Благодаря scope
[`cleanupOutdatedCaches()`](https://developer.chrome.com/docs/workbox/modules/workbox-precaching/#cleanupoutdatedcaches)
может распознать собственный старый precache; E2E создаёт синтетический `v0` и
доказывает его удаление после активации `v1`. Recent-media cache также
audience-specific. Это явная one-origin граница: официальный Workbox contract
формирует имена как `<prefix>-<cache-id>-<suffix>` и рекомендует разные prefix
для нескольких приложений на одном origin
([`workbox-core.setCacheNameDetails`](https://developer.chrome.com/docs/workbox/modules/workbox-core/#setcachenamedetails)).
API и auth URL не попадают в precache/runtime caches.

`PwaUpdateController` живёт снаружи `RuntimeBootstrap` и Dexie provider.
Поэтому несовместимый runtime payload или ошибка локальной базы блокируют
protected UI, но не регистрацию worker и не recovery через prompt обновления.

## Production-like E2E origin

`make pwa-e2e`, `pwa-e2e-runtime`, `pwa-e2e-functional` и visual-команды идут
через [`scripts/e2e_runner.py`](../scripts/e2e_runner.py). Один
cross-process `flock` охватывает build и Playwright; конкурентный запуск
завершается до изменения общих `dist`, портов или seeded SQLite. Runner сначала
собирает все три production bundles. Затем
[`playwright.config.ts`](../playwright.config.ts) поднимает настоящий aiohttp на
8380 и test-only [`scripts/e2e_gateway.py`](../scripts/e2e_gateway.py) на 5380.
Gateway:

- отдаёт три `dist` под их production base paths на одном origin;
- раньше SPA fallback маршрутизирует точные API и WebSocket paths;
- не превращает отсутствующий API, malformed WS path или отсутствующий asset в
  `index.html`;
- принудительно делает proxy responses `no-store`, не хранит upstream cookies
  и отклоняет path traversal, symlink самого dist root и escaping symlinks;
- запускается только с `VMSH_RUNTIME_PROFILE=pwa-e2e`, literal loopback bind и
  literal loopback upstream.

Локальные capability-gated test routes меняют только байты выдаваемого built
`sw.js` и ответ runtime: они позволяют доказать настоящую цепочку несовместимый
runtime → доступный update prompt → waiting worker → `SKIP_WAITING` → новый
controller без второго frontend и без production backdoor. Control token
эфемерен, действует только на loopback и может присутствовать в сохранённом
Playwright trace, поэтому не является секретом продукта и не даёт доступа к
API.

Playwright выполняет функциональные проверки во всех трёх проектах. Его
специальные Service Worker events/network interception официально доступны
только Chromium, но наш lifecycle proof использует browser-native
`navigator.serviceWorker` и Cache Storage API и сейчас обязателен и зелёный в
Chromium, WebKit и Firefox. Capability-based skip допустим только при реальном
отсутствии API и остаётся видимым в результате
([Playwright Service Workers](https://playwright.dev/docs/service-workers)).

Production build guard отдельно запускает каждый Vite app с
`VITE_ENABLE_MSW=true` и `VITE_PROTOTYPE=true` и требует отказа до очистки или
создания output directory. Общий config-time guard использует Vite `loadEnv`,
поэтому unit test проверяет controlled `.env.production`, а subprocess test —
process environment для каждого приложения. Это соответствует
[официальному порядку загрузки env в Vite config](https://vite.dev/config/#using-environment-variables-in-config).

## Известное ограничение этапа 0

Runtime bootstrap пока требует сеть при холодном открытии: валидированный
runtime contract не сохраняется для offline boot. Уже открытый service worker и
Dexie namespace не дают права угадывать audience/instance при следующем cold
start. Versioned cached bootstrap с expiry/revocation semantics относится к
этапу 3. До его реализации E2E доказывает offline storage isolation и PWA
lifecycle, но не заявляет cold offline reading как готовый сценарий.

Phase-0 gateway моделирует один browser origin, но ещё не production trusted
reverse proxy: upstream видит `Host` API-порта 8380, а браузер отправляет
`Origin` gateway 5380. До auth/CSRF gate этапа 1 нужен явный public-origin и
trusted-proxy contract, включая отказ от поддельных `Forwarded` и
`X-Forwarded-*` headers. Это не блокирует текущую transport/storage проверку,
но её нельзя использовать как доказательство session/CSRF policy.

Gateway unit/E2E доказывают server-side fallback ordering, а browser scenario
повторяет exact `/api`, malformed `/ws/...`, `/assets`, отсутствующий root
static и PDF как реальные page navigations после получения активного
controller. Manifest и icons имеют отдельную request-based install-boundary
проверку, поскольку browser navigation может открыть download UI. Поэтому
`NavigationRoute` и gateway проверяются совместно, а не только через
`APIRequestContext`, который обходит Service Worker.

Обычный aiohttp startup миграции не применяет. Он только сверяет IDs/hash всех migrations и persistent WAL mode; при пустой, устаревшей или более новой схеме процесс завершается с указанием сначала выполнить maintenance-команду. Playwright перед aiohttp + one-origin gateway запускает изолированный seed, а Python API tests получают отдельную временную SQLite на каждый pytest worker и не читают постоянную E2E-БД.

Seed строит sibling temporary database, валидирует и только затем атомарно заменяет target. Существующий `-wal` нельзя удалять вручную: это часть состояния SQLite. Если после корректного закрытия процесса остались `-wal/-shm`, seed открывает target через SQLite, выполняет zero-wait `wal_checkpoint(TRUNCATE)` и закрывает его; активная блокировка или неубранный sidecar приводят к отказу без замены. Это следует официальным правилам [SQLite WAL file](https://www.sqlite.org/wal.html#the_wal_file) и [checkpoint modes](https://www.sqlite.org/pragma.html#pragma_wal_checkpoint).

Каждый PWA worker после Gunicorn fork, но до проверки схемы берёт shared advisory lock на стабильном файле `.DATABASE.vmshpwa-lifecycle.lock` рядом с SQLite. aiohttp cleanup context держит его не только во время работы, но и до окончания `on_shutdown` и draining активных запросов. `pwa-migrate` и seed берут exclusive lock до чтения sidecars и освобождают только после завершения миграции либо атомарной замены и `fsync`. Занятый lock завершает команду сразу с понятной ошибкой: обслуживание не ждёт скрытно, а runtime не стартует посреди него. Сам lock-файл никогда не удаляется и не заменяется; DB symlink/hardlink aliases запрещены. Протокол требует локальную файловую систему с рабочим Unix/BSD `flock` (macOS dev, Linux production) и одну service identity для runtime/maintenance. Он закрывает опасную для WAL гонку с переименованием открытой БД и описан вместе с первичными источниками в [`adr/0002-pwa-sqlite-concurrency-and-migrations.md`](../../adr/0002-pwa-sqlite-concurrency-and-migrations.md).

Maintenance-entrypoints работают fail-closed: до импорта общего legacy config они требуют явный `VMSH_RUNTIME_PROFILE=pwa-*`, а после импорта проверяют непустые instance и DB path. Произвольного `--database` у команд нет; неизвестный аргумент является ошибкой, а не молча игнорируемой подсказкой. Так опечатка не может незаметно переключить команду на legacy test DB и запустить загрузку Telegram/Google-настроек. Выбор файла всегда делается целиком проверенным Make-профилем.

Обычные agent/E2E profiles используют filesystem media adapter и не читают `creds_test`/`creds_prod`. Ручной local S3 integration profile может allowlist-ом прочитать `s3_url`, `s3_bucket_name`, `s3_access_key`, `s3_secret_key` из `creds_test/vmsh_bot_config_test.json` и работает только в выделенном test bucket/prefix. Production читает те же поля из production config; смешение test/prod key или prefix является startup error.

## Запреты

Agent никогда не запускает human-цели, Telegram polling, Google loaders и не использует реальные credentials. E2E не применяет MSW и поднимает настоящий aiohttp с seeded SQLite. Production build аварийно завершается, если включён `VITE_ENABLE_MSW=true` или `VITE_PROTOTYPE=true`.
