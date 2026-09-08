"""Connection-per-operation SQLite boundary for new PWA domain services."""

from __future__ import annotations

import inspect
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from helpers.pwa.request_trace import trace_stage, traced_thread

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

    def __post_init__(self) -> None:
        if self.busy_timeout_ms < 0:
            raise ValueError("busy_timeout_ms must be non-negative")
        if any(delay < 0 for delay in self.retry_delays_seconds):
            raise ValueError("retry delays must be non-negative")
        if self.write_begin != "BEGIN IMMEDIATE":
            raise ValueError("PWA write transactions must use BEGIN IMMEDIATE")


class PwaConnectionFactory:
    """Open a fresh connection for each synchronous unit of work.

    A connection never crosses an asyncio request/coroutine boundary. The async
    helpers below run the complete callback in one worker thread. See
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
        if verify_schema:
            require_current_schema(self.database_path)
            self._require_wal_mode()

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
        with trace_stage("db.connect"):
            connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def write_transaction(self) -> Iterator[sqlite3.Connection]:
        with trace_stage("db.connect"):
            connection = self.connect()
        try:
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
        finally:
            connection.close()

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
        return await traced_thread(self.run_read, operation)

    async def run_write_async(
        self, operation: Callable[[sqlite3.Connection], ResultT]
    ) -> ResultT:
        return await traced_thread(self.run_write, operation)
