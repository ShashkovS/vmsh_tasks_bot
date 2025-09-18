# VMSh Tasks Bot

VMSh Tasks Bot is an asynchronous Telegram assistant used by the Moscow math circle to manage problem assignments, collect solutions, and broadcast live game updates. The project combines an [aiogram](https://docs.aiogram.dev/) bot, aiohttp web applications, a SQLite database, and Google Sheets synchronization routines so tutors can administer tasks from a single workflow.

## Overview
- The `main.py` entry point wires every application, exposes the aiohttp server on port 8179 during development, and keeps graceful shutdown routines for background tasks.
- `apps/` contains pluggable aiohttp modules: the Telegram bot, a teachers' scoreboard (`results_app.py`), the cooperative game dashboard (`game_web_app.py`), and an optional Zoom webhook parser (`zoom_events_parser.py`). The list of enabled modules is driven by the `apps` setting from the runtime configuration.
- Database access lives in `db_methods/`, which bootstraps SQLite via yoyo migrations and offers domain-specific helpers for lessons, queues, and game state.
- Google Sheets remain the single source of truth for problems, students, and teachers; `models/spreadsheets.py` loads sheets into SQLite when the database is empty.

## Features
- Telegram command handling, custom keyboards, and rate limiting implemented on top of aiogram.
- Teacher-only dashboards for results and statistics delivered through aiohttp routes that authenticate via web tokens stored in SQLite.
- Cooperative "game" web interface with websocket updates backed by NATS and Telegram notifications when treasure chests are opened.
- Zoom webhook ingestion that populates the queue table and normalizes participant names to match internal records.

## Architecture
A deeper breakdown of components, data flow, and external dependencies is available in [ARCHITECTURE.md](ARCHITECTURE.md).

## Requirements
- Python 3.9+ and SQLite 3.35+ (matching the deployment prerequisites used in production).
- Access to Telegram Bot API credentials, Google Sheets service account JSON, and spreadsheets that mirror the schemas consumed by `models/spreadsheets.py`.
- (Optional) A running NATS server when enabling realtime game dashboards or other cross-process messaging.

## Configuration
1. Copy `creds_test/vmsh_bot_config_test.json_ex` to either `creds_test/vmsh_bot_config_test.json` or the production counterpart under `creds_prod/`, then fill every field with the real bot token, Google Sheets key, webhook host, database path, and messaging channel identifiers.
2. Place the Google service account JSON obtained from Google Cloud under `creds_test/vmsh_bot_sheets_creds_test.json` (or the production path) so that `helpers.config` can read it on startup.
3. The configuration loader automatically runs yoyo migrations and resolves the SQLite path before returning a `Config` dataclass instance to the rest of the codebase.
4. The only environment flag is `PROD`. Set `PROD=true` to switch into production mode, otherwise omit it (or set any other value) to load the development credentials.

## Installation
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-test.txt  # optional, only needed for pytest and HTTP fixtures
```

## Running the stack
### Local development
1. Ensure SQLite and (optionally) NATS are available. Any missing migrations are applied automatically the first time `helpers.config` is imported.
2. Start the Telegram bot and aiohttp server in polling mode:
   ```bash
   source .venv/bin/activate
   python main.py
   ```
   The aiohttp server listens on [http://127.0.0.1:8179](http://127.0.0.1:8179/) and prints the list of registered routes for enabled apps.
3. When realtime features are required, start a NATS server (for example `nats-server -DV` or `docker run --rm -p 4222:4222 nats:latest`) before launching the bot so websocket broadcasts succeed.

### Production
- Enable `PROD=true`, provide the production JSON credentials under `creds_prod/`, and run the project behind gunicorn so that aiohttp handles Telegram webhooks instead of polling.
- Deployment automation, nginx examples, and SSL prerequisites are documented (in Russian) under [docs/deploy.md](docs/deploy.md).

## Testing
Run the complete suite with either the helper script or pytest directly:
```bash
./run_tests.sh
# or
pytest -vvs tests/
```
The tests rely on the same configuration loader and will create temporary databases using the paths from your JSON configuration files.

## HTTP API
An OpenAPI specification that describes the exposed aiohttp routes (login forms, teacher dashboards, game actions, and Zoom hooks) is maintained in [openapi.yaml](openapi.yaml).

## Additional documentation
- `docs/for_teacher.md`, `docs/for_admin.md`, and `docs/settings.md` provide end-user manuals for the Telegram bot (currently in Russian).
- `docs/tests.md` documents historical testing tips; follow this README for the latest dependency names.

## Maintainers
The git history is dominated by Sergey Shashkov, with additional contributions from eyakm1, chvtl, dirigabel, Max Ushakov, Oleg Yunin, ChV, and Viktor.

## License
The project is distributed under the MIT License; see [LICENCE](LICENCE) for details.
