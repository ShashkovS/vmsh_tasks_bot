# Phase 8: news notification events

## Result

- The first live create of a verified course/group news post creates one
  deduplicated `news` notification event per eligible active Student account
  and linked, non-revoked Family account.
- Course posts target active course enrollments; group posts target active
  `course_group_access` rows. No recipient is inferred from Telegram titles.
- Backfill, duplicate delivery and edits do not create another notification.
- Routes remain audience-scoped and payloads contain only the public post ID.
- Existing notification preferences, quiet sound policy and durable Web Push
  delivery consume these events without a second outbox.
- Realtime `news` changes also invalidate `notification-events`; HTTP remains
  account-scoped.

## Proof

- `uv run pytest -q pwa_tests/test_live_news.py pwa_tests/integration/test_phase8_notification_core.py pwa_tests/integration/test_phase8_push_delivery.py`
  — 13 passed.
- `uv run pytest -q pwa_tests/test_pwa_app.py pwa_tests/integration/test_phase8_news_moderation.py`
  — 37 passed.
- `uv run ruff check db_methods/pwa/news.py models/pwa/news_notifications.py helpers/pwa/live_news.py pwa_tests/test_live_news.py`
  — passed.
- `git diff --check` — passed before commit.

No Telegram, S3 or Web Push network call is made by these tests.
