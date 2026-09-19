# Phase 8: edited Telegram albums

## Result

- A live one-message edit of an already stored Telegram album reads the latest
  immutable revision and constructs a new complete snapshot.
- Changed caption/content replaces the album content. Changed media replaces
  only the matching `source_message_id`; all other stored objects and their
  order remain intact.
- The new revision keeps the original album identity and publication time.
- Edits still work after the current binding is disabled because the post owns
  a historical binding/owner snapshot.
- If the original album is absent, the adapter records
  `incomplete_edited_album` and does not invent missing media.

## Proof

- `uv run pytest -q pwa_tests/test_live_news.py pwa_tests/integration/test_phase8_news_mirror.py`
  — 8 passed.
- `uv run ruff check helpers/pwa/live_news.py pwa_tests/test_live_news.py`
  — passed.
- `git diff --check` — passed before commit.

Telegram still provides no ordinary deleted-channel-post update; explicit
reconciliation remains required for deletion.
