"""Real child, request drain and Gunicorn SIGTERM; vmshpwa/docs/graceful-shutdown.md."""

import asyncio
import json
import os
import signal
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import aiohttp
import pytest
from aiohttp import web
from helpers.math_worker import MathWorker

import main
from helpers import checkers
from pwa_tests.sqlite_template import create_test_database

ROOT = Path(__file__).resolve().parents[2]


def assert_gone(pid):
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


@pytest.fixture
def symbolic_worker(monkeypatch):
    worker = MathWorker(method="spawn")
    monkeypatch.setattr(checkers, "worker", worker)
    yield worker
    checkers.shutdown_worker()


def test_symbolic_child_and_pipes_close_and_can_restart(symbolic_worker):
    assert checkers.symb_eq("a+b", "b+a")
    assert checkers.symb_eq2("x+x", "2*x")
    assert not checkers.symb_eq("x+x", "2*x")
    assert not checkers.symb_eq2("1", "2")
    pid = symbolic_worker.process.pid
    pipes = (symbolic_worker.pipe_worker, symbolic_worker.pipe_manager)
    checkers.shutdown_worker()
    assert_gone(pid)
    assert all(pipe.closed for pipe in pipes)
    assert symbolic_worker.process is None
    checkers.shutdown_worker()
    # A late thread cannot recreate a child after its app's cleanup completed.
    assert not checkers.symb_eq("b+a", "a+b")
    assert symbolic_worker.process is None
    checkers.resume_worker()
    assert checkers.symb_eq("b+a", "a+b")
    assert symbolic_worker.process.pid != pid



def test_systemd_term_does_not_interrupt_the_owned_child(symbolic_worker):
    assert checkers.symb_eq("a+b", "b+a")
    pid = symbolic_worker.process.pid
    os.kill(pid, signal.SIGTERM)
    assert checkers.symb_eq("b+a", "a+b")
    assert symbolic_worker.process.pid == pid
    checkers.shutdown_worker()
    assert_gone(pid)


def test_calculation_deadline_reaps_a_child_that_ignores_term(symbolic_worker, monkeypatch):
    from helpers import math_worker
    from pwa_tests.fixtures.shutdown_probe import stalled_symbolic_worker

    with monkeypatch.context() as patch:
        patch.setattr(math_worker, "run_worker", stalled_symbolic_worker)
        result = symbolic_worker.strict_compare_v2("a+b", "b+a", timeout=0.01)
    assert "error" in result
    assert symbolic_worker.process is None
    assert symbolic_worker.pipe_worker is symbolic_worker.pipe_manager is None
    assert checkers.symb_eq("a+b", "b+a")


def test_concurrent_symbolic_answers_keep_their_receipts(symbolic_worker):
    # The library uses one pipe/task_id; calls from different HTTP threads
    # must not consume each other's reply.
    cases = [("a+b", "b+a", True), ("1", "2", False)] * 8
    with ThreadPoolExecutor(max_workers=4) as executor:
        pending = [executor.submit(checkers.symb_eq, a, b) for a, b, _ in cases]
        assert [task.result(timeout=5) for task in pending] == [r for _, _, r in cases]


