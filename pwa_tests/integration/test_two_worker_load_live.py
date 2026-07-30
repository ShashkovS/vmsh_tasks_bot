"""Small two-worker write smoke sized from the observed club workload."""

from __future__ import annotations

import asyncio
import math
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
from aiohttp import ClientSession, DummyCookieJar, TCPConnector

from pwa_tests.fixtures.seed import load_baseline_v1
from pwa_tests.integration.test_two_worker_live import (
    REPOSITORY_ROOT,
    _stop_worker,
    _unused_port,
    _wait_until_ready,
    _worker_environment,
)
from vmshpwa.scripts.seed_runtime import _seed_runtime_under_lock


RUN_LIVE_SMOKE = os.environ.get("VMSH_RUN_TWO_WORKER_SMOKE") == "1"
CONCURRENT_LOGINS = 40

pytestmark = pytest.mark.skipif(
    not RUN_LIVE_SMOKE,
    reason="set VMSH_RUN_TWO_WORKER_SMOKE=1 for the local two-worker smoke",
)


def _count(database: Path, sql: str) -> int:
    with sqlite3.connect(database) as connection:
        return int(connection.execute(sql).fetchone()[0])


def _journal_mode(database: Path) -> str:
    with sqlite3.connect(database) as connection:
        return str(connection.execute("PRAGMA journal_mode").fetchone()[0])


@pytest.mark.asyncio
async def test_two_workers_complete_small_concurrent_write_burst(
    tmp_path: Path,
) -> None:
    """Exceed the observed minute peak without turning this into a load lab."""

    database = tmp_path / "shared-load.sqlite3"
    _seed_runtime_under_lock(database, tmp_path / "media", load_baseline_v1())
    sessions_before = _count(database, "SELECT count(*) FROM auth_sessions")
    events_before = _count(
        database,
        "SELECT count(*) FROM auth_events WHERE event_type = 'session.created'",
    )

    ports = [_unused_port(), _unused_port()]
    origins = [f"http://127.0.0.1:{port}" for port in ports]
    prefix = f"vmshpwa_agent_phase11_load_{uuid.uuid4().hex[:12]}"
    processes: list[subprocess.Popen[bytes]] = []
    log_paths = [tmp_path / "worker-0.log", tmp_path / "worker-1.log"]
    log_files = []
    session = ClientSession(
        cookie_jar=DummyCookieJar(), connector=TCPConnector(limit=CONCURRENT_LOGINS)
    )
    try:
        for index, port in enumerate(ports):
            log_file = log_paths[index].open("wb")
            log_files.append(log_file)
            processes.append(
                subprocess.Popen(
                    [sys.executable, "main.py"],
                    cwd=REPOSITORY_ROOT,
                    env=_worker_environment(
                        database=database,
                        media_root=tmp_path / f"media-{index}",
                        port=port,
                        origins=origins,
                        prefix=prefix,
                    ),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )
            )

        await asyncio.gather(
            *(_wait_until_ready(session, origin) for origin in origins)
        )

        async def login(index: int) -> float:
            started = time.monotonic()
            origin = origins[index % len(origins)]
            async with session.post(
                f"{origin}/student/api/v1/auth/login",
                headers={"Origin": origin, "X-Request-ID": f"phase11-load-{index}"},
                json={
                    "username": "testovyy-onlayn-14",
                    "telegramToken": "synthetic-telegram-token-not-a-secret",
                },
            ) as response:
                assert response.status == 200, await response.text()
                await response.read()
            return time.monotonic() - started

        burst_started = time.monotonic()
        latencies = await asyncio.gather(
            *(login(index) for index in range(CONCURRENT_LOGINS))
        )
        elapsed = time.monotonic() - burst_started

        ordered = sorted(latencies)
        p95 = ordered[math.ceil(len(ordered) * 0.95) - 1]
        # These are generous smoke bounds, not production latency SLOs. They
        # catch a stuck writer/timeout while remaining stable on a developer Mac.
        assert elapsed < 30
        assert p95 < 20
    finally:
        await session.close()
        for process in processes:
            _stop_worker(process)
        for log_file in log_files:
            log_file.close()

    assert _count(database, "SELECT count(*) FROM auth_sessions") == (
        sessions_before + CONCURRENT_LOGINS
    )
    assert (
        _count(
            database,
            "SELECT count(*) FROM auth_events WHERE event_type = 'session.created'",
        )
        == events_before + CONCURRENT_LOGINS
    )
    assert _journal_mode(database).casefold() == "wal"

    combined_logs = b"\n".join(path.read_bytes().lower() for path in log_paths)
    assert b"database is locked" not in combined_logs
    assert b"write lock was busy" not in combined_logs
