from __future__ import annotations

import asyncio
import threading

import pytest
import pytest_asyncio

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


@pytest_asyncio.fixture(params=[False, True], ids=["fresh", "persistent"])
async def async_factory(database_path, request):
    factory = PwaConnectionFactory(
        database_path, policy=SqliteConcurrencyPolicy(read_concurrency=1)
    )
    if request.param:
        factory.start_async_workers()
    try:
        yield factory
    finally:
        await factory.aclose()


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
async def test_admission_bounds_workers_and_releases_after_failure(async_factory, kind):
    factory = async_factory
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
async def test_cancelled_worker_keeps_permit_until_connection_closes(async_factory):
    factory = async_factory
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
async def test_waiting_writer_does_not_block_reads_or_leak_cancelled_waiter(async_factory):
    factory = async_factory
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


@pytest.mark.asyncio
async def test_persistent_connections_reuse_owner_threads_and_fresh_results(database_path):
    factory = PwaConnectionFactory(database_path)
    factory.start_async_workers()
    trace = RequestTrace()
    token = current_trace.set(trace)
    try:
        def identity(c):
            return id(c), threading.get_ident()

        reader = await factory.run_read_async(identity)
        writer = await factory.run_write_async(identity)
        assert reader[0] != writer[0]
        assert reader[1] != writer[1]
        for _ in range(5):
            assert await factory.run_read_async(identity) == reader
            assert await factory.run_write_async(identity) == writer
        assert trace.stages["db.connect"][0] == 2

        def broken(c):
            c.execute("INSERT INTO kv (key, value) VALUES ('rollback', '1')")
            raise ValueError("rollback")

        with pytest.raises(ValueError, match="rollback"):
            await factory.run_write_async(broken)
        assert await factory.run_read_async(
            lambda c: c.execute("SELECT value FROM kv WHERE key='rollback'").fetchone()
        ) is None
        await factory.run_write_async(
            lambda c: c.execute("INSERT INTO kv (key, value) VALUES ('fresh', '1')").rowcount
        )
        assert await factory.run_read_async(
            lambda c: c.execute("SELECT value FROM kv WHERE key='fresh'").fetchone()
        ) == {"value": "1"}
        # A mistakenly unfinished read transaction cannot pin a snapshot.
        await factory.run_read_async(lambda c: c.execute("BEGIN").rowcount)
        assert not await factory.run_read_async(lambda c: c.in_transaction)
    finally:
        current_trace.reset(token)
        await factory.aclose()
    await factory.aclose()
    with pytest.raises(RuntimeError, match="closed"):
        await factory.run_read_async(lambda c: None)


@pytest.mark.asyncio
async def test_cancelled_shutdown_drains_and_closes_on_owner_thread(database_path):
    factory = PwaConnectionFactory(database_path)
    factory.start_async_workers()
    started = threading.Event()
    release = threading.Event()
    worker_thread = None

    def blocking(c):
        nonlocal worker_thread
        worker_thread = threading.current_thread()
        started.set()
        assert release.wait(5)
        return c.execute("SELECT 1").fetchone()

    operation = asyncio.create_task(factory.run_read_async(blocking))
    assert await asyncio.to_thread(started.wait, 5)
    close = asyncio.create_task(factory.aclose())
    try:
        await asyncio.sleep(0.01)
        close.cancel()
        await asyncio.sleep(0.01)
        assert not close.done()
    finally:
        release.set()
    await operation
    with pytest.raises(asyncio.CancelledError):
        await close
    assert worker_thread is not None and not worker_thread.is_alive()
