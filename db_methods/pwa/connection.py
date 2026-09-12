"""SQLite units of work and two thread-owned runtime connections (ADR 0002)."""

from __future__ import annotations

import asyncio
import inspect
import sqlite3
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from helpers.pwa.request_trace import trace_stage, submit_traced_thread

from .migrations import require_current_schema


ResultT = TypeVar("ResultT")


class BusyRetryExhausted(RuntimeError):
    """A write could not acquire SQLite's single writer slot in time."""

    def __init__(self, attempts: int) -> None:
        super().__init__(f"SQLite write lock was busy after {attempts} attempts")
        self.attempts = attempts


class JournalModeMismatchError(RuntimeError):
    """The runtime database was not prepared in persistent WAL mode."""


@dataclass(frozen=True, slots=True)
class SqliteConcurrencyPolicy:
    busy_timeout_ms: int = 750
    retry_delays_seconds: tuple[float, ...] = (0.025, 0.075, 0.225)
    write_begin: str = "BEGIN IMMEDIATE"
    read_concurrency: int = 2
    write_concurrency: int = 1

    def __post_init__(self) -> None:
        if self.read_concurrency < 1 or self.write_concurrency < 1:
            raise ValueError("SQLite concurrency must be positive")
        if self.busy_timeout_ms < 0:
            raise ValueError("busy_timeout_ms must be non-negative")
        if any(delay < 0 for delay in self.retry_delays_seconds):
            raise ValueError("retry delays must be non-negative")
        if self.write_begin != "BEGIN IMMEDIATE":
            raise ValueError("PWA write transactions must use BEGIN IMMEDIATE")


