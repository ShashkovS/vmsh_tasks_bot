# ADR 0002: SQLite concurrency and migration lifecycle for PWA

- Status: accepted for implementation
- Date: 2026-07-27
- Scope: new PWA domain services and shared write paths migrated to them

## Context

The Telegram adapter, two aiohttp/gunicorn workers and background delivery jobs
share one SQLite database. SQLite WAL lets readers and one writer progress
concurrently, but it still permits only one active write transaction. A deferred
transaction may also fail while being upgraded from a reader to a writer.

Python 3.14 recommends explicit `Connection.autocommit` handling. Yoyo applies
each migration transactionally and provides an inter-process migration lock.
Runtime startup must not unexpectedly take that lock or alter production schema.

Primary references checked on 27 July 2026:

- <https://docs.python.org/3.14/library/sqlite3.html#transaction-control>
- <https://sqlite.org/wal.html#concurrency>
- <https://sqlite.org/lang_transaction.html#deferred_immediate_and_exclusive_transactions>
- <https://sqlite.org/pragma.html#pragma_busy_timeout>
- <https://ollycope.com/software/yoyo/latest/#calling-yoyo-from-python-code>

## Decision

1. Migrations are applied only by an explicit seed/deploy command under yoyo's
   lock. PWA runtime startup performs a read-only migration-head check and fails
   with a diagnostic when migrations are missing, changed or newer than the
   checkout. Legacy startup retains its old auto-apply behavior until its
   separate cutover.
2. New PWA repositories use `PwaConnectionFactory`: one connection per complete
   synchronous operation. Connections are never shared across requests,
   coroutines or threads.
3. Async callers move the entire operation to `asyncio.to_thread`; callbacks are
   synchronous. No `await`, network access or media conversion occurs inside a
   transaction.
4. The explicit maintenance command enables persistent WAL mode. Runtime
   startup verifies WAL without changing it; each operation enables
   `foreign_keys`, verifies WAL again and uses a bounded `busy_timeout`.
5. Multi-write use cases acquire the writer slot with `BEGIN IMMEDIATE`, then
   retry only `SQLITE_BUSY`/`SQLITE_LOCKED` using the finite policy
   `25ms, 75ms, 225ms` after the initial attempt. Exhaustion is observable as
   `BusyRetryExhausted`; it is not silently converted to success.
6. Durable external effects happen from an outbox after commit. Later phases
   introduce the outbox tables and workers; this ADR only establishes the
   transaction boundary.
7. WAL files stay on the same host/filesystem as the database and are included
   with `-wal`/`-shm` in migration rehearsal and backup coordination.

## Consequences

- Contention is surfaced early instead of occurring midway through a deferred
  write transaction.
- Long CPU/network work must be prepared before entering the transaction.
- Repositories receive a connection from the unit of work rather than importing
  the legacy global connection.
- SQLite remains suitable while measured workload stays within the Phase 0
  workload profile. Phase 11 re-evaluates that decision against production
  latency, busy-rate and queue-depth evidence.

## Verification

- `pwa_tests/integration/test_sqlite_concurrency.py` covers two writers, bounded
  retry exhaustion and rollback after an exception.
- `pwa_tests/integration/test_migration_lifecycle.py` proves explicit apply,
  persistent WAL, no startup mutation and mismatch/future-schema rejection.
- `pwa_tests/test_app_factory.py` proves that the real aiohttp startup rejects
  an absent schema and exposes the verified connection factory after explicit
  migration.
