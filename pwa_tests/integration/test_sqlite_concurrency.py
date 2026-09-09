from __future__ import annotations

import asyncio
import threading

import pytest

from helpers.pwa.request_trace import RequestTrace, current_trace

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


@pytest.mark.asyncio
async def test_trace_records_database_stages_without_sql(database_path):
    factory = PwaConnectionFactory(database_path)
    trace = RequestTrace()
    token = current_trace.set(trace)
    try:
        await factory.run_write_async(
            lambda connection: (
                connection.execute(
                    "INSERT INTO kv (key, value) VALUES ('trace-secret', 'secret')"
                ).rowcount
            )
        )
        await factory.run_read_async(
            lambda connection: connection.execute("SELECT 1").fetchone()
        )
    finally:
        current_trace.reset(token)
    assert set(trace.stages) == {
        "db.admission_queue",
        "db.thread_queue",
        "db.connect",
        "db.write_lock",
        "db.write",
        "db.commit",
        "db.read",
    }
    assert trace.stages["db.connect"][0] == 2
    assert "secret" not in str(trace.stages)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["read", "write"])
async def test_admission_bounds_workers_and_releases_after_failure(database_path, kind):
    factory = PwaConnectionFactory(
        database_path, policy=SqliteConcurrencyPolicy(read_concurrency=1)
    )
    run = getattr(factory, f"run_{kind}_async")
    started = threading.Event()
    release = threading.Event()
    second_started = threading.Event()

    def first(_connection):
        started.set()
        assert release.wait(5)
        raise ValueError("callback failure")

    task = asyncio.create_task(run(first))
    assert await asyncio.to_thread(started.wait, 5)
    second = asyncio.create_task(run(lambda _connection: second_started.set()))
    try:
        await asyncio.sleep(0.03)
        assert not second_started.is_set()
    finally:
        release.set()
    with pytest.raises(ValueError, match="callback failure"):
        await task
    await second
    assert second_started.is_set()


@pytest.mark.asyncio
async def test_cancelled_worker_keeps_permit_until_connection_closes(database_path):
    factory = PwaConnectionFactory(
        database_path, policy=SqliteConcurrencyPolicy(read_concurrency=1)
    )
    started = threading.Event()
    release = threading.Event()
    second_started = threading.Event()

    def first(_connection):
        started.set()
        assert release.wait(5)
        raise ValueError("failure after cancellation")

    task = asyncio.create_task(factory.run_read_async(first))
    assert await asyncio.to_thread(started.wait, 5)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    second = asyncio.create_task(
        factory.run_read_async(lambda _connection: second_started.set())
    )
    try:
        await asyncio.sleep(0.03)
        assert not task.done()
        assert not second_started.is_set()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await second


@pytest.mark.asyncio
async def test_waiting_writer_does_not_block_reads_or_leak_cancelled_waiter(database_path):
    factory = PwaConnectionFactory(database_path)
    started = threading.Event()
    release = threading.Event()

    def hold_writer(connection):
        connection.execute("INSERT INTO kv (key, value) VALUES ('uncommitted', '1')")
        started.set()
        assert release.wait(5)

    writer = asyncio.create_task(factory.run_write_async(hold_writer))
    assert await asyncio.to_thread(started.wait, 5)
    waiter = asyncio.create_task(factory.run_write_async(lambda _connection: None))
    try:
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert await asyncio.wait_for(factory.run_read_async(
            lambda c: c.execute("SELECT value FROM kv WHERE key = 'uncommitted'").fetchone()
        ), 2) is None
    finally:
        release.set()
        await writer
    assert await factory.run_write_async(lambda _connection: 42) == 42
