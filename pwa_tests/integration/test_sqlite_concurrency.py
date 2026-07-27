from __future__ import annotations

import asyncio
import threading

import pytest

from db_methods.pwa import (
    BusyRetryExhausted,
    PwaConnectionFactory,
    SqliteConcurrencyPolicy,
    apply_schema_migrations,
)


@pytest.fixture()
def database_path(tmp_path):
    path = tmp_path / "concurrency.sqlite3"
    apply_schema_migrations(path)
    return path


def test_second_writer_retries_then_reports_exhaustion(database_path):
    sleeps: list[float] = []
    policy = SqliteConcurrencyPolicy(
        busy_timeout_ms=1,
        retry_delays_seconds=(0.001, 0.002),
    )
    holder = PwaConnectionFactory(database_path, policy=policy)
    contender = PwaConnectionFactory(
        database_path, policy=policy, sleeper=sleeps.append
    )

    with holder.write_transaction() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO kv (key, value) VALUES ('holder', '1')"
        )
        with pytest.raises(BusyRetryExhausted) as error:
            contender.run_write(
                lambda other: other.execute(
                    "INSERT OR REPLACE INTO kv (key, value) VALUES ('contender', '1')"
                )
            )

    assert error.value.attempts == 3
    assert sleeps == [0.001, 0.002]
    contender.run_write(
        lambda connection: connection.execute(
            "INSERT OR REPLACE INTO kv (key, value) VALUES ('contender', '1')"
        )
    )


def test_exception_rolls_back_the_complete_unit_of_work(database_path):
    factory = PwaConnectionFactory(database_path)

    def failing_write(connection):
        connection.execute("INSERT INTO kv (key, value) VALUES ('before-crash', '1')")
        raise RuntimeError("synthetic crash")

    with pytest.raises(RuntimeError, match="synthetic crash"):
        factory.run_write(failing_write)

    stored = factory.run_read(
        lambda connection: connection.execute(
            "SELECT value FROM kv WHERE key = 'before-crash'"
        ).fetchone()
    )
    assert stored is None


@pytest.mark.asyncio
async def test_async_boundary_moves_the_whole_operation_off_event_loop(database_path):
    factory = PwaConnectionFactory(database_path)
    event_loop_thread = threading.get_ident()

    worker_thread = await factory.run_read_async(
        lambda _connection: threading.get_ident()
    )

    assert worker_thread != event_loop_thread


def test_unit_of_work_rejects_coroutine_callbacks(database_path):
    factory = PwaConnectionFactory(database_path)

    async def invalid_operation(_connection):
        await asyncio.sleep(0)

    with pytest.raises(TypeError, match="must be synchronous"):
        factory.run_write(invalid_operation)
