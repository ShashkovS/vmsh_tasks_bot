# -*- coding: utf-8 -*-
from __future__ import annotations

import contextvars
import json
import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

from helpers.consts import USER_TYPE

TRACE_LOGGER_NAME = "MathBotTrace"
TRACE_FIELD_MAX_LEN = 256
TRACE_ERROR_MAX_LEN = 240

_TRACE_CONTEXT: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar("trace_context", default={})
_TRACE_ENABLED = False
_TRACE_LOGGER: Optional[logging.Logger] = None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _safe_short(value: Any, *, max_len: int = TRACE_FIELD_MAX_LEN) -> Any:
    if isinstance(value, str):
        if len(value) <= max_len:
            return value
        return value[:max_len]
    return value


def _jsonify(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return _safe_short(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value") and not isinstance(value, (list, tuple, dict, set)):
        # Enums and enum-like values
        return _jsonify(value.value)
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, item in value.items():
            key_s = str(key)
            if key_s in {"message_text", "text", "msg_text", "callback_data"}:
                continue
            json_item = _jsonify(item)
            if json_item is not None:
                out[key_s] = json_item
        return out
    if isinstance(value, (list, tuple, set)):
        return [_jsonify(item) for item in value]
    return _safe_short(str(value))


def trace_enabled() -> bool:
    return _TRACE_ENABLED and _TRACE_LOGGER is not None


def init_trace(config) -> None:
    global _TRACE_ENABLED, _TRACE_LOGGER
    enabled = _as_bool(getattr(config, "trace_enabled", False))
    trace_log_path = str(getattr(config, "trace_log_path", "logs/events.jsonl"))
    trace_backup_days = int(getattr(config, "trace_backup_days", 21) or 21)

    logger = logging.getLogger(TRACE_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    _TRACE_ENABLED = enabled
    if not enabled:
        _TRACE_LOGGER = None
        return

    log_path = Path(trace_log_path)
    if not log_path.is_absolute():
        log_path = Path(os.getcwd()) / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    rotating_handler = TimedRotatingFileHandler(
        filename=str(log_path),
        when="midnight",
        backupCount=max(1, trace_backup_days),
        encoding="utf-8",
        delay=True,
    )
    rotating_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(rotating_handler)
    _TRACE_LOGGER = logger


def set_trace_context(**ctx: Any) -> None:
    _TRACE_CONTEXT.set(_jsonify(ctx) or {})


def update_trace_context(**ctx: Any) -> None:
    current = get_trace_context()
    current.update(_jsonify(ctx) or {})
    _TRACE_CONTEXT.set(current)


def get_trace_context() -> Dict[str, Any]:
    return dict(_TRACE_CONTEXT.get({}) or {})


def clear_trace_context() -> None:
    _TRACE_CONTEXT.set({})


def emit_trace(event: str, **fields: Any) -> None:
    if not trace_enabled():
        return
    logger = _TRACE_LOGGER
    if logger is None:
        return

    payload: Dict[str, Any] = {}
    payload.update(get_trace_context())
    payload.update(_jsonify(fields) or {})
    payload["ts"] = datetime.now().isoformat(timespec="milliseconds")
    payload["event"] = event
    payload.setdefault("trace_id", "na")
    payload.setdefault("flow_id", "na")
    payload.setdefault("ok", True)
    payload.setdefault("source", "unknown")

    try:
        logger.info(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    except Exception as exc:
        # Trace logging must never break business flow.
        fallback = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "event": "trace.emit.error",
            "trace_id": payload.get("trace_id", "na"),
            "flow_id": payload.get("flow_id", "na"),
            "ok": False,
            "source": "trace",
            "error_type": exc.__class__.__name__,
            "error_short": _safe_short(str(exc), max_len=TRACE_ERROR_MAX_LEN),
        }
        try:
            logger.info(json.dumps(fallback, ensure_ascii=False, separators=(",", ":")))
        except Exception:
            pass


def _extract_command(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    token = text.strip().split(maxsplit=1)[0]
    if not token.startswith("/"):
        return None
    token = token[1:]
    if "@" in token:
        token = token.split("@", 1)[0]
    return token or None


def _actor_type(user) -> str:
    if not user:
        return "anonymous"
    try:
        user_type = USER_TYPE(user.type)
    except Exception:
        return "unknown"

    if user_type == USER_TYPE.STUDENT:
        return "student"
    if user_type == USER_TYPE.TEACHER:
        return "teacher"
    if user_type == USER_TYPE.ADMIN:
        return "admin"
    if user_type == USER_TYPE.UNKNOWN:
        return "unknown_user"
    if user_type == USER_TYPE.DEACTIVATED_STUDENT:
        return "deactivated_student"
    if user_type == USER_TYPE.DELETED:
        return "deleted_user"
    if user_type & USER_TYPE.TEACHER_OR_ADMIN:
        return "teacher_admin"
    return "unknown"


def _flow_id(chat_id: Optional[int], user_id: Optional[int]) -> str:
    if user_id is not None:
        return f"u:{user_id}"
    if chat_id is not None:
        return f"ch:{chat_id}"
    return "na"


def build_message_ctx(message, user=None) -> dict:
    chat = getattr(message, "chat", None)
    chat_id = getattr(chat, "id", None)
    message_id = getattr(message, "message_id", None)
    text = getattr(message, "text", None) or ""
    doc = getattr(message, "document", None)
    photo = getattr(message, "photo", None) or []
    user_id = getattr(user, "id", None)

    return {
        "trace_id": f"m:{chat_id}:{message_id}",
        "flow_id": _flow_id(chat_id, user_id),
        "source": "tg.message",
        "update_type": "message",
        "chat_id": chat_id,
        "tg_message_id": message_id,
        "user_id": user_id,
        "actor_type": _actor_type(user),
        "group_id": getattr(user, "group_id", None) if user else None,
        "command": _extract_command(text),
        "has_text": bool(text),
        "text_len": len(text),
        "photo_count": len(photo),
        "doc_mime": getattr(doc, "mime_type", None),
        "doc_size": getattr(doc, "file_size", None),
        "media_group_id": getattr(message, "media_group_id", None),
    }


def build_callback_ctx(query, user=None) -> dict:
    message = getattr(query, "message", None)
    chat = getattr(message, "chat", None)
    chat_id = getattr(chat, "id", None)
    message_id = getattr(message, "message_id", None)
    callback_data = getattr(query, "data", None) or ""
    callback_type = callback_data[:1] if callback_data else None
    user_id = getattr(user, "id", None)
    query_id = getattr(query, "id", None)

    return {
        "trace_id": f"c:{chat_id}:{message_id}:{query_id}",
        "flow_id": _flow_id(chat_id, user_id),
        "source": "tg.callback",
        "update_type": "callback",
        "chat_id": chat_id,
        "tg_message_id": message_id,
        "user_id": user_id,
        "actor_type": _actor_type(user),
        "group_id": getattr(user, "group_id", None) if user else None,
        "callback_type": callback_type,
        "callback_len": len(callback_data),
    }
