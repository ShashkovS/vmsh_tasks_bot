# Phase 8: Telegram scheduled-queue reconciliation

Date: 2026-08-03

## Result

- A small offline command validates the owner-reviewed inventory of posts that
  were scheduled manually in Telegram clients before Staff owns a destination.
- Every item has one explicit decision: retain in Telegram, cancel and recreate
  in Staff, or cancel as obsolete.
- Changed-after-review content/media, duplicate active intents, duplicate
  inventory keys and reused Staff drafts block cutover.
- Identical content in different destinations remains valid.
- Unknown fields are rejected, so a Telegram payload cannot accidentally enter
  the inventory/report path.
- The generated report contains aggregate counts, row ordinals and stable issue
  codes only. It contains no payload, Telegram ID, destination key or hash.
- The command is deliberately offline and does not add an MTProto user session:
  the official scheduled-history methods are user-only, while the Bot API does
  not expose the manually maintained Telegram-client queue.

## Files

- `vmshpwa/scripts/telegram_schedule_reconciliation.py`
- `pwa_tests/fixtures/telegram-scheduled-queue-v1.json`
- `pwa_tests/test_telegram_schedule_reconciliation.py`
- `vmshpwa/docs/telegram-scheduled-queue-cutover.md`
- `Makefile` target `pwa-telegram-schedule-reconcile`

## Proof

- `uv run pytest -q -n8 pwa_tests/test_telegram_schedule_reconciliation.py`
  — **8 passed**.
- `uv run ruff check vmshpwa/scripts/telegram_schedule_reconciliation.py
  pwa_tests/test_telegram_schedule_reconciliation.py` — passed.
- Complete `make pwa-python-test` regression — **1560 passed / 6 intentional
  skips in 116.44s**, eight workers.
- The committed synthetic inventory contains four rows across three decisions;
  `make pwa-telegram-schedule-reconcile ...` returned **ready (4 items,
  0 blockers)** and wrote a mode-`0600` aggregate report.
- The test matrix covers a post changed after review, exact-intent duplication,
  reused item/Staff keys, decision/Staff-draft ownership, timezone validation,
  same content in different destinations and rejection of an unexpected
  payload field.

This proof closes only the scheduled-queue cutover validator. Owner execution
against the real Telegram UI remains a deployment gate; deletion reconciliation
for already published channel posts is separate and still open.
