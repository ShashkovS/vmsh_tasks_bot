"""Strictly opt-in Core NATS smoke against the user-managed local server."""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest

from helpers.nats_brocker import NatsBroker

RUN_LIVE_NATS = os.environ.get("VMSH_RUN_LOCAL_NATS_SMOKE") == "1"
LOCAL_NATS_URL = "nats://127.0.0.1:4222"

pytestmark = pytest.mark.skipif(
    not RUN_LIVE_NATS,
    reason="set VMSH_RUN_LOCAL_NATS_SMOKE=1 for the isolated local NATS smoke",
)


@pytest.mark.asyncio
async def test_local_nats_agent_prefix_fanout_and_isolation():
    run_id = uuid.uuid4().hex[:12]
    agent_prefix = f"vmshpwa_agent_smoke_{run_id}"
    isolated_prefix = f"vmshpwa_agent_other_{run_id}"
    first = NatsBroker(agent_prefix)
    second = NatsBroker(agent_prefix)
    isolated = NatsBroker(isolated_prefix)
    delivered_first = asyncio.Event()
    delivered_second = asyncio.Event()
    leaked = asyncio.Event()

    async def receive_first(payload):
        assert payload == {"kind": "synthetic", "runId": run_id}
        delivered_first.set()

    async def receive_second(payload):
        assert payload == {"kind": "synthetic", "runId": run_id}
        delivered_second.set()

    async def receive_leak(_payload):
        leaked.set()

    primary_error: BaseException | None = None
    try:
        await asyncio.gather(
            first.setup(LOCAL_NATS_URL),
            second.setup(LOCAL_NATS_URL),
            isolated.setup(LOCAL_NATS_URL),
        )
        await first.subscribe("phase0_probe", receive_first)
        await second.subscribe("phase0_probe", receive_second)
        await isolated.subscribe("phase0_probe", receive_leak)
        await asyncio.gather(first.flush(), second.flush(), isolated.flush())

        await first.publish("phase0_probe", {"kind": "synthetic", "runId": run_id})
        await first.flush()
        await asyncio.wait_for(
            asyncio.gather(delivered_first.wait(), delivered_second.wait()), timeout=2
        )
        await asyncio.sleep(0.05)
        assert not leaked.is_set()
    except BaseException as error:
        primary_error = error
    finally:
        cleanup_results = await asyncio.gather(
            first.disconnect(),
            second.disconnect(),
            isolated.disconnect(),
            return_exceptions=True,
        )
        cleanup_errors = [
            result for result in cleanup_results if isinstance(result, BaseException)
        ]
        if cleanup_errors:
            failures = (
                [primary_error, *cleanup_errors]
                if primary_error is not None
                else cleanup_errors
            )
            raise BaseExceptionGroup(
                "Local NATS smoke operation and cleanup failed", failures
            )
    if primary_error is not None:
        raise primary_error
