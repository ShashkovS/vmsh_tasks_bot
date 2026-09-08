import asyncio
import json
import logging

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from helpers.pwa.request_trace import (
    RequestTrace,
    current_trace,
    trace_stage,
    traced_thread,
    request_trace_middleware,
    event_loop_trace_lifecycle,
)


@pytest.mark.asyncio
async def test_thread_context_and_failure_timings():
    trace = RequestTrace()
    token = current_trace.set(trace)
    try:

        def operation():
            with trace_stage("db.read"):
                raise ValueError("secret")

        with pytest.raises(ValueError):
            await traced_thread(operation)
        assert trace.stages["db.thread_queue"][0] == 1
        assert trace.stages["db.read"][0] == 1
    finally:
        current_trace.reset(token)


@pytest.mark.asyncio
async def test_slow_request_safe_payload_and_reset(caplog, monkeypatch):
    monkeypatch.setattr(
        "helpers.pwa.request_trace.canonical_route",
        lambda _: "/student/api/v1/problems/{id}",
    )
    request = make_mocked_request(
        "GET", "/student/api/v1/problems/secret?answer=secret"
    )
    request["request_id"] = "test-id"

    async def handler(request):
        with trace_stage("auth"):
            await asyncio.sleep(0.21)
        return web.Response(status=422)

    with caplog.at_level(logging.INFO):
        response = await request_trace_middleware(request, handler)
    assert response.status == 422
    assert current_trace.get() is None
    payload = json.loads(caplog.records[-1].message.split(" ", 1)[1])
    assert payload["request_id"] == "test-id"
    assert payload["status"] == 422
    assert payload["stages"]["auth"]["count"] == 1
    assert "secret" not in caplog.text


@pytest.mark.asyncio
async def test_fast_request_and_monitor_cleanup(caplog, monkeypatch):
    monkeypatch.setattr(
        "helpers.pwa.request_trace.canonical_route", lambda _: "/student/api/v1/home"
    )

    async def handler(request):
        return web.Response()

    with caplog.at_level(logging.INFO):
        await request_trace_middleware(make_mocked_request("GET", "/"), handler)
    assert not caplog.records
    lifecycle = event_loop_trace_lifecycle(web.Application())
    await anext(lifecycle)
    await lifecycle.aclose()
    assert not [
        task
        for task in asyncio.all_tasks()
        if task.get_name() == "pwa-event-loop-trace"
    ]


@pytest.mark.asyncio
async def test_parallel_requests_do_not_share_timings():
    async def run(name):
        trace = RequestTrace()
        token = current_trace.set(trace)
        try:
            await traced_thread(lambda: trace.add(name, 0.001))
            return trace.stages
        finally:
            current_trace.reset(token)

    first, second = await asyncio.gather(run("first"), run("second"))
    assert "second" not in first
    assert "first" not in second
