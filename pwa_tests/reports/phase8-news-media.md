# Phase 8: Telegram news media storage

## Result

- A normalized Telegram post/album can copy every pending media item into the
  configured PWA object storage before the existing revision ingest runs.
- Images are re-encoded to WebP through the existing bounded 1920px converter;
  the original image is not retained.
- Video, audio and documents keep their bytes and validated MIME-derived
  extension.
- Final bytes use `news/sha256/...` content-addressed keys, so an interrupted
  album retry converges on the same objects and keeps Telegram order.
- Already stored import media is retained without download. Empty, incomplete,
  oversized or invalid converter output fails before a DB revision can become
  visible.

## Implementation

- `helpers/pwa/news_media.py`
- `helpers/object_storage.py`
- `helpers/pwa/content/assets.py`

## Proof

- `uv run pytest -q pwa_tests/test_news_media.py pwa_tests/integration/test_phase8_news_mirror.py`
  — 8 passed.
- `uv run ruff check helpers/pwa/news_media.py pwa_tests/test_news_media.py`
  — passed.
- `git diff --check` — passed before commit.

No live Telegram or S3 side effect is part of this hermetic slice. The live
test-only bucket is exercised by the separate Phase 0 integration harness.
