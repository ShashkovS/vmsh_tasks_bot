# Phase 8: live aiogram news normalization

## Result

- One channel post or a complete media group is normalized into the same
  snapshot accepted by the existing immutable news ingest.
- Album messages are ordered by Telegram message ID; the first available text
  or caption supplies the post text while every media item retains its source
  message ID.
- Message and caption entities use Telegram's UTF-16 offsets. Segmentation
  preserves nested marks and links around astral Unicode characters instead of
  shifting formatting after emoji.
- Unsupported entity names stay explicit in the stored snapshot and are not
  emitted as unsafe HTML.
- Photos, videos, animations, audio, voice and documents receive an ordered
  pending-media manifest for the storage step in `helpers/pwa/news_media.py`.

## Implementation

- `helpers/pwa/telegram_news.py`
- `models/pwa/news.py`
- `apps/pwa_api/news_routes.py`

## Proof

- `uv run pytest -q pwa_tests/test_telegram_news_aiogram.py pwa_tests/integration/test_phase8_news_mirror.py`
  — 7 passed.
- `uv run ruff check helpers/pwa/telegram_news.py models/pwa/news.py apps/pwa_api/news_routes.py pwa_tests/test_telegram_news_aiogram.py`
  — passed.
- `git diff --check` — passed before commit.

This slice has no Telegram network side effect. Handler registration, album
collection and the test-channel lifecycle remain the next adapter increment.
