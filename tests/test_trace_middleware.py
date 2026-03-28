from __future__ import annotations

from types import SimpleNamespace

import pytest

from helpers import trace_middleware
from helpers.trace import get_trace_context

from .telegram_harness import make_callback_query, make_message

pytestmark = pytest.mark.asyncio


async def test_message_middleware_emits_update_and_command_events(live_seed_db, monkeypatch):
    user = live_seed_db.bind_chat(live_seed_db.get_user("qwerty1"), 86001)
    events = []

    async def handler(event, data):
        assert get_trace_context()["user_id"] == user.id
        return "ok"

    async def student_handler():
        return None

    student_handler.__module__ = "handlers.student_handlers"
    middleware = trace_middleware.TraceMessageMiddleware()
    monkeypatch.setattr(trace_middleware, "trace_enabled", lambda: True)
    monkeypatch.setattr(trace_middleware, "emit_trace", lambda event, **fields: events.append((event, fields)))

    result = await middleware(
        handler,
        make_message(user.chat_id, text="/results", message_id=1),
        {"handler": SimpleNamespace(callback=student_handler)},
    )

    assert result == "ok"
    assert [event for event, _ in events[:2]] == ["update.message.received", "command.invoked"]
    assert get_trace_context() == {}


async def test_callback_middleware_emits_routing_and_error_events(live_seed_db, monkeypatch):
    user = live_seed_db.bind_chat(live_seed_db.get_teacher(), 86002)
    events = []

    async def boom_handler(event, data):
        raise RuntimeError("boom")

    async def admin_handler():
        return None

    admin_handler.__module__ = "handlers.admin_handlers"
    middleware = trace_middleware.TraceCallbackMiddleware()
    monkeypatch.setattr(trace_middleware, "trace_enabled", lambda: True)
    monkeypatch.setattr(trace_middleware, "emit_trace", lambda event, **fields: events.append((event, fields)))

    with pytest.raises(RuntimeError):
        await middleware(
            boom_handler,
            make_callback_query("t_123", chat_id=user.chat_id, message_id=2),
            {"handler": SimpleNamespace(callback=admin_handler)},
        )

    assert [event for event, _ in events[:2]] == ["update.callback.received", "callback.routed"]
    assert events[-1][0] == "update.handler.error"
    assert events[-1][1]["error_type"] == "RuntimeError"
    assert get_trace_context() == {}
