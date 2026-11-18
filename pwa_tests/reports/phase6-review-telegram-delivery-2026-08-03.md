# Phase 6: immediate Telegram review delivery

Date: 2026-08-03.

## Delivered

- A completed Staff review is read back from SQLite and sent to the Student's
  existing personal bot chat immediately after the authoritative transaction.
- A combined synonym case lists every concrete source problem. The message
  includes the legacy verdict symbol and the public Teacher comment.
- Every stored annotation is rendered over its immutable source WebP by the
  existing `helpers/pwa/review_composite.py` renderer and sent as a separate
  PNG. The source object is never replaced.
- Messages and photos are silent, matching the current legacy review path.
  Long comments are split into conservative 3500-character chunks by the real
  aiogram adapter.

## Deliberately small boundary

- `db_methods/pwa/review_telegram.py` performs only focused mechanical reads;
  it contains no delivery policy or localized text.
- `apps/pwa_api/review_routes.py` formats Russian MVP copy and performs the
  best-effort post-commit delivery.
- `apps/pwa_app.py` wires the existing bot only when the Telegram adapter is
  explicitly enabled. PWA-only startup and all normal tests need no Telegram
  credentials or network.
- No new queue, repository, retry framework or dashboard was added. A later
  version may add delivery observability if real MVP use demonstrates the need.

## Failure and idempotency semantics

- The review/result transaction commits before Telegram work begins.
- Failure to read or render one annotation omits that PNG but still attempts
  the text and every other successfully rendered image.
- Telegram failure is logged with stable review/attachment public IDs and does
  not roll back or change the HTTP success response.
- Replaying the same review idempotency key does not send a second message.
- Admin append-only correction is intentionally not re-notified, matching the
  owner decision to avoid duplicate notifications for corrections.

## Executable evidence

- Successful real aiohttp/SQLite completion proves one personal delivery, two
  synonym source labels, verdict/comment text, one composite PNG and no replay
  duplicate.
- Failure integration proves renderer and Telegram exceptions leave exactly
  one immutable review and one result committed.
- The production adapter test proves 3500-character splitting, `parse_mode=None`,
  silent messages/photos and stable PNG filenames without loading credentials.
- Existing real ImageMagick tests continue to prove PNG rendering and unchanged
  source SHA-256.
- Focused review/API/app-factory regression before the final two failure cases:
  **54 passed**; final delivery/composite matrix: **7 passed**.
- Full PWA Python regression with eight workers: **1634 passed, 6 skipped** in
  **75.22 seconds**.

No live Student message or production credential was used. The authorized test
channel is a channel, not a substitute for a Student's personal chat, so this
increment remains hermetic and tests the injected adapter boundary.
