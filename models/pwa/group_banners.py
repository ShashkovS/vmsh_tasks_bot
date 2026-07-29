"""Small validation and sanitizing rules for group banner windows."""

from __future__ import annotations

import html
import re
import sqlite3
from datetime import datetime

import nh3

from db_methods.pwa.group_banners import (
    cancel_group_banner,
    insert_group_banner,
    update_group_banner,
)


_AUDIENCES = frozenset({"student", "family", "both"})
_TAG = re.compile(r"<[^>]*>")


class InvalidGroupBanner(ValueError):
    pass


class GroupBannerConflict(Exception):
    pass


def sanitize_group_banner_html(value: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 5_000:
        raise InvalidGroupBanner("html")
    sanitized = nh3.clean(
        value,
        tags={"a", "b", "code", "i"},
        attributes={"a": {"href"}},
        url_schemes={"https", "mailto"},
        link_rel="noopener noreferrer",
    ).strip()
    text = html.unescape(_TAG.sub("", sanitized)).strip()
    if not text:
        raise InvalidGroupBanner("html")
    return sanitized


def _window(starts_at: str, ends_at: str) -> None:
    try:
        start = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise InvalidGroupBanner("window") from error
    if (
        start.tzinfo is None
        or end.tzinfo is None
        or start.utcoffset() is None
        or end.utcoffset() is None
        or end <= start
    ):
        raise InvalidGroupBanner("window")


def create_group_banner(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    group_id: str,
    audience: str,
    html_source: str,
    starts_at: str,
    ends_at: str,
    priority: int,
    dismissible: bool,
    actor_user_id: int,
    now: str,
) -> dict[str, object]:
    _window(starts_at, ends_at)
    if audience not in _AUDIENCES or not -100 <= priority <= 100:
        raise InvalidGroupBanner("settings")
    return insert_group_banner(
        connection,
        public_id=public_id,
        group_id=group_id,
        audience=audience,
        html_sanitized=sanitize_group_banner_html(html_source),
        starts_at=starts_at,
        ends_at=ends_at,
        priority=priority,
        dismissible=dismissible,
        actor_user_id=actor_user_id,
        now=now,
    )


def edit_group_banner(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    audience: str,
    html_source: str,
    starts_at: str,
    ends_at: str,
    priority: int,
    dismissible: bool,
    actor_user_id: int,
    now: str,
) -> dict[str, object]:
    _window(starts_at, ends_at)
    if audience not in _AUDIENCES or not -100 <= priority <= 100:
        raise InvalidGroupBanner("settings")
    item = update_group_banner(
        connection,
        public_id=public_id,
        expected_version=expected_version,
        audience=audience,
        html_sanitized=sanitize_group_banner_html(html_source),
        starts_at=starts_at,
        ends_at=ends_at,
        priority=priority,
        dismissible=dismissible,
        actor_user_id=actor_user_id,
        now=now,
    )
    if item is None:
        raise GroupBannerConflict
    return item


def cancel_banner(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    actor_user_id: int,
    now: str,
) -> dict[str, object]:
    item = cancel_group_banner(
        connection,
        public_id=public_id,
        expected_version=expected_version,
        actor_user_id=actor_user_id,
        now=now,
    )
    if item is None:
        raise GroupBannerConflict
    return item


__all__ = [
    "GroupBannerConflict",
    "InvalidGroupBanner",
    "cancel_banner",
    "create_group_banner",
    "edit_group_banner",
    "sanitize_group_banner_html",
]
