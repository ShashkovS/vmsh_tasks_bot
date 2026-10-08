"""Opt-in two-process PWA smoke against the user-managed local NATS server."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
from aiohttp import ClientSession, CookieJar

from helpers.nats_brocker import NatsBroker
from pwa_tests.fixtures.seed import load_baseline_v1
from vmshpwa.scripts.seed_runtime import _seed_runtime_under_lock


RUN_LIVE_SMOKE = os.environ.get("VMSH_RUN_TWO_WORKER_SMOKE") == "1"
LOCAL_NATS_URL = "nats://127.0.0.1:4222"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    not RUN_LIVE_SMOKE,
    reason="set VMSH_RUN_TWO_WORKER_SMOKE=1 for the local two-worker smoke",
)


def _unused_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


async def _wait_until_ready(session: ClientSession, origin: str) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            async with session.get(f"{origin}/student/api/v1/health") as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        await asyncio.sleep(0.1)
    raise AssertionError(f"PWA worker did not become ready at {origin}")


def _worker_environment(
    *, database: Path, media_root: Path, port: int, origins: list[str], prefix: str
) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "UV_CACHE_DIR": str(REPOSITORY_ROOT / ".runtime" / "uv-cache"),
            "VMSH_RUNTIME_PROFILE": "pwa-e2e",
            "VMSH_INSTANCE": "phase11-two-worker",
            "VMSH_DB_FILENAME": str(database),
            "VMSH_MEDIA_ROOT": str(media_root),
            "VMSH_NATS_SERVER": LOCAL_NATS_URL,
            "VMSH_NATS_TOPIC_PREFIX": prefix,
            "VMSH_PWA_PROTOTYPE": "false",
            "VMSH_API_PORT": str(port),
            "VMSH_PWA_PUBLIC_ORIGINS_JSON": json.dumps(
                {audience: origins for audience in ("student", "family", "staff")}
            ),
            "VMSH_PWA_AUTH_SIGNING_KEYS_JSON": json.dumps(["s" * 32]),
            "VMSH_PWA_REFRESH_PEPPER_B64": base64.urlsafe_b64encode(b"r" * 32).decode(),
            "VMSH_PWA_THROTTLE_PEPPER_B64": base64.urlsafe_b64encode(
                b"t" * 32
            ).decode(),
        }
    )
    return environment


def _stop_worker(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@pytest.mark.asyncio
async def test_two_workers_share_sqlite_and_receive_the_same_nats_invalidation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "shared.sqlite3"
    _seed_runtime_under_lock(database, tmp_path / "media", load_baseline_v1())

    ports = [_unused_port(), _unused_port()]
    origins = [f"http://127.0.0.1:{port}" for port in ports]
    prefix = f"vmshpwa_agent_phase11_{uuid.uuid4().hex[:12]}"
    processes: list[subprocess.Popen[bytes]] = []
    log_files = []
    publisher = NatsBroker(prefix)
    session = ClientSession(cookie_jar=CookieJar(unsafe=True))
    first_socket = second_socket = reconnected_socket = None
    try:
        for index, port in enumerate(ports):
            log_file = (tmp_path / f"worker-{index}.log").open("wb")
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
        async with session.post(
            f"{origins[0]}/student/api/v1/auth/login",
            headers={"Origin": origins[0]},
            json={
                "username": "testovyy-onlayn-14",
                "telegramToken": "synthetic-telegram-token-not-a-secret",
            },
        ) as login:
            assert login.status == 200, await login.text()

        # The login writes through worker A. Worker B must immediately accept
        # the same signed cookie and read the authoritative session from SQLite.
        async with session.get(
            f"{origins[1]}/student/api/v1/auth/me",
            headers={"Origin": origins[1]},
        ) as current_session:
            assert current_session.status == 200, await current_session.text()

        first_socket = await session.ws_connect(
            f"{origins[0].replace('http:', 'ws:')}/student/ws",
            origin=origins[0],
        )
        second_socket = await session.ws_connect(
            f"{origins[1].replace('http:', 'ws:')}/student/ws",
            origin=origins[1],
        )
        assert (await first_socket.receive_json(timeout=5))["type"] == "connected"
        assert (await second_socket.receive_json(timeout=5))["type"] == "connected"

        await publisher.setup(LOCAL_NATS_URL)
        await publisher.publish(
            "pwa_invalidate",
            {"resources": ["phase11/two-worker"], "reason": "phase11-smoke"},
        )
        await publisher.flush()
        first_event, second_event = await asyncio.gather(
            first_socket.receive_json(timeout=5),
            second_socket.receive_json(timeout=5),
        )
        assert first_event["type"] == second_event["type"] == "invalidate"
        assert (
            first_event["resources"]
            == second_event["resources"]
            == ["phase11/two-worker"]
        )

        await second_socket.close()
        reconnected_socket = await session.ws_connect(
            f"{origins[1].replace('http:', 'ws:')}/student/ws?cursor="
            f"{second_event['cursor']}",
            origin=origins[1],
        )
        assert (await reconnected_socket.receive_json(timeout=5))["type"] == (
            "resync-required"
        )
    finally:
        for websocket in (first_socket, second_socket, reconnected_socket):
            if websocket is not None and not websocket.closed:
                await websocket.close()
        await publisher.disconnect()
        await session.close()
        for process in processes:
            _stop_worker(process)
        for log_file in log_files:
            log_file.close()
