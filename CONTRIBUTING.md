# Contributing to VMSh Tasks Bot

Thank you for helping the math circle bot evolve. This document captures the conventions already used in the repository so that new contributions integrate smoothly.

## Set up a development environment
1. Clone the repository and create a virtual environment:
   ```bash
   git clone https://github.com/ShashkovS/vmsh_tasks_bot.git
   cd vmsh_tasks_bot
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install -r requirements-test.txt
   ```
2. Copy `creds_test/vmsh_bot_config_test.json_ex` to `creds_test/vmsh_bot_config_test.json` (or to the equivalent file under `creds_prod/`) and fill the Telegram bot token, Google Sheets key, webhook host, database path, and channel identifiers.
3. Place the Google service account JSON referenced by the configuration at `creds_test/vmsh_bot_sheets_creds_test.json` so that `helpers.config` can load credentials on startup.
4. Keep a SQLite 3.35+ binary and, if you plan to work on realtime features, a running NATS server accessible at the URL configured in the JSON file.

## Local development workflow
- The entry point is `python main.py`. In development it runs the Telegram bot in polling mode and serves the aiohttp apps on `http://127.0.0.1:8179`.
- On import, `helpers.config` runs yoyo migrations located in the `migrations/` directory. Commit any new migration scripts so other contributors obtain the same schema.
- To generate a new migration, install `yoyo-migrations` (already listed in `requirements.txt`) and use a command such as:
  ```bash
  yoyo new --sql -m "short-description" migrations
  ```
  Fill in the forward and backward SQL statements before committing the file.

## Coding standards
- Follow idiomatic Python style (PEP 8/PEP 257) and reuse existing helper functions from modules such as `helpers/bot.py`, `db_methods/`, and `models/` whenever possible.
- Keep asynchronous code cooperative: prefer `asyncio.create_task` for long-lived jobs and cancel tasks during shutdown using the same patterns already present in `main.py` and `apps/tg_bot.py`.
- Update or extend unit tests under `tests/` when you change behaviour. Fixtures rely on the JSON configuration, so ensure your test setup works with both development and production modes.

## Testing
Run the full suite locally before submitting changes:
```bash
./run_tests.sh
# or
pytest -vvs tests/
```
When writing new tests, prefer `pytest` and keep database interactions isolated to temporary files.

## Submitting changes
1. Format and lint your code manually; no automated formatters are configured in this repository.
2. Commit logically grouped changes with descriptive messages.
3. Open a pull request that describes the intent, implementation details, configuration updates, and any manual testing performed.
4. Reference related documentation updates (README, ARCHITECTURE, ADRs, etc.) whenever behaviour changes.

Thank you for contributing!
