# 0001 - Adopt aiogram, aiohttp, SQLite, and Google Sheets as the core stack

## Status
Accepted

## Context
The bot needs to coordinate assignments between dozens of students and teachers, expose administrative dashboards, and integrate with Google Sheets (the existing source of truth for tasks). Telegram updates must be processed asynchronously, a lightweight database is required to run on inexpensive servers, and the team already maintains Google spreadsheets with the necessary metadata.

## Decision
- Use **aiogram 3** for Telegram updates because it provides asyncio-friendly dispatching, middleware, and webhook integration already leveraged by `apps/tg_bot.py` and the `handlers/` modules.
- Use **aiohttp** for HTTP services so the Telegram bot, results dashboard, game board, and Zoom webhook can share one event loop inside `main.py` while remaining modular under `apps/`.
- Store state in **SQLite** managed by yoyo migrations. The schema lives alongside the code (`migrations/`, `db_methods/`, `models/`) and runs without external infrastructure in both development and production.
- Keep **Google Sheets** as the canonical dataset, synchronizing it into SQLite through `models/spreadsheets.py` and `helpers/loader_from_google_spreadsheets.py` when the database is empty or refreshed manually.
- Employ **NATS** as the optional message bus for realtime features. `helpers/nats_brocker.py` publishes updates that the game dashboard and bot consume to stay consistent across multiple processes.

## Consequences
- Developers must configure both JSON credentials and service account access to Google Sheets before the application works locally.
- SQLite limitations (single-writer) require careful batching of writes and task coordination, but migrations remain easy to version and deploy.
- Running all aiohttp apps inside one process simplifies deployment under gunicorn but makes careful shutdown handling necessary to avoid leaving background tasks alive.
- NATS is optional, yet realtime features degrade gracefully when it is unavailable because the broker wrapper falls back to in-process callbacks. Production environments still need to run a secured NATS cluster for the best experience.
