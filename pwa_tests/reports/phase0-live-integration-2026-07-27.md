# Phase-0 live integration proof — 27 July 2026

This proof contains only synthetic results. Tokens, remote error bodies,
production destinations, real recipients and Telegram message IDs are not
recorded here. Detailed safe reports remain in the ignored, owner-only
`.runtime/vmshpwa/telegram-smoke/` directory.

## Local NATS

- The user-managed server at `127.0.0.1:4222` was used; the test did not start,
  stop or reconfigure it.
- Two clients under one generated agent prefix received the same canonical
  synthetic JSON event.
- A subscriber under a separate generated prefix received nothing.
- All clients completed checked cleanup; Core NATS retained no durable record.
- Result: `pwa_tests/integration/test_nats_live.py` — **1 passed**.
- Detailed proof: [`phase0-nats-local.md`](phase0-nats-local.md).

## Telegram test capability

- Owner approval: explicit permission was given for read/write/delete against
  the dedicated test bot and private test channel only.
- Read-only bind used the owner-provided canonical signed channel ID without
  deriving or transforming it.
- `getMe`, `getChat` and `getChatMember` matched the expected test-only bot,
  private channel identity and post/edit/delete capabilities.
- The verified binding was persisted only in the ignored owner-only runtime
  database. The write command accepted no destination from its environment.
- Before writing, the command revalidated the persisted identity through the
  Bot API.
- One fixed synthetic message was sent, edited and deleted successfully;
  cleanup ran and no synthetic message remained.
- Bind command: `make pwa-telegram-bind-test-channel` with the explicit live
  opt-in and canonical test-only channel ID — **passed**.
- Lifecycle command: `make pwa-telegram-live-smoke` with the explicit live
  opt-in — **passed**.

## Outcome

- Unexpected side effects: none observed.
- Residual synthetic objects/messages: none.
- Accepted Phase-0 capability proof: yes.
- Scope not proved here: rich Telegram HTML, `tg-math`, tables, media and album
  rendering; those remain Phase-2 content-pipeline acceptance tests.
