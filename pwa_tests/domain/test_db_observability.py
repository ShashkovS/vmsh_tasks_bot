import asyncio
import json

import pytest
from prometheus_client import CollectorRegistry, multiprocess

from helpers.pwa import db_observability as diagnostics
from helpers.pwa.request_trace import RequestTrace, current_trace


def sample(name, role):
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return sum(
        s.value
        for metric in registry.collect()
        for s in metric.samples
        if s.name == name and s.labels.get("role") == role
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["read", "write"])
async def test_owner_queue_cancellation_and_burst(role, monkeypatch, caplog):
    monkeypatch.setattr(diagnostics, "OWNER_INTERVAL", 0.01)
    monkeypatch.setattr(diagnostics, "SLOW_SECONDS", 0)
    slots = asyncio.Semaphore(1)
    depth = {"read": 0, "write": 0}
    entered = asyncio.Event()
    release = asyncio.Event()
    baseline = {key: sample(f"vmsh_db_{key}", role) for key in ("active", "waiting")}

    async def operation():
        async with diagnostics.observed_admission(role, slots, operation, depth):
            entered.set()
            await release.wait()

    token = current_trace.set(RequestTrace(request_id="test-owner", route="/api/{id}"))
    try:
        owner = asyncio.create_task(operation())
        await entered.wait()
        waiters = [asyncio.create_task(operation()) for _ in range(5)]
        await asyncio.sleep(0.03)
        assert depth[role] == 5
        assert sample("vmsh_db_waiting", role) == baseline["waiting"] + 5
        assert sample("vmsh_db_active", role) == baseline["active"] + 1
        waiters[0].cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiters[0]
        assert depth[role] == 4
        records = [
            json.loads(r.message.split(" ", 1)[1])
            for r in caplog.records
            if r.message.startswith("pwa_db_operation ")
        ]
        assert any(
            r["event"] == "holding"
            and r["queue_depth"] == 5
            and r["request_id"] == "test-owner"
            and r["route"] == "/api/{id}"
            for r in records
        )
        release.set()
        await asyncio.gather(owner, *waiters[1:])
        assert depth[role] == 0
        for key in baseline:
            assert sample(f"vmsh_db_{key}", role) == baseline[key]
        count = len(caplog.records)
        await asyncio.sleep(0.03)
        assert len(caplog.records) == count
    finally:
        release.set()
        current_trace.reset(token)
