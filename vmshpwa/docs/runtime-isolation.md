# Runtime isolation и команды

Human и agent runtime могут работать одновременно и не делят изменяемое состояние.

| Ресурс      | Human                    | Agent                      | E2E                      |
| ----------- | ------------------------ | -------------------------- | ------------------------ |
| Student     | 5173                     | 5273                       | 5373                     |
| Family      | 5174                     | 5274                       | 5374                     |
| Staff       | 5175                     | 5275                       | 5375                     |
| Storybook   | 6006                     | 6106                       | —                        |
| API         | 8180                     | 8280                       | 8380                     |
| SQLite      | `db/vmshpwa_dev.sqlite3` | `db/vmshpwa_agent.sqlite3` | `db/vmshpwa_e2e.sqlite3` |
| instance    | `human`                  | `agent`                    | `e2e`                    |
| NATS prefix | `vmshpwa_human`          | `vmshpwa_agent`            | `vmshpwa_e2e`            |
| media       | `.runtime/vmshpwa/human` | `.runtime/vmshpwa/agent`   | `.runtime/vmshpwa/e2e`   |

Legacy aiohttp остаётся на 8179. Новые команды его не занимают.

## Запуск

- `make pwa-dev` — API, три приложения и Storybook для человека;
- `make pwa-agent-dev` — параллельный комплект агента;
- отдельные цели `pwa-api`, `pwa-student`, `pwa-family`, `pwa-staff`, `pwa-storybook` и их `pwa-agent-*` аналоги;
- `make pwa-seed` / `make pwa-agent-seed` — миграции и детерминированная prototype-fixture;
- `make pwa-format`, `pwa-lint`, `pwa-typecheck`, `pwa-test`, `pwa-storybook-test`, `pwa-build`;
- `make pwa-e2e`, `pwa-visual`, `pwa-visual-update`;
- `make telegram-history-test` — отдельная историческая регрессия Telegram.

Frontend runtime получает адрес API через `VMSH_API_ORIGIN`; это не встраивается в production bundle. PWA IndexedDB называется по audience и instance, service worker ограничен audience scope. Test credentials и browser context создаются независимо для каждого запуска.

Обычные agent/E2E profiles используют filesystem media adapter и не читают `creds_test`/`creds_prod`. Ручной local S3 integration profile может allowlist-ом прочитать `s3_url`, `s3_bucket_name`, `s3_access_key`, `s3_secret_key` из `creds_test/vmsh_bot_config_test.json` и работает только в выделенном test bucket/prefix. Production читает те же поля из production config; смешение test/prod key или prefix является startup error.

## Запреты

Agent никогда не запускает human-цели, Telegram polling, Google loaders и не использует реальные credentials. E2E не применяет MSW и поднимает настоящий aiohttp с seeded SQLite. Production build аварийно завершается, если включён `VITE_ENABLE_MSW=true` или `VITE_PROTOTYPE=true`.
