"""Small transition rules for hiding Telegram news in the PWA."""

from __future__ import annotations

import sqlite3

from db_methods.pwa.news_moderation import (
    list_news_for_moderation,
    update_news_source_state,
    update_news_visibility,
)


class NewsPostNotFound(LookupError):
    pass


class NewsVisibilityConflict(RuntimeError):
    pass


class InvalidNewsVisibility(ValueError):
    pass


def change_news_visibility(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    target_state: object,
    reason: object,
    actor_user_id: int,
    now: str,
) -> dict[str, object]:
    rows = list_news_for_moderation(
        connection, state=None, limit=1, public_id=public_id
    )
    if not rows:
        raise NewsPostNotFound
    current = rows[0]
    if int(current["visibility_version"]) != expected_version:
        raise NewsVisibilityConflict
    if current["visibility_state"] == "source_deleted":
        raise InvalidNewsVisibility("source_deleted")
    if target_state not in {"visible", "manual_hidden"}:
        raise InvalidNewsVisibility("state")
    if reason is not None:
        if not isinstance(reason, str):
            raise InvalidNewsVisibility("reason")
        reason = reason.strip()
        if not reason or len(reason) > 500:
            raise InvalidNewsVisibility("reason")
    if target_state == "visible":
        reason = None
    if (
        current["visibility_state"] == target_state
        and current["moderation_reason"] == reason
    ):
        return current
    updated = update_news_visibility(
        connection,
        public_id=public_id,
        expected_version=expected_version,
        state=target_state,
        reason=reason,
        actor_user_id=actor_user_id,
        now=now,
    )
    if updated is None:
        raise NewsVisibilityConflict
    return updated


def reconcile_news_source_state(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    source_state: object,
    actor_user_id: int,
    now: str,
) -> tuple[dict[str, object], dict[str, object]]:
    """Reconcile manually verified Telegram presence without guessing updates.

    The Bot API has no ordinary channel-post deletion update, so the explicit
    admin workflow is authoritative here. See
    ``vmshpwa/docs/telegram-news-deletion-reconciliation.md``.
    """

    rows = list_news_for_moderation(
        connection, state=None, limit=1, public_id=public_id
    )
    if not rows:
        raise NewsPostNotFound
    current = rows[0]
    if int(current["visibility_version"]) != expected_version:
        raise NewsVisibilityConflict
    if current["source_type"] != "telegram" or source_state not in {
        "deleted",
        "present",
    }:
        raise InvalidNewsVisibility("source_state")
    if source_state == "deleted" and current["visibility_state"] == "source_deleted":
        raise InvalidNewsVisibility("already_deleted")
    if source_state == "present" and current["visibility_state"] != "source_deleted":
        raise InvalidNewsVisibility("already_present")

    updated = update_news_source_state(
        connection,
        public_id=public_id,
        expected_version=expected_version,
        source_state=source_state,
        actor_user_id=actor_user_id,
        now=now,
    )
    if updated is None:
        raise NewsVisibilityConflict
    return current, updated


__all__ = [
    "InvalidNewsVisibility",
    "NewsPostNotFound",
    "NewsVisibilityConflict",
    "change_news_visibility",
    "reconcile_news_source_state",
]
