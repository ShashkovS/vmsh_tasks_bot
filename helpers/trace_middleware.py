# -*- coding: utf-8 -*-
from __future__ import annotations

import time

from aiogram import BaseMiddleware

from helpers.trace import (
    build_callback_ctx,
    build_message_ctx,
    clear_trace_context,
    emit_trace,
    set_trace_context,
    trace_enabled,
)
from models import User


def _handler_module(data: dict) -> str:
    handler_obj = data.get("handler")
    callback = getattr(handler_obj, "callback", None)
    if callback is None and callable(handler_obj):
        callback = handler_obj
    return getattr(callback, "__module__", "") if callback else ""


def _should_skip(module_name: str) -> bool:
    return module_name.startswith("handlers.group_and_channel_handlers")


def _command_event_name(module_name: str) -> str:
    if module_name.startswith("handlers.admin_handlers"):
        return "admin.command.invoked"
    return "command.invoked"


def _resolve_user(chat_id):
    if chat_id is None:
        return None
    try:

        return User.get_by_chat_id(chat_id)
    except Exception:
        return None


class TraceMessageMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if not trace_enabled():
            return await handler(event, data)

        module_name = _handler_module(data)
        chat = getattr(event, "chat", None)
        chat_type = getattr(chat, "type", None)
        if _should_skip(module_name) or (not module_name and chat_type in {"group", "supergroup", "channel"}):
            return await handler(event, data)

        chat_id = getattr(chat, "id", None)
        user = _resolve_user(chat_id)
        ctx = build_message_ctx(event, user=user)
        set_trace_context(**ctx)
        emit_trace("update.message.received", handler_module=module_name)
        if ctx.get("command"):
            emit_trace(_command_event_name(module_name), command=ctx["command"], handler_module=module_name)

        started_at = time.perf_counter()
        try:
            return await handler(event, data)
        except Exception as exc:
            emit_trace(
                "update.handler.error",
                ok=False,
                handler_module=module_name,
                error_type=exc.__class__.__name__,
                error_short=str(exc)[:240],
                duration_ms=round((time.perf_counter() - started_at) * 1000, 1),
            )
            raise
        finally:
            clear_trace_context()


class TraceCallbackMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if not trace_enabled():
            return await handler(event, data)

        module_name = _handler_module(data)
        message = getattr(event, "message", None)
        chat = getattr(message, "chat", None)
        chat_type = getattr(chat, "type", None)
        if _should_skip(module_name) or (not module_name and chat_type in {"group", "supergroup", "channel"}):
            return await handler(event, data)

        chat_id = getattr(chat, "id", None)
        user = _resolve_user(chat_id)
        ctx = build_callback_ctx(event, user=user)
        set_trace_context(**ctx)
        emit_trace("update.callback.received", handler_module=module_name)
        emit_trace("callback.routed", handler_module=module_name, callback_type=ctx.get("callback_type"))

        started_at = time.perf_counter()
        try:
            return await handler(event, data)
        except Exception as exc:
            emit_trace(
                "update.handler.error",
                ok=False,
                handler_module=module_name,
                error_type=exc.__class__.__name__,
                error_short=str(exc)[:240],
                duration_ms=round((time.perf_counter() - started_at) * 1000, 1),
            )
            raise
        finally:
            clear_trace_context()
