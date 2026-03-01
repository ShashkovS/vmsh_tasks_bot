# -*- coding: utf-8 -*-
import json
import logging
from types import SimpleNamespace

from helpers.trace import (
    TRACE_LOGGER_NAME,
    build_callback_ctx,
    build_message_ctx,
    clear_trace_context,
    emit_trace,
    init_trace,
    set_trace_context,
    trace_enabled,
)


def _flush_trace_handlers():
    logger = logging.getLogger(TRACE_LOGGER_NAME)
    for handler in logger.handlers:
        handler.flush()


def test_trace_writes_jsonl(tmp_path):
    log_path = tmp_path / "events.jsonl"
    cfg = SimpleNamespace(trace_enabled=True, trace_log_path=str(log_path), trace_backup_days=2)
    init_trace(cfg)
    assert trace_enabled()

    set_trace_context(trace_id="m:10:20", flow_id="u:1", source="tg.message", user_id=1)
    emit_trace(
        "update.message.received",
        ok=True,
        text="must_be_dropped",
        message_text="must_be_dropped_too",
        text_len=17,
        command="start",
    )
    clear_trace_context()
    _flush_trace_handlers()

    assert log_path.exists()
    rows = log_path.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    payload = json.loads(rows[0])
    assert payload["event"] == "update.message.received"
    assert payload["trace_id"] == "m:10:20"
    assert payload["flow_id"] == "u:1"
    assert payload["text_len"] == 17
    assert payload["command"] == "start"
    assert "text" not in payload
    assert "message_text" not in payload


def test_trace_noop_when_disabled(tmp_path):
    log_path = tmp_path / "disabled.jsonl"
    cfg = SimpleNamespace(trace_enabled=False, trace_log_path=str(log_path), trace_backup_days=2)
    init_trace(cfg)
    assert not trace_enabled()
    emit_trace("update.message.received", trace_id="x", flow_id="x", source="x")
    assert not log_path.exists()


def test_build_message_ctx_has_no_full_text():
    message = SimpleNamespace(
        chat=SimpleNamespace(id=77),
        message_id=88,
        text="/start hello world",
        photo=[1, 2],
        document=SimpleNamespace(mime_type="image/jpeg", file_size=1024),
        media_group_id="mg-1",
    )
    user = SimpleNamespace(id=11, type=1, group_id="novice")
    ctx = build_message_ctx(message, user)
    assert ctx["trace_id"] == "m:77:88"
    assert ctx["flow_id"] == "u:11"
    assert ctx["command"] == "start"
    assert ctx["text_len"] == len("/start hello world")
    assert "text" not in ctx


def test_build_callback_ctx_has_callback_meta_only():
    query = SimpleNamespace(
        id="cbq1",
        data="t_123_456",
        message=SimpleNamespace(chat=SimpleNamespace(id=55), message_id=66),
    )
    user = SimpleNamespace(id=99, type=1, group_id="novice")
    ctx = build_callback_ctx(query, user)
    assert ctx["trace_id"] == "c:55:66:cbq1"
    assert ctx["flow_id"] == "u:99"
    assert ctx["callback_type"] == "t"
    assert ctx["callback_len"] == len("t_123_456")
    assert "callback_data" not in ctx
