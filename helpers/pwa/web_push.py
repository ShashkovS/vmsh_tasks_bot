"""Small pywebpush adapter that never exposes provider response bodies."""

from __future__ import annotations

import asyncio
import json

from pywebpush import WebPushException, webpush


class WebPushTransportError(Exception):
    def __init__(self, *, status_code: int | None) -> None:
        super().__init__("web_push_transport_failed")
        self.status_code = status_code
        self.stale_subscription = status_code in {404, 410}
        self.retryable = status_code is None or status_code == 429 or status_code >= 500


async def send_web_push(
    subscription: dict[str, object],
    payload: dict[str, object],
    *,
    private_key: str,
    subject: str,
) -> None:
    def send() -> None:
        try:
            webpush(
                subscription_info=subscription,
                data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
                ttl=24 * 60 * 60,
                timeout=10,
            )
        except WebPushException as error:
            response = error.response
            status_code = getattr(response, "status_code", None)
            raise WebPushTransportError(
                status_code=status_code if isinstance(status_code, int) else None
            ) from error

    await asyncio.to_thread(send)


__all__ = ["WebPushTransportError", "send_web_push"]