class PwaConnectionFactory:
    """Run complete synchronous units of work without sharing transactions.

    Runtime opts into one persistent reader and writer, each confined to its
    own thread. Standalone sync/maintenance calls keep fresh connections. See
    ``adr/0002-pwa-sqlite-concurrency-and-migrations.md`` and the fault tests in
    ``pwa_tests/integration/test_sqlite_concurrency.py``.
    """

    def __init__(
        self,
        database_path: str | Path,
        *,
        policy: SqliteConcurrencyPolicy | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        verify_schema: bool = True,
    ) -> None:
        self.database_path = Path(database_path)
        self.policy = policy or SqliteConcurrencyPolicy()
        self._sleep = sleeper
        # ADR 0002: bound schema-loading contention before entering the thread
        # pool. Writers waiting on another process must not consume read slots.
        self._read_slots = asyncio.Semaphore(self.policy.read_concurrency)
        self._write_slots = asyncio.Semaphore(self.policy.write_concurrency)
        self._local = threading.local()
        self._executors: dict[str, ThreadPoolExecutor] = {}
        self._closed = False
        self._close_task: asyncio.Task | None = None
        if verify_schema:
            require_current_schema(self.database_path)
            self._require_wal_mode()

    def start_async_workers(self) -> None:
        """Enable two lazy connections after runtime has acquired its flock."""
        if self._closed or self._executors:
            raise RuntimeError("SQLite workers already started or closed")
        self._read_slots = asyncio.Semaphore(1)
        self._write_slots = asyncio.Semaphore(1)
        for role in ("read", "write"):
            self._executors[role] = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix=f"pwa-db-{role}"
            )

    def _close_workers(self) -> None:
        def close_connection():
            connection = getattr(self._local, "connection", None)
            if connection is not None:
                connection.close()
                self._local.connection = None

        try:
            closing = [executor.submit(close_connection) for executor in self._executors.values()]
            for future in closing:
                future.result()
        finally:
            for executor in self._executors.values():
                executor.shutdown(wait=True)

    async def aclose(self) -> None:
        """Drain dispatched operations and close on owner threads before unlock."""
        async def close():
            async with self._read_slots, self._write_slots:
                await asyncio.to_thread(self._close_workers)

        if self._close_task is None:
            self._closed = True
            self._close_task = asyncio.create_task(close())
        await self._drain_on_cancel(self._close_task)

    def _require_wal_mode(self) -> None:
        uri = f"{self.database_path.resolve().as_uri()}?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, autocommit=True)) as connection:
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        if str(journal_mode).casefold() != "wal":
            raise JournalModeMismatchError(
                "SQLite database is not in WAL mode; run the explicit migration command"
            )

    @staticmethod
    def _dict_factory(
        cursor: sqlite3.Cursor, row: tuple[object, ...]
    ) -> dict[str, object]:
        return {
            description[0]: row[index]
            for index, description in enumerate(cursor.description)
        }

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=self.policy.busy_timeout_ms / 1000,
            autocommit=True,
        )
        try:
            connection.row_factory = self._dict_factory
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {self.policy.busy_timeout_ms}")
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[
                "journal_mode"
            ]
            if str(journal_mode).casefold() != "wal":
                raise JournalModeMismatchError(
                    "SQLite database left WAL mode after runtime preflight"
                )
        except BaseException:
            connection.close()
            raise
        return connection

    def _begin_write(self, connection: sqlite3.Connection) -> None:
        attempts = 0
        delays = (0.0, *self.policy.retry_delays_seconds)
        for index, delay in enumerate(delays):
            attempts += 1
            if delay:
                self._sleep(delay)
            try:
                connection.execute(self.policy.write_begin)
                return
            except sqlite3.OperationalError as exc:
                error_code = getattr(exc, "sqlite_errorcode", None)
                primary_error_code = (
                    error_code & 0xFF if isinstance(error_code, int) else None
                )
                is_busy = primary_error_code in {
                    sqlite3.SQLITE_BUSY,
                    sqlite3.SQLITE_LOCKED,
                }
                if not is_busy:
                    raise
                if index == len(delays) - 1:
                    raise BusyRetryExhausted(attempts) from exc

    @contextmanager
    def read_connection(self) -> Iterator[sqlite3.Connection]:
        reusable = getattr(self._local, "reusable", False)
        connection = getattr(self._local, "connection", None) if reusable else None
        if connection is None:
            with trace_stage("db.connect"):
                connection = self.connect()
            if reusable:
                self._local.connection = connection
        try:
            yield connection
        finally:
            if reusable:
                # No transaction/snapshot may escape into the next callback.
                try:
                    if connection.in_transaction:
                        connection.execute("ROLLBACK")
                except BaseException:
                    connection.close()
                    self._local.connection = None
                    raise
            else:
                connection.close()

    @contextmanager
    def write_transaction(self) -> Iterator[sqlite3.Connection]:
        with self.read_connection() as connection:
            with trace_stage("db.write_lock"):
                self._begin_write(connection)
            try:
                yield connection
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
            else:
                with trace_stage("db.commit"):
                    connection.execute("COMMIT")

    def run_read(self, operation: Callable[[sqlite3.Connection], ResultT]) -> ResultT:
        with self.read_connection() as connection:
            with trace_stage("db.read"):
                result = operation(connection)
            if inspect.isawaitable(result):
                if inspect.iscoroutine(result):
                    result.close()
                raise TypeError("Database unit of work callbacks must be synchronous")
            return result

    def run_write(self, operation: Callable[[sqlite3.Connection], ResultT]) -> ResultT:
        with self.write_transaction() as connection:
            with trace_stage("db.write"):
                result = operation(connection)
            if inspect.isawaitable(result):
                if inspect.iscoroutine(result):
                    result.close()
                raise TypeError("Database unit of work callbacks must be synchronous")
            return result

    async def run_read_async(
        self, operation: Callable[[sqlite3.Connection], ResultT]
    ) -> ResultT:
        return await self._run_admitted("read", self._read_slots, self.run_read, operation)

    async def run_write_async(
        self, operation: Callable[[sqlite3.Connection], ResultT]
    ) -> ResultT:
        return await self._run_admitted("write", self._write_slots, self.run_write, operation)

    async def _run_admitted(
        self,
        role: str,
        slots: asyncio.Semaphore,
        runner: Callable[[Callable[[sqlite3.Connection], ResultT]], ResultT],
        operation: Callable[[sqlite3.Connection], ResultT],
    ) -> ResultT:
        with trace_stage("db.admission_queue"):
            await slots.acquire()
        try:
            if self._closed:
                raise RuntimeError("SQLite workers are closed")
            executor = self._executors.get(role)

            def run():
                self._local.reusable = executor is not None
                return runner(operation)

            worker = submit_traced_thread(run, executor=executor)
            return await self._drain_on_cancel(worker)
        finally:
            slots.release()

    @staticmethod
    async def _drain_on_cancel(worker):
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError:
            # Cancellation cannot stop SQLite: keep the permit until the unit
            # of work has finished, even if shutdown cancels the caller again.
            while not worker.done():
                try:
                    await asyncio.shield(worker)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if not worker.cancelled():
                worker.exception()
            raise
