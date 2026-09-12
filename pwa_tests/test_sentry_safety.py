from __future__ import annotations

import sys
from types import ModuleType

from helpers import config as config_module
from helpers.pwa.sentry_safety import (
    sanitize_sentry_breadcrumb,
    sanitize_sentry_event,
)


def test_backend_sentry_event_removes_private_request_and_product_data() -> None:
    sanitized = sanitize_sentry_event(
        {
            "user": {"id": "student-17", "ip_address": "192.0.2.1"},
            "request": {
                "url": "https://vmsh.example/student/tasks?student=17#answer",
                "cookies": {"vmsh_student_access": "secret-cookie"},
                "headers": {"Authorization": "Bearer secret"},
                "data": {"answer": "179"},
                "env": {"REMOTE_ADDR": "192.0.2.1"},
            },
            "extra": {
                "requestId": "request-17",
                "telegramToken": "secret-token",
                "teacherComment": "Точный комментарий",
            },
            "contexts": {
                "product": {
                    "courseId": "math-57",
                    "photoUrl": "https://media.example/sol_imgs/user_17/private.webp",
                }
            },
        }
    )

    assert "user" not in sanitized
    assert sanitized["request"] == {"url": "https://vmsh.example/student/tasks"}
    assert sanitized["extra"] == {
        "requestId": "request-17",
        "telegramToken": "[redacted]",
        "teacherComment": "[redacted]",
    }
    assert sanitized["contexts"]["product"] == {
        "courseId": "math-57",
        "photoUrl": "[redacted]",
    }


def test_backend_sentry_breadcrumb_hides_log_text_and_query() -> None:
    assert sanitize_sentry_breadcrumb(
        {
            "category": "log",
            "message": "Ученик написал своё решение",
            "data": {
                "url": "https://vmsh.example/staff/review?student=Иванов",
                "answer": "179",
            },
        }
    ) == {
        "category": "log",
        "message": "[redacted]",
        "data": {
            "url": "https://vmsh.example/staff/review",
            "answer": "[redacted]",
        },
    }


def test_sentry_initialization_uses_privacy_hooks(monkeypatch) -> None:
    captured: dict[str, object] = {}
    fake_sdk = ModuleType("sentry_sdk")
    fake_sdk.init = lambda **kwargs: captured.update(kwargs)
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sdk)

    for module_name, class_name in (
        ("sentry_sdk.integrations.aiohttp", "AioHttpIntegration"),
        ("sentry_sdk.integrations.asyncio", "AsyncioIntegration"),
        ("sentry_sdk.integrations.logging", "LoggingIntegration"),
    ):
        module = ModuleType(module_name)
        setattr(module, class_name, lambda **_kwargs: object())
        monkeypatch.setitem(sys.modules, module_name, module)

    config_module._init_sentry("https://public@example.invalid/1", "pwa", "rev-17")

    assert captured["send_default_pii"] is False
    assert captured["before_send"] is sanitize_sentry_event
    assert captured["before_send_transaction"] is sanitize_sentry_event
    assert captured["before_breadcrumb"] is sanitize_sentry_breadcrumb
    assert captured["release"] == "rev-17"


def test_pwa_runtime_reads_only_explicit_sentry_environment(monkeypatch) -> None:
    monkeypatch.setenv("VMSH_RUNTIME_PROFILE", "pwa-agent")
    monkeypatch.setenv("VMSH_SENTRY_DSN", "https://public@example.invalid/1")
    monkeypatch.setenv("VMSH_SENTRY_RELEASE", "rev-18")

    runtime = config_module._setup()

    assert runtime.sentry_dsn == "https://public@example.invalid/1"
    assert runtime.sentry_release == "rev-18"
    assert runtime.telegram_bot_token == ""
    assert runtime.google_cred_json == ""
