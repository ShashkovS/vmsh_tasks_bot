"""Cross-worker/reload quota proof; 2026-10-11 Sentry decision and 0117."""

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from db_methods.pwa.connection import PwaConnectionFactory
from helpers.pwa.sentry_budget import admit_frontend_event
from pwa_tests.sqlite_template import create_test_database


NOW = datetime(2026, 10, 11, 23, 59, tzinfo=UTC)


@pytest.fixture
async def factories(tmp_path):
    path = tmp_path / "sentry.sqlite3"
    create_test_database(path)
    workers = [PwaConnectionFactory(path), PwaConnectionFactory(path)]
    try:
        yield workers
    finally:
        await asyncio.gather(*(worker.aclose() for worker in workers))


@pytest.mark.asyncio
async def test_parallel_workers_and_reopened_factory_share_daily_budget(factories):
    results = await asyncio.gather(*(
        admit_frontend_event(
            factories[index % 2], lane="query", signature=f"{index:08x}", now=NOW,
        )
        for index in range(64)
    ))
    assert results.count("admitted") == 3
    assert results.count("budget") == 61
    reopened = PwaConnectionFactory(factories[0].database_path)
    try:
        assert await admit_frontend_event(
            reopened, lane="query", signature="fffffffe", now=NOW + timedelta(minutes=2),
        ) == "budget"  # Crossing midnight does not reset a rolling window.
        assert await admit_frontend_event(
            reopened, lane="error", signature="ffffffff", now=NOW,
        ) == "admitted"
        rows = reopened.run_read(lambda db: db.execute("SELECT * FROM pwa_sentry_admissions").fetchall())
        assert len(rows) == 4
        assert set(rows[0].keys()) == {"id", "occurred_at", "lane", "signature"}
    finally:
        await reopened.aclose()


@pytest.mark.asyncio
async def test_one_representative_per_signature_per_day_across_workers(factories):
    results = await asyncio.gather(*(
        admit_frontend_event(worker, lane="error", signature="deadbeef", now=NOW)
        for worker in factories
        for _ in range(20)
    ))
    assert results.count("admitted") == 1
    assert results.count("repeat") == 39
    assert await admit_frontend_event(
        factories[1], lane="error", signature="deadbeef", now=NOW + timedelta(days=1),
    ) == "admitted"


@pytest.mark.asyncio
@pytest.mark.parametrize("lane,period_limit", [("query", 100), ("error", 900)])
async def test_rolling_period_budget_and_expiry(factories, lane, period_limit):
    factory = factories[0]
    # Isolate the long-window threshold from the separately tested daily cap.
    occurred = (NOW - timedelta(days=31)).isoformat(timespec="milliseconds")
    factory.run_write(lambda db: db.executemany(
        "INSERT INTO pwa_sentry_admissions (lane, signature, occurred_at) VALUES (?, ?, ?)",
        [(lane, f"{index:08x}", occurred) for index in range(period_limit)],
    ))
    assert await admit_frontend_event(
        factory, lane=lane, signature="ffffffff", now=NOW,
    ) == "budget"
    assert await admit_frontend_event(
        factory, lane=lane, signature="ffffffff", now=NOW + timedelta(days=1),
    ) == "admitted"
    assert factory.run_read(lambda db: db.execute(
        "SELECT count(*) AS total FROM pwa_sentry_admissions"
    ).fetchone()["total"]) == 1


@pytest.mark.asyncio
async def test_error_flood_cannot_exceed_reserved_daily_budget(factories):
    outcomes = await asyncio.gather(*(
        admit_frontend_event(
            factories[index % 2], lane="error", signature=f"{index:08x}", now=NOW,
        )
        for index in range(100)
    ))
    assert outcomes.count("admitted") == 30
    assert outcomes.count("budget") == 70


@pytest.mark.parametrize("lane,signature", [("recovery", "deadbeef"), ("error", "private-answer")])
def test_migration_constraints_reject_non_protocol_data(tmp_path, lane, signature):
    path = tmp_path / "constraints.sqlite3"
    create_test_database(path)
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO pwa_sentry_admissions (lane, signature, occurred_at) VALUES (?, ?, ?)",
                (lane, signature, NOW.isoformat(timespec="milliseconds")),
            )
