# Phase 8: optional live Telegram news adapter

## Result

- The existing aiogram router observes new and edited channel posts only when
  the PWA adapter injects its callback. PWA-only startup still has no Telegram
  dependency and never starts polling.
- Media-group updates wait one short bounded interval, are ingested once and
  are sorted by Telegram message ID.
- The live path is direct: normalize → mirror media → one SQLite ingest
  transaction → `news` realtime invalidation for actual create/update/delete.
- Unmapped or ambiguous sources stop in the existing diagnostic table before
  downloading media.
- A one-message edit of an existing album is recorded as
  `incomplete_edited_album` and cannot replace a complete album with a partial
  snapshot.

## Implementation

- `handlers/pwa_news_handlers.py`
- `helpers/pwa/live_news.py`
- `apps/pwa_app.py`

## Proof

- `uv run pytest -q pwa_tests/test_live_news.py pwa_tests/test_pwa_news_handler.py pwa_tests/test_telegram_news_aiogram.py pwa_tests/test_news_media.py`
  — 8 passed.
- `uv run ruff check apps/pwa_app.py handlers/pwa_news_handlers.py helpers/pwa/live_news.py pwa_tests/test_live_news.py pwa_tests/test_pwa_news_handler.py`
  — passed.
- `make telegram-history-test` — 44 passed; the existing bot submission and
  weekly-operation flows remain unchanged.
- `uv run pytest -q pwa_tests/test_api_contracts.py pwa_tests/test_pwa_app.py`
  — 51 passed; PWA-only composition still requires no Telegram token or bot.
- `git diff --check` — passed before commit.

Known Telegram Bot API boundary: there is no ordinary deleted-channel-post
update. Source deletion therefore still needs explicit reconciliation/backfill;
it is not guessed from missing updates. Full edited-album reconstruction is the
next adapter increment.
