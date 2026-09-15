"""Focused tests for the pywebpush transport adapter."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pywebpush import WebPushException

from helpers.pwa import web_push


async def test_web_push_adapter_passes_vapid_and_json(monkeypatch):
    calls = []

    def fake_webpush(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(web_push, "webpush", fake_webpush)
    await web_push.send_web_push(
        {
            "endpoint": "https://push.example.test/device",
            "keys": {"p256dh": "public", "auth": "secret"},
        },
        {"title": "Проверка завершена", "silent": True},
        private_key="private-vapid-key",
        subject="mailto:vmsh@179.ru",
    )

    assert json.loads(calls[0]["data"]) == {
        "title": "Проверка завершена",
        "silent": True,
    }
    assert calls[0]["vapid_private_key"] == "private-vapid-key"
    assert calls[0]["vapid_claims"] == {"sub": "mailto:vmsh@179.ru"}
    assert calls[0]["timeout"] == 10


async def test_web_push_adapter_classifies_gone_subscription(monkeypatch):
    def fake_webpush(**_kwargs):
        raise WebPushException(
            "gone",
            response=SimpleNamespace(status_code=410),
        )

    monkeypatch.setattr(web_push, "webpush", fake_webpush)
    with pytest.raises(web_push.WebPushTransportError) as caught:
        await web_push.send_web_push(
            {"endpoint": "https://push.example.test/device", "keys": {}},
            {"title": "Test"},
            private_key="private-vapid-key",
            subject="mailto:vmsh@179.ru",
        )
    assert caught.value.status_code == 410
    assert caught.value.stale_subscription
    assert not caught.value.retryable
