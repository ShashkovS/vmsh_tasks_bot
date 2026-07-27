# Runtime isolation и команды

Human и agent runtime могут работать одновременно и не делят изменяемое состояние.

| Ресурс    | Human                                    | Agent                                    | E2E                      |
| --------- | ---------------------------------------- | ---------------------------------------- | ------------------------ |
| Student   | 5173                                     | 5273                                     | 5373                     |
| Family    | 5174                                     | 5274                                     | 5374                     |
| Staff     | 5175                                     | 5275                                     | 5375                     |
| Storybook | 6006                                     | 6106                                     | —                        |
| API       | 8180                                     | 8280                                     | 8380                     |
| SQLite    | `db/vmshpwa_dev.sqlite3`                 | `db/vmshpwa_agent.sqlite3`               | `db/vmshpwa_e2e.sqlite3` |
| instance  | `human`                                  | `agent`                                  | `e2e`                    |
| NATS      | `127.0.0.1:4222`, prefix `vmshpwa_human` | `127.0.0.1:4222`, prefix `vmshpwa_agent` | отключён                 |
| media     | `.runtime/vmshpwa/human`                 | `.runtime/vmshpwa/agent`                 | `.runtime/vmshpwa/e2e`   |

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
- `make pwa-e2e`, `pwa-visual`, `pwa-visual-update`;
- `make telegram-history-test` — отдельная историческая регрессия Telegram.

Frontend runtime получает адрес API через `VMSH_API_ORIGIN`; это не встраивается в production bundle. PWA IndexedDB называется по audience и instance, service worker ограничен audience scope. Test credentials и browser context создаются независимо для каждого запуска.

Обычный aiohttp startup миграции не применяет. Он только сверяет IDs/hash всех migrations и persistent WAL mode; при пустой, устаревшей или более новой схеме процесс завершается с указанием сначала выполнить maintenance-команду. Playwright перед своим production-preview сервером запускает изолированный seed, а Python API tests получают отдельную временную SQLite на каждый pytest worker и не читают постоянную E2E-БД.

Seed строит sibling temporary database, валидирует и только затем атомарно заменяет target. Существующий `-wal` нельзя удалять вручную: это часть состояния SQLite. Если после корректного закрытия процесса остались `-wal/-shm`, seed открывает target через SQLite, выполняет zero-wait `wal_checkpoint(TRUNCATE)` и закрывает его; активная блокировка или неубранный sidecar приводят к отказу без замены. Это следует официальным правилам [SQLite WAL file](https://www.sqlite.org/wal.html#the_wal_file) и [checkpoint modes](https://www.sqlite.org/pragma.html#pragma_wal_checkpoint).

Каждый PWA worker после Gunicorn fork, но до проверки схемы берёт shared advisory lock на стабильном файле `.DATABASE.vmshpwa-lifecycle.lock` рядом с SQLite. aiohttp cleanup context держит его не только во время работы, но и до окончания `on_shutdown` и draining активных запросов. `pwa-migrate` и seed берут exclusive lock до чтения sidecars и освобождают только после завершения миграции либо атомарной замены и `fsync`. Занятый lock завершает команду сразу с понятной ошибкой: обслуживание не ждёт скрытно, а runtime не стартует посреди него. Сам lock-файл никогда не удаляется и не заменяется; DB symlink/hardlink aliases запрещены. Протокол требует локальную файловую систему с рабочим Unix/BSD `flock` (macOS dev, Linux production) и одну service identity для runtime/maintenance. Он закрывает опасную для WAL гонку с переименованием открытой БД и описан вместе с первичными источниками в [`adr/0002-pwa-sqlite-concurrency-and-migrations.md`](../../adr/0002-pwa-sqlite-concurrency-and-migrations.md).

Maintenance-entrypoints работают fail-closed: до импорта общего legacy config они требуют явный `VMSH_RUNTIME_PROFILE=pwa-*`, а после импорта проверяют непустые instance и DB path. Произвольного `--database` у команд нет; неизвестный аргумент является ошибкой, а не молча игнорируемой подсказкой. Так опечатка не может незаметно переключить команду на legacy test DB и запустить загрузку Telegram/Google-настроек. Выбор файла всегда делается целиком проверенным Make-профилем.

Обычные agent/E2E profiles используют filesystem media adapter и не читают `creds_test`/`creds_prod`. Ручной local S3 integration profile может allowlist-ом прочитать `s3_url`, `s3_bucket_name`, `s3_access_key`, `s3_secret_key` из `creds_test/vmsh_bot_config_test.json` и работает только в выделенном test bucket/prefix. Production читает те же поля из production config; смешение test/prod key или prefix является startup error.

## Запреты

Agent никогда не запускает human-цели, Telegram polling, Google loaders и не использует реальные credentials. E2E не применяет MSW и поднимает настоящий aiohttp с seeded SQLite. Production build аварийно завершается, если включён `VITE_ENABLE_MSW=true` или `VITE_PROTOTYPE=true`.
