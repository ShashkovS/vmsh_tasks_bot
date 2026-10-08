# Phase 8: news mirror storage and historical corpus

## Delivered slice

- Migration `0067.pwa_news_mirror` adds the Telegram/local post identity, immutable revisions, revision media, current PWA visibility and ingest diagnostics.
- `db_methods/pwa/news.py` contains only direct storage operations.
- `models/pwa/news.py` validates a normalized complete post/album snapshot and coordinates one transaction.
- Existing posts keep their binding/course/group snapshot: later edits and source deletion still apply after the original binding is disabled.
- A new post from an unmapped or ambiguous chat stops in diagnostics; owner identity is never guessed from a title or username.
- Duplicate content produces no new post, revision or media row.
- Telegram Desktop export parsing is isolated in `helpers/pwa/telegram_news.py`.

Desktop export does not contain Telegram `media_group_id`. The one-time backfill parser groups only consecutive photos with the same Unix timestamp and assigns an import-only album key. A future import command must show this inference in a dry-run preview before writing production data.

## Proof

- Migration up → down → up and `PRAGMA integrity_check`: passed.
- Create → duplicate → edit after binding disable → source delete: passed.
- Unmapped source diagnostic without post creation: passed.
- Historical `_external_pipelines/ChatExport_2026-07-25/result.json`: all **196** message records partitioned exactly once; all **167** photos retained in order; unsupported custom emoji is explicitly marked for safe fallback.
- Focused Phase 8/schema regression: **33 passed**.
- Final news/schema regression after formatting: **25 passed**.
- Canonical schema inventory: **397 objects**, SHA-256 `6cb150e1d26d6276f256e04e1bab8be2815bcd1da926e2245e825bc4deee0f06`.
- Ruff formatting and checks passed.

## Still outside this slice

- media copy to the configured object storage;
- live aiogram channel update adapter and album collection;
- audience feed/moderation HTTP API and frontend data wiring;
- NATS invalidation and news notification creation;
- owner-reviewed production backfill preview.
