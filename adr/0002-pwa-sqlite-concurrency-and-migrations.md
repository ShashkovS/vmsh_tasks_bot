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
- <https://sqlite.org/howtocorrupt.html#_unlinking_or_renaming_a_database_file_while_in_use>
- <https://docs.python.org/3.14/library/fcntl.html#fcntl.flock>
- <https://ollycope.com/software/yoyo/latest/#calling-yoyo-from-python-code>

## Decision

1. Migrations are applied only by an explicit seed/deploy command under yoyo's
   lock. PWA runtime startup performs a read-only migration-head check and fails
   with a diagnostic when migrations are missing, changed or newer than the
   checkout. Legacy startup retains its old auto-apply behavior until its
   separate cutover.
2. New PWA repositories use `PwaConnectionFactory`. Runtime enables two lazy,
   persistent connections after acquiring its lifecycle lock: one reader and
   one writer, each confined to its own single-thread executor. Connections
   are reused between complete units of work, never concurrently or across
   threads. Standalone synchronous maintenance retains connection-per-operation.
3. Async callers move the entire operation to a worker thread; callbacks are
   synchronous. No `await`, network access or media conversion occurs inside a
   transaction.
   Performance amendment (9 September 2026): runtime admits at most one
   async read and one async write to the executors at a time. Separate gates
   preserve WAL read progress while a writer waits. Waiting happens on the
   event loop, not in executor threads; cancellation of a queued caller opens
   no connection, cancellation after dispatch drains the callback before
   releasing its permit. Cleanup drains the units of work and closes both
   connections on their owner threads before releasing the lifecycle lock;
   this also holds if the cleanup caller is cancelled. No transaction may
   remain open after a callback; exceptional writes roll back. Measurements and
   rollout checks: `vmshpwa/docs/sqlite-admission-performance.md`.
4. The explicit maintenance command enables persistent WAL mode. Runtime
   startup verifies WAL without changing it; each new connection enables
   `foreign_keys`, verifies WAL and uses a bounded `busy_timeout`.
5. Multi-write use cases acquire the writer slot with `BEGIN IMMEDIATE`, then
   retry only `SQLITE_BUSY`/`SQLITE_LOCKED` using the finite policy
   `25ms, 75ms, 225ms` after the initial attempt. Exhaustion is observable as
   `BusyRetryExhausted`; it is not silently converted to success.
6. Durable external effects happen from an outbox after commit. Later phases
   introduce the outbox tables and workers; this ADR only establishes the
   transaction boundary.
7. WAL files stay on the same host/filesystem as the database and are included
   with `-wal`/`-shm` in migration rehearsal and backup coordination.
8. Every PWA worker acquires a non-blocking shared `flock` on a stable sibling
   lifecycle file before it checks or opens SQLite, and holds that descriptor
   in an aiohttp cleanup context until after `on_shutdown` and active-request
   draining. Seed and migration commands acquire the exclusive
   form before inspecting sidecars and hold it through the final schema change
   or atomic replacement plus directory sync. The lock file is never renamed or
   removed. This application-level protocol is required because SQLite warns
   that renaming an open database can pair two database inodes with the same
   pathname-derived WAL/journal and cause corruption. A busy lock fails fast;
   operators stop the runtime or retry maintenance instead of waiting silently.
   Runtime acquisition happens synchronously during worker startup, after the
   Gunicorn fork; the blocking schema preflight runs in a worker thread while
   the lock remains cancellation-safe. Descriptors use `CLOEXEC` and release
   by final `close()`, not explicit `LOCK_UN`, so an inherited duplicate cannot
   unlock its parent. Existing database and lock files must be regular,
   single-link, non-symlink paths; lock open uses `O_NOFOLLOW` and verifies
   pathname/device/inode identity.
   This is a cooperative contract for the PWA runtime and maintenance commands,
   not a replacement for SQLite's transaction locks or yoyo's migration lock.
9. Backend runtime is supported on a local filesystem with working Unix/BSD
   `flock` semantics (macOS development and Linux production). Runtime and
   maintenance run as the same service identity; the persistent lock file is
   mode `0600`. Network filesystems with uncertain lock semantics are excluded.

## Consequences

- Contention is surfaced early instead of occurring midway through a deferred
  write transaction.
- Long CPU/network work must be prepared before entering the transaction.
- Repositories receive a connection from the unit of work rather than importing
  the legacy global connection.
- SQLite remains suitable while measured workload stays within the Phase 0
  workload profile. Phase 11 re-evaluates that decision against production
  latency, busy-rate and queue-depth evidence.
- Seed/migrate cannot race a cooperating two-worker deployment, and a worker
  cannot start against a database pathname while it is being replaced. Legacy
  scripts that bypass this lock remain outside the atomic-reseed contract; the
  production deploy must stop all such writers before database replacement.

## Verification

- `pwa_tests/integration/test_sqlite_concurrency.py` covers two writers, bounded
  retry exhaustion and rollback after an exception.
- `pwa_tests/integration/test_migration_lifecycle.py` proves explicit apply,
  persistent WAL, no startup mutation and mismatch/future-schema rejection.
- `pwa_tests/test_app_factory.py` proves that the real aiohttp startup rejects
  an absent schema and exposes the verified connection factory after explicit
  migration.
- `pwa_tests/integration/test_runtime_lifecycle_lock.py` proves shared
  multi-process/exclusive-maintenance semantics, fork-safe close, stale-lock
  reuse, fail-fast behavior and DB/lock path identity guards.
  `pwa_tests/test_app_factory.py` additionally proves cancellation-safe
  preflight and cleanup after a later startup failure. `pwa_tests/test_seed_runtime.py` exercises a
  runtime start attempt at the exact pre-`os.replace` boundary.
