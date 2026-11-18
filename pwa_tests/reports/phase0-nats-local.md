# Phase-0 local NATS smoke — 2026-07-27

## Scope

- Endpoint: user-managed `nats://127.0.0.1:4222` only.
- Subject scope: generated `vmshpwa_agent_smoke_<run-id>` and a distinct
  generated agent isolation prefix.
- Payload: fixed synthetic JSON marker; no users, credentials or production
  identifiers.
- The test did not start, stop or reconfigure `nats-server`.

## Result

Command:

```bash
VMSH_RUN_LOCAL_NATS_SMOKE=1 \
  .venv/bin/python -m pytest -q -n0 \
  pwa_tests/integration/test_nats_live.py
```

Result: **1 passed** in 0.19 seconds.

Assertions proved:

- two independent clients under the same generated agent prefix both received
  the canonical JSON payload;
- the subscriber under the other generated prefix received nothing;
- every connection completed checked cleanup in `finally`; cleanup exceptions
  больше не превращаются в ложный PASS;
- startup readiness подтверждается server `flush`, reconnecting state не
  считается healthy, а disconnect имеет forced-close fallback;
- PWA использует per-audience cursor, bounded WebSocket fan-out и закрывает
  tracked sockets перед broker shutdown;
- Core NATS retained no durable test record.

The run emitted three upstream `nats-py` deprecation warnings about its internal
use of `asyncio.iscoroutinefunction`; they do not change delivery or cleanup and
are not emitted by project code.

Telegram live capability was not invoked as part of this report.
