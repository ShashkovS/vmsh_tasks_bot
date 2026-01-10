# Architecture

This document describes how VMSh Tasks Bot is structured and how the major components collaborate to deliver Telegram automation, teacher dashboards, and realtime game updates.

## High-level view
```mermaid
flowchart TD
    TelegramAPI[Telegram Bot API] -->|updates/webhooks| AiogramDispatcher
    AiogramDispatcher[aiogram 3 Dispatcher \n (apps/tg_bot.py)] -->|commands| Handlers[handlers/*]
    Handlers --> SQLite[(SQLite via db_methods)]
    GoogleSheets[Google Sheets] -->|synchronize| Loader[models/spreadsheets.py]
    Loader --> SQLite
    ZoomWebhook[Zoom Webhooks] --> ZoomParser[apps/zoom_events_parser.py]
    ZoomParser --> SQLite
    Users -->|HTTP| WebApps[aiohttp apps \n (results_app, game_web_app)]
    WebApps --> SQLite
    WebApps -->|publish| NATS[NATS broker]
    NATS --> WebApps
    NATS --> AiogramDispatcher
```

- **Telegram bot** (`apps/tg_bot.py` + `handlers/`) reacts to `/start`, `/sos`, and administrative commands, drives inline keyboards, and pushes progress notifications back to teachers.
- **Web apps** (`apps/game_web_app.py`, `apps/results_app.py`) render HTML dashboards for teachers and students. They authenticate via cookies backed by the `webtoken` table and use aiohttp routes to accept logins and AJAX requests.
- **Zoom integration** (`apps/zoom_events_parser.py`) receives meeting webhooks, normalizes participant names, and updates queues in SQLite so mentors can coordinate oral exams.
- **Shared services** (`helpers/config.py`, `helpers/nats_brocker.py`) provide configuration, logging, Google credentials loading, and inter-process messaging.

## Runtime composition
`main.py` bootstraps an aiohttp `web.Application`, registers start-up and shutdown hooks, and attaches every enabled module declared in the `apps` configuration setting. In development it also launches the Telegram bot in polling mode and exposes the aiohttp server on `http://127.0.0.1:8179`.

```python
# main.py (simplified)
app = web.Application()
app.on_startup.append(on_startup)
for module in apps.all_apps:
    module.configue(app)
```

The `apps/__init__.py` loader imports each sub-application on demand by inspecting `config.apps`. The default sample configuration enables the Telegram bot, the game dashboard, the results dashboard, and the Zoom webhook listener. Removing an entry from the comma-separated list disables its routes without changing code.

## Configuration lifecycle
`helpers/config.py` centralizes runtime settings:

1. Detects the environment via the `PROD` flag and selects the JSON file under `creds_test/` or `creds_prod/`.
2. Loads the Google service account JSON to verify credentials at startup.
3. Applies yoyo migrations before returning an initialized `Config` dataclass.
4. Configures logging and optionally enables Sentry when a DSN is present.

The configuration exposes runtime options such as rate limits, enabled apps, game mode toggles, and the NATS server URL used by realtime features.

## Data layer
SQLite is accessed through `db_methods/` modules, each wrapping CRUD operations for a functional area (users, problems, queues, game state, logs, etc.). `db_methods/db_abc.py` manages a single shared connection, applies migrations stored in `migrations/`, and offers a simple key-value store for auxiliary settings. `models/` provide thin objects over database rows (e.g. `models/user.py`, `models/problem.py`) and orchestrate synchronization with Google Sheets.

Migrations run automatically when `helpers.config` imports `db_methods`. Contributors creating new tables should add SQL scripts to `migrations/` via `yoyo new` and commit them alongside model changes.

## External integrations
- **Telegram**: The bot uses aiogram 3 to handle updates. In production `apps/tg_bot.setup_tgbot_webhook` configures Telegram webhooks via aiohttp routes served by gunicorn, while development uses long polling (`run_tg_bot_in_polling_mode`) alongside the aiohttp server.
- **Google Sheets**: `helpers/loader_from_google_spreadsheets.py` (used by `models/spreadsheets.py`) fetches problems, students, and teachers, then refreshes the database whenever it is empty or when `/ut`-style commands run.
- **NATS**: `helpers/nats_brocker.NATS` connects to the configured NATS cluster. When available, the game dashboard publishes map updates and player balances to topics derived from `config.config_name`. When NATS is unavailable the class falls back to in-process callbacks so tests can run without the broker.
- **Zoom**: `apps/zoom_events_parser.py` listens for `/zoomevents` POSTs, validates the Zoom challenge payload, and tracks participants entering or leaving waiting rooms to maintain the oral exam queue.

## Web applications
The aiohttp apps follow similar patterns:
- Decorate routes with `@routes.get`/`@routes.post`.
- Authenticate users via cookies stored in `Webtoken` records.
- Serve HTML templates loaded from `templates/` and respond with JSON for AJAX calls.
- Publish updates via NATS when the cooperative game state changes (map reveals, flag placements, treasure chests).

Websocket handlers maintain weak references to active connections and broadcast updates originating from NATS or user actions.

## Background jobs and shutdown
Both `main.py` and `apps/tg_bot.py` gather outstanding asyncio tasks during shutdown to avoid orphaned tasks. When running with webhooks, gunicorn is responsible for process lifecycle; in polling mode the bot spawns a background task to run the aiohttp server. The shutdown sequence closes database connections, bot sessions, and NATS subscriptions.

## Testing strategy
The `tests/` package uses pytest and synchronous sqlite databases stored under the paths supplied by the JSON configuration. Tests reset the `PROD` environment flag to cover both development and production branches of the configuration loader. No other services (NATS, Telegram) are required because helper classes fall back to local behavior when brokers are unavailable.

## Documentation and operations
- Operations manuals (`docs/deploy.md`, `docs/for_teacher.md`, `docs/for_admin.md`, `docs/settings.md`) remain in Russian but outline production practices, bot usage, and configuration tips.
- Newly introduced documents (README, CONTRIBUTING, SECURITY, ADRs) complement these manuals with English-language onboarding guidance.
