# Phase-0 live integration proof template

Этот файл — шаблон ручного proof, а не утверждение, что live-проверки уже
выполнены. Не вставлять tokens, secret keys, Telegram remote error bodies,
персональные данные или production destinations.

## Run metadata

- Date/time (UTC): `<YYYY-MM-DDTHH:MM:SSZ>`
- Reviewer: `<name>`
- Commit/worktree revision: `<revision>`
- Synthetic run marker: `<marker>`

## Local NATS

- User-managed server confirmed at `127.0.0.1:4222`: `<yes/no>`
- Generated agent prefix: `<vmshpwa_agent_smoke_RUN_ID>`
- Both same-prefix subscribers received canonical JSON: `<yes/no>`
- Different-prefix subscriber received nothing: `<yes/no>`
- Connections drained; server process was not stopped: `<yes/no>`
- Exact test command/result: `<command + pass/fail, no environment secrets>`

## Telegram test capability

- Explicit owner approval for this run: `<yes/no>`
- Read-only bind used canonical signed Bot API ID without transformation: `<yes/no>`
- `getMe` matched expected test bot username: `<yes/no>`
- `getChat` returned exact title, canonical ID, channel type and no public username: `<yes/no>`
- `getChatMember` proved post/edit/delete capability: `<yes/no>`
- Immutable owner-only local binding persisted and reviewed: `<yes/no>`
- Write-enabled smoke ignored/refused environment destination: `<yes/no>`
- Identity was revalidated from the persisted binding before send: `<yes/no>`
- Synthetic message ID: `<id or not-created>`
- Send succeeded: `<yes/no>`
- Edit succeeded: `<yes/no>`
- Cleanup attempted: `<yes/no>`
- Delete succeeded: `<yes/no>`
- Runtime safe-report path: `<.runtime path; do not commit its JSON>`
- Exact test command/result: `<command + pass/fail, no token>`

## Review outcome

- Unexpected side effects: `<none/details>`
- Residual synthetic objects/messages: `<none/details and cleanup owner>`
- Accepted for Phase-0 proof: `<yes/no>`
- Follow-up: `<none/issue>`
