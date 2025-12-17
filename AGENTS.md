# Repository Guidelines

## Project Structure
- `main.py` is the entry point; it starts the aiogram bot and aiohttp apps.
- `apps/` holds pluggable aiohttp modules (Telegram bot, dashboards, game UI, Zoom hooks). Enabled apps are selected via config.
- `handlers/` contains Telegram command/message handlers; `helpers/` provides shared bot, config, and utility code.
- `db_methods/` and `models/` implement domain logic and persistence over SQLite; schema changes live in `migrations/` (yoyo).
- `templates/` and `web/` contain HTML/Jinja assets for dashboards and the game UI.
- `tests/` contains pytest suites and fixtures.
- Secrets/config templates are in `creds_test/`, `creds_prod/`, and `.env.example`. Never commit real credentials.

## Build, Test, and Development Commands
- Install deps: `pip install -r requirements.txt` (+ `-r requirements-test.txt` for tests).
- Run locally: `python main.py` (polling mode; aiohttp on `http://127.0.0.1:8179`).
- Run tests: `./run_tests.sh` or `pytest -vvs tests/`.
- Create migrations: `yoyo new --sql -m "short-description" migrations`.
- (Optional) Fetch prod DB snapshot: `make dbl` (uses `scp` to `db/`; requires access).

## Coding Style & Naming
- Follow PEP 8/257; 4‑space indentation; prefer explicit names over abbreviations.
- Keep async code cooperative; use existing shutdown/task patterns from `main.py` and `apps/tg_bot.py`.
- No auto‑formatter is configured; run linters/formatting manually if you use them.

## Testing Guidelines
- Frameworks: `pytest` with `aresponses` for HTTP mocks.
- Name tests `test_*.py` and functions `test_*`.
- When changing DB behavior, add/adjust migrations and extend tests to cover the new paths.

## Commit & Pull Requests
- Commit history uses short Conventional‑Commit style (e.g., `feat: …`, `fix: …`). Use imperative, scoped messages.
- PRs should include: clear description, linked issue/ADR if relevant, config or migration notes, and how you validated the change (commands/output). Add screenshots for UI changes.

## Security & Configuration
- Use `creds_test/*_json_ex` as templates; set `PROD=true` only for production runs.
- Store service account JSON locally as described in `README.md`; do not add to git.
