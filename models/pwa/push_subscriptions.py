"""Validation rules for browser Web Push subscriptions."""

from __future__ import annotations

import base64
import binascii
import re
import sqlite3
import uuid
from urllib.parse import urlsplit

from db_methods.pwa.push_subscriptions import delete_subscription, save_subscription


class InvalidPushSubscription(Exception):
    pass


def _decode_key(value: str, *, expected_bytes: int, label: str) -> bytes:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None
    ):
        raise InvalidPushSubscription(label)
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, binascii.Error) as error:
        raise InvalidPushSubscription(label) from error
    if len(decoded) != expected_bytes:
        raise InvalidPushSubscription(label)
    return decoded


def register_subscription(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    session_id: int,
    endpoint: str,
    p256dh: str,
    auth_secret: str,
    expiration_time: int | None,
    user_agent: str | None,
    now: str,
) -> str:
    if not isinstance(endpoint, str) or len(endpoint) > 2048:
        raise InvalidPushSubscription("endpoint")
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise InvalidPushSubscription("endpoint")
    public_key = _decode_key(p256dh, expected_bytes=65, label="p256dh")
    if public_key[0] != 4:
        raise InvalidPushSubscription("p256dh")
    _decode_key(auth_secret, expected_bytes=16, label="auth")
    if expiration_time is not None and (
        not isinstance(expiration_time, int)
        or isinstance(expiration_time, bool)
        or expiration_time <= 0
        or expiration_time > 9_007_199_254_740_991
    ):
        raise InvalidPushSubscription("expiration_time")
    if user_agent is not None:
        user_agent = user_agent.strip()[:256] or None
    return save_subscription(
        connection,
        public_id=f"push.{uuid.uuid4().hex}",
        account_id=account_id,
        session_id=session_id,
        endpoint=endpoint,
        p256dh=p256dh,
        auth_secret=auth_secret,
        expiration_time=expiration_time,
        user_agent=user_agent,
        now=now,
    )


def unregister_subscription(
    connection: sqlite3.Connection, *, account_id: int, endpoint: str
) -> bool:
    if not isinstance(endpoint, str) or len(endpoint) > 2048:
        raise InvalidPushSubscription("endpoint")
    return delete_subscription(connection, account_id=account_id, endpoint=endpoint)


__all__ = [
    "InvalidPushSubscription",
    "register_subscription",
    "unregister_subscription",
]