def test_shutdown_waits_for_an_accepted_symbolic_answer(symbolic_worker, monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    closing = threading.Event()
    pids = []
    compare = symbolic_worker.strict_compare_v2

    def active(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        result = compare(*args, **kwargs)
        pids.append(symbolic_worker.process.pid)
        return result

    def stop():
        closing.set()
        checkers.shutdown_worker()

    monkeypatch.setattr(symbolic_worker, "strict_compare_v2", active)
    with ThreadPoolExecutor(max_workers=2) as executor:
        answer = executor.submit(checkers.symb_eq, "a+b", "b+a")
        assert entered.wait(5)
        cleanup = executor.submit(stop)
        assert closing.wait(5)
        try:
            assert not cleanup.done()
        finally:
            release.set()
        assert answer.result(timeout=5)
        cleanup.result(timeout=5)
    assert_gone(pids[0])


@pytest.mark.asyncio
async def test_cleanup_does_not_import_a_checker(monkeypatch):
    monkeypatch.delitem(sys.modules, "helpers.checkers", raising=False)
    context = main.math_worker_lifecycle(web.Application())
    await anext(context)
    with pytest.raises(StopAsyncIteration):
        await anext(context)
    assert "helpers.checkers" not in sys.modules


@pytest.mark.asyncio
async def test_cancelled_cleanup_still_reaps_child(symbolic_worker, monkeypatch):
    assert await asyncio.to_thread(checkers.symb_eq, "a+b", "b+a")
    pid = symbolic_worker.process.pid
    entered = threading.Event()
    release = threading.Event()
    shutdown = checkers.shutdown_worker

    def stop():
        entered.set()
        assert release.wait(5)
        shutdown()

    monkeypatch.setattr(checkers, "shutdown_worker", stop)
    context = main.math_worker_lifecycle(web.Application())
    await anext(context)
    cleanup = asyncio.create_task(anext(context))
    assert await asyncio.to_thread(entered.wait, 5)
    try:
        for _ in range(3):
            cleanup.cancel()
            await asyncio.sleep(0)
            assert not cleanup.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await cleanup
    assert_gone(pid)


@pytest.mark.asyncio
@pytest.mark.skipif(os.name != "posix", reason="Gunicorn requires POSIX")
async def test_two_gunicorn_workers_reap_symbolic_children_on_sigterm():
    # Own process group/private Unix socket; no production credentials, ports,
    # media, NATS or database. Linux uses exactly the production worker class.
    with tempfile.TemporaryDirectory(prefix="vmsh-sd-", dir="/tmp") as folder:
        root = Path(folder)
        database = root / "probe.sqlite3"
        create_test_database(database)
        socket = root / "api.sock"
        metrics = root / "metrics"
        metrics.mkdir()
        environment = {
            key: value for key, value in os.environ.items()
            if not key.startswith("VMSH_") and key != "PROD"
        }
        environment.update(
            PROD="false", PYTHONPATH=str(ROOT), VMSH_RUNTIME_PROFILE="pwa-e2e",
            VMSH_PWA_PROTOTYPE="true", VMSH_INSTANCE="e2e-shutdown-probe",
            VMSH_DB_FILENAME=str(database), VMSH_MEDIA_ROOT=str(root / "media"),
            VMSH_NATS_SERVER="", PROMETHEUS_MULTIPROC_DIR=str(metrics),
        )
        children = set()
        with (root / "gunicorn.log").open("w+") as log:
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "gunicorn", "--config", "gunicorn.conf.py",
                "--workers", "2", "--worker-class",
                "uvloop_worker.GunicornUVLoopWebWorkerFixed", "--bind", f"unix:{socket}",
                "--no-control-socket", "--timeout", "15", "--graceful-timeout", "5",
                "pwa_tests.fixtures.shutdown_probe:create_app()",
                cwd=ROOT, env=environment, stdout=log, stderr=log, start_new_session=True,
            )
            workers = set()
            try:
                async with aiohttp.ClientSession(
                    connector=aiohttp.UnixConnector(path=str(socket), force_close=True),
                    timeout=aiohttp.ClientTimeout(total=3),
                ) as session:
                    deadline = time.monotonic() + 20
                    while len(workers) < 2 and time.monotonic() < deadline:
                        try:
                            async with session.get("http://localhost/symbolic") as response:
                                assert response.status == 200
                                result = await response.json()
                                assert result["equal"] and result["method"] == "spawn"
                                workers.add(result["pid"])
                                children.add(result["child"])
                        except (aiohttp.ClientConnectionError, TimeoutError):
                            if process.returncode is not None:
                                log.seek(0)
                                pytest.fail(log.read())
                            await asyncio.sleep(0.05)
                    assert len(workers) == len(children) == 2
                started = time.monotonic()
                process.send_signal(signal.SIGTERM)
                result = await asyncio.wait_for(process.wait(), timeout=5)
                elapsed = time.monotonic() - started
                log.seek(0)
                output = log.read()
                assert result == 0, output
                # The five-second wait above guards shutdown correctness even
                # under parallel-suite load. Record speed separately below;
                # an arbitrary three-second wall-clock limit is CPU-sensitive.
                assert "SIGKILL" not in output and "WORKER TIMEOUT" not in output
                for pid in children:
                    assert_gone(pid)
                print(json.dumps({"gunicorn_shutdown_seconds": round(elapsed, 3),
                                  "workers": 2, "symbolic_children": 2, "exit_code": result}))
            finally:
                # Test-only process group; never leave a failed reproduction alive.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await process.wait()
